"""Registro de alterações: quem criou, alterou, validou, descartou, moveu, importou ou excluiu o quê, e quando.

As rotas chamam `registrar` dentro da mesma transação da alteração (antes do commit), com uma frase clara em
`resumo` e o antes/depois em `detalhe`. O histórico só cresce: não há rota para editar nem apagar.
"""
import difflib
import json
import sqlite3

from .. import config
from ..db import caminho_menu
from . import relacoes

ACOES = ("criou", "alterou", "excluiu", "validou", "descartou", "importou", "moveu")
AREAS = {
    "manual": "Manual",
    "trecho": "Trecho do manual",
    "ligacao": "Ligação entre colunas",
    "informativo": "Informativo de incidentes",
    "diagrama": "Diagrama",
    "tela": "Tabelas da tela",
    "dicionario": "Dicionário de dados",
}
TIPO_BLOCO = {"passo": "passo", "texto": "parágrafo", "subtitulo": "subtítulo", "obs": "observação", "nota": "nota",
              "sql": "SQL", "imagem": "imagem"}


def registrar(con: sqlite3.Connection, por: str, acao: str, area: str, resumo: str, *, alvo: str = "",
              modulo: str = "", detalhe: dict | list | None = None) -> None:
    """Uma linha no histórico. Não faz commit: entra junto com a alteração que descreve."""
    assert acao in ACOES and area in AREAS, (acao, area)
    con.execute("INSERT INTO registro_alteracoes (em, por, acao, area, modulo, alvo, resumo, detalhe) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (config.agora_brasilia(), por or "", acao, area, modulo or "", alvo[:500], resumo[:2000],
                 json.dumps(detalhe, ensure_ascii=False) if detalhe is not None else None))


def listar(con: sqlite3.Connection, *, por: str | None = None, area: str | None = None, acao: str | None = None,
           modulo: str | None = None, busca: str | None = None, antes: int | None = None, limite: int = 100) -> dict:
    """Mais recentes primeiro. `antes` = id da última linha da página anterior (paginação por cursor)."""
    sql, args = "SELECT * FROM registro_alteracoes WHERE 1 = 1", []
    for campo, valor in (("por", por), ("area", area), ("acao", acao), ("modulo", modulo)):
        if valor:
            sql += f" AND {campo} = ?"
            args.append(valor)
    if busca:
        sql += " AND (resumo LIKE ? OR alvo LIKE ? OR detalhe LIKE ?)"
        args += [f"%{busca}%"] * 3
    if antes:
        sql += " AND id < ?"
        args.append(antes)
    linhas = con.execute(sql + " ORDER BY id DESC LIMIT ?", (*args, limite + 1)).fetchall()
    itens = [{**dict(r), "detalhe": json.loads(r["detalhe"]) if r["detalhe"] else None} for r in linhas[:limite]]
    return {"itens": itens, "mais": len(linhas) > limite}


def pessoas(con: sqlite3.Connection) -> list[str]:
    return [r[0] for r in con.execute("SELECT DISTINCT por FROM registro_alteracoes WHERE por <> '' ORDER BY por")]


# ---------------- frases ----------------
def relacao(con: sqlite3.Connection, banco: str, rel_id: str) -> str:
    """'vendas.id_cliente → clientes.id_cliente' (relação composta: pares separados por vírgula)."""
    r = next(iter(relacoes.listar(con, banco, " AND r.id = ?", (rel_id,))), None)
    if not r:
        return rel_id
    return ", ".join(f"{r['origem']}.{a} → {r['destino']}.{b}" for a, b in r["colunas"])


def tela_da_chave(con: sqlite3.Connection, modulo: str, chave: str) -> str:
    """O diagrama é guardado pela tela (id do menu) ou, no formato antigo, pelas tabelas dela; para quem lê, vale o
    caminho da tela ('Vendas › Devoluções')."""
    if con.execute("SELECT 1 FROM menus WHERE id = ? AND modulo = ?", (chave, modulo)).fetchone():
        return "diagrama da tela " + " › ".join(p["titulo"] for p in caminho_menu(con, chave))
    tabelas = set(filter(None, chave.split(",")))
    for r in con.execute("""SELECT mt.menu, group_concat(mt.tabela, ',') AS tabelas FROM menu_tabelas mt
                            JOIN menus m ON m.id = mt.menu WHERE m.modulo = ? GROUP BY mt.menu""", (modulo,)):
        if set(r["tabelas"].split(",")) == tabelas:
            return "diagrama da tela " + " › ".join(p["titulo"] for p in caminho_menu(con, r["menu"]))
    return "diagrama das tabelas " + ", ".join(sorted(tabelas))


