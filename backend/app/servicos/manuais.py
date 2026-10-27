import json
import re
import secrets
import shutil
import sqlite3
import time
from pathlib import Path

from .. import config
from ..db import caminho_menu
from .limpeza import mascarar, tabelas_citadas


def manual_completo(con: sqlite3.Connection, codigo: str) -> dict | None:
    m = con.execute("SELECT m.*, mo.nome AS modulo_nome FROM manuais m JOIN modulos mo ON mo.id = m.modulo WHERE codigo = ?", (codigo,)).fetchone()
    if not m:
        return None
    return {**dict(m), "secoes": json.loads(m["conteudo"]), "tabelas": json.loads(m["tabelas"]), "conteudo": None,
            "fontes": json.loads(m["fontes"] or "[]"),
            "caminho": caminho_menu(con, m["menu"]) if m["menu"] else []}


def gravar_no_banco(con: sqlite3.Connection, m: dict, menu: str | None) -> None:
    """Upsert de um manual no formato dos arquivos JSON (seed e editor usam o mesmo caminho).

    atualizado_em: a data gravada no JSON pelo editor, quando houver; senão, agora. Num manual que já existe, a data
    só muda se o conteúdo mudou: o seed roda a cada subida e não pode "atualizar" manuais que ninguém mexeu.
    """
    con.execute("""INSERT INTO manuais (codigo, titulo, subtitulo, versao, modulo, menu, conteudo, tabelas, fontes, por, alterado_em, atualizado_em)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, datetime('now', 'localtime')))
                   ON CONFLICT(codigo) DO UPDATE SET
                     atualizado_em = CASE WHEN manuais.titulo = excluded.titulo AND manuais.subtitulo = excluded.subtitulo
                                           AND manuais.conteudo = excluded.conteudo AND manuais.versao = excluded.versao
                                          THEN manuais.atualizado_em ELSE excluded.atualizado_em END,
                     titulo = excluded.titulo, subtitulo = excluded.subtitulo, versao = excluded.versao,
                     modulo = excluded.modulo, menu = excluded.menu, conteudo = excluded.conteudo, tabelas = excluded.tabelas,
                     fontes = excluded.fontes, por = excluded.por, alterado_em = excluded.alterado_em""",
                (m["codigo"], m["titulo"], m.get("subtitulo", ""), m.get("versao", "1.0"), m["modulo"], menu,
                 json.dumps(m["secoes"], ensure_ascii=False), json.dumps(m.get("tabelas", [])),
                 json.dumps(m.get("fontes", []), ensure_ascii=False), m.get("por", ""),
                 # manual salvo pelo editor antes de existir alterado_em: a data dele é a da última gravação
                 m.get("alterado_em") or (m.get("atualizado_em") if m.get("editado") else None), m.get("atualizado_em")))


# ---------------- editor ----------------
PASTA_RASCUNHO = "_rascunho"  # prints colados antes de salvar: dados/imagens/_rascunho/<id>.<ext>
TAMANHO_MAXIMO_IMAGEM = 8 * 1024 * 1024
ASSINATURAS = {b"\x89PNG\r\n\x1a\n": "png", b"\xff\xd8\xff": "jpg", b"GIF87a": "gif", b"GIF89a": "gif"}
ARQUIVO_IMAGEM = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")


def extensao_imagem(dados: bytes) -> str | None:
    """Pelo conteúdo, não pelo nome nem pelo Content-Type: png, jpg, gif ou webp."""
    for assinatura, ext in ASSINATURAS.items():
        if dados.startswith(assinatura):
            return ext
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "webp"
    return None


def caminho_imagem(arquivo: str) -> Path | None:
    """Arquivo "<código>/<nome>" em dados/imagens (real) ou seed/imagens (exemplo); None se não existir ou for inválido."""
    if not ARQUIVO_IMAGEM.match(arquivo) or ".." in arquivo:
        return None
    for base in (config.DADOS / "imagens", config.SEED / "imagens"):
        arq = base / arquivo
        if arq.is_file():
            return arq
    return None


def guardar_rascunho(dados: bytes) -> str:
    ext = extensao_imagem(dados)
    pasta = config.DADOS / "imagens" / PASTA_RASCUNHO
    pasta.mkdir(parents=True, exist_ok=True)
    # rascunhos de edições abandonadas: somem depois de um dia
    limite = time.time() - 86400
    for velho in pasta.iterdir():
        if velho.is_file() and velho.stat().st_mtime < limite:
            velho.unlink(missing_ok=True)
    nome = f"{secrets.token_hex(8)}.{ext}"
    (pasta / nome).write_bytes(dados)
    return f"{PASTA_RASCUNHO}/{nome}"


def proximo_codigo(con: sqlite3.Connection, modulo: str) -> str:
    """PDV.001, PDV.002…: o maior número já usado com o prefixo do módulo, mais um (olha banco e arquivos)."""
    prefixo = modulo.upper()
    rx = re.compile(rf"^{re.escape(prefixo)}\.(\d+)$")
    codigos = [r[0] for r in con.execute("SELECT codigo FROM manuais")]
    codigos += [a.stem for a in (config.DADOS / "manuais").glob("*.json")]
    usados = [int(m.group(1)) for c in codigos if (m := rx.match(c))]
    return f"{prefixo}.{max(usados, default=0) + 1:03d}"


def proxima_versao(versao: str) -> str:
    """1.0 → 1.1; versões fora do padrão recomeçam em 1.1."""
    m = re.fullmatch(r"(\d+)\.(\d+)", versao or "")
    return f"{m.group(1)}.{int(m.group(2)) + 1}" if m else "1.1"


def _promover_imagens(codigo: str, secoes: list[dict]) -> None:
    """Move os prints do rascunho para dados/imagens/<código>/NN.ext e reescreve os blocos."""
    destino = config.DADOS / "imagens" / codigo
    usados = {p.stem for p in destino.glob("*")} if destino.exists() else set()
    n = max((int(s) for s in usados if s.isdigit()), default=0)
    for s in secoes:
        for b in s["blocos"]:
            if b["tipo"] != "imagem" or not b.get("arquivo", "").startswith(PASTA_RASCUNHO + "/"):
                continue
            origem = config.DADOS / "imagens" / b["arquivo"]
            n += 1
            nome = f"{n:02d}{origem.suffix}"
            destino.mkdir(parents=True, exist_ok=True)
            shutil.move(origem, destino / nome)
            b["arquivo"] = f"{codigo}/{nome}"


def _limpar(secoes: list[dict]) -> list[dict]:
    """Só os campos de cada tipo de bloco, com senhas mascaradas (mesmo formato dos manuais importados)."""
    saida = []
    for s in secoes:
        blocos = []
        for b in s["blocos"]:
            if b["tipo"] == "imagem":
                blocos.append({"tipo": "imagem", "arquivo": b.get("arquivo", ""), "legenda": mascarar(b.get("legenda", "").strip())})
            else:
                novo = {"tipo": b["tipo"], "texto": mascarar(b["texto"].strip() if b["tipo"] != "sql" else b["texto"].rstrip())}
                if b["tipo"] == "passo" and b.get("rotulo"):
                    novo["rotulo"] = b["rotulo"]
                blocos.append(novo)
        saida.append({"titulo": mascarar(s["titulo"].strip()), "blocos": blocos})
    return saida


def salvar(con: sqlite3.Connection, dados: dict, por: str, codigo: str | None = None) -> dict:
    """Cria (codigo=None) ou atualiza um manual vindo do editor. Grava o JSON em dados/manuais/ e o banco.

    `dados`: {titulo, subtitulo, modulo, menu, secoes, fontes} já validados pelo modelo da rota. Sem `fontes`
    (o editor comum), o manual mantém as que já tinha.
    """
    anterior = manual_completo(con, codigo) if codigo else None
    agora = config.agora_brasilia()
    codigo = codigo or proximo_codigo(con, dados["modulo"])
    secoes = _limpar(dados["secoes"])
    _promover_imagens(codigo, secoes)
    banco = con.execute("SELECT banco FROM modulos WHERE id = ?", (dados["modulo"],)).fetchone()["banco"]
    nomes = {r[0].lower() for r in con.execute("SELECT nome FROM tabelas WHERE banco = ?", (banco,))}
    blocos = [b for s in secoes for b in s["blocos"]]
    textos = "\n".join([s["titulo"] for s in secoes] + [b.get("texto", "") for b in blocos if b["tipo"] != "sql"])
    sqls = "\n".join(b["texto"] for b in blocos if b["tipo"] == "sql")
    manual = {
        "editado": True,  # o importador nunca sobrescreve um manual feito ou ajustado pela interface
        "codigo": codigo, "titulo": mascarar(dados["titulo"].strip()), "subtitulo": mascarar(dados.get("subtitulo", "").strip()),
        "versao": proxima_versao(anterior["versao"]) if anterior else "1.0",
        "modulo": dados["modulo"], "menu": dados.get("menu"),
        "fontes": dados.get("fontes") or (anterior["fontes"] if anterior else []),
        "tabelas": tabelas_citadas(textos, sqls, nomes),
        # alterado_em: hora de Brasília em que alguém salvou pelo editor; vai no rodapé do manual e do PDF
        "por": por, "atualizado_em": agora, "alterado_em": agora, "secoes": secoes,
    }
    pasta = config.DADOS / "manuais"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"{codigo}.json").write_text(json.dumps(manual, ensure_ascii=False, indent=2), encoding="utf-8")
    gravar_no_banco(con, manual, manual["menu"])
    con.commit()
    return manual