def caminho_da_tela(con: sqlite3.Connection, menu: str | None) -> str:
    return " › ".join(p["titulo"] for p in caminho_menu(con, menu)) if menu else "(sem tela)"


def _corta(texto: str, n: int = 140) -> str:
    texto = " ".join((texto or "").split())
    return texto if len(texto) <= n else texto[: n - 1] + "…"


def _bloco(b: dict) -> str:
    return f"{TIPO_BLOCO.get(b.get('tipo'), b.get('tipo'))} “{_corta(b.get('texto') or b.get('arquivo') or '')}”"


def mudancas_manual(con: sqlite3.Connection, antes: dict | None, depois: dict) -> list[str]:
    """O que mudou de uma versão do manual para a outra, em frases ('seção 2 “Passo a passo”: alterou o passo …')."""
    if not antes:
        n = sum(len(s["blocos"]) for s in depois["secoes"])
        return [f"criou com {len(depois['secoes'])} seção(ões) e {n} bloco(s)"]
    saida = []
    for campo, nome in (("titulo", "título"), ("subtitulo", "subtítulo"), ("tipo", "tipo")):
        if (antes.get(campo) or "") != (depois.get(campo) or ""):
            saida.append(f"{nome}: “{_corta(antes.get(campo) or '')}” → “{_corta(depois.get(campo) or '')}”")
    if antes.get("menu") != depois.get("menu"):
        saida.append(f"tela: {caminho_da_tela(con, antes.get('menu'))} → {caminho_da_tela(con, depois.get('menu'))}")
    if list(antes.get("fontes") or []) != list(depois.get("fontes") or []):
        saida.append(f"documentos de origem: {', '.join(antes.get('fontes') or []) or '(nenhum)'} → {', '.join(depois.get('fontes') or []) or '(nenhum)'}")

    # seções e blocos: alinhados pelo conteúdo (difflib), para "incluiu um passo no meio" não virar "alterou todos"
    def chave_secao(s):
        return s["titulo"].strip().lower()
    sa, sd = antes["secoes"], depois["secoes"]
    for op, a1, a2, d1, d2 in difflib.SequenceMatcher(a=[chave_secao(s) for s in sa], b=[chave_secao(s) for s in sd], autojunk=False).get_opcodes():
        if op == "equal" or (op == "replace" and a2 - a1 == d2 - d1):
            for ia, idd in zip(range(a1, a2), range(d1, d2)):
                if op == "replace":
                    saida.append(f"seção {idd + 1}: título “{sa[ia]['titulo']}” → “{sd[idd]['titulo']}”")
                saida += _mudancas_blocos(f"seção {idd + 1} “{sd[idd]['titulo']}”", sa[ia]["blocos"], sd[idd]["blocos"])
            continue
        for ia in range(a1, a2):
            saida.append(f"excluiu a seção “{sa[ia]['titulo']}” ({len(sa[ia]['blocos'])} bloco(s))")
        for idd in range(d1, d2):
            saida.append(f"incluiu a seção {idd + 1} “{sd[idd]['titulo']}” ({len(sd[idd]['blocos'])} bloco(s))")
    return saida


def _mudancas_blocos(onde: str, ba: list[dict], bd: list[dict]) -> list[str]:
    def chave(b):
        return (b.get("tipo"), b.get("texto") or "", b.get("arquivo") or "", b.get("legenda") or "")
    saida = []
    for op, a1, a2, d1, d2 in difflib.SequenceMatcher(a=[chave(b) for b in ba], b=[chave(b) for b in bd], autojunk=False).get_opcodes():
        if op == "equal":
            continue
        pares = list(zip(range(a1, a2), range(d1, d2))) if op == "replace" else []
        for ia, idd in pares:
            saida.append(f"{onde}: alterou o {TIPO_BLOCO.get(bd[idd].get('tipo'), 'bloco')} {idd + 1}: "
                         f"“{_corta(ba[ia].get('texto') or ba[ia].get('arquivo') or '')}” → “{_corta(bd[idd].get('texto') or bd[idd].get('arquivo') or '')}”")
        for ia in range(a1 + len(pares), a2):
            saida.append(f"{onde}: excluiu o {_bloco(ba[ia])}")
        for idd in range(d1 + len(pares), d2):
            saida.append(f"{onde}: incluiu o {_bloco(bd[idd])} (posição {idd + 1})")
    return saida
