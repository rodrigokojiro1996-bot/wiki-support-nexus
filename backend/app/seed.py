"""Cria o banco da Wiki e carrega: módulos, catálogo do coletor, menus do sistema e manuais.

Uso (dentro de backend/):
    python -m app.seed

Pode rodar de novo a qualquer momento: atualiza catálogo, menus e manuais sem apagar
as validações de relação nem os vínculos menu ↔ tabela feitos pela equipe.

Sistema real x exemplo: o versionado é só o exemplo (coletor/exemplo, seed/menus_*.json, seed/manuais). Para o
sistema real, fora do git: modulos.json, coletor/saida/<banco>/catalogo.json e menus_reais/menus_<módulo>.json (ou
dados/menus_<módulo>.json), que substitui o seed/menus_<módulo>.json de mesmo nome. Com o catálogo real, os manuais de exemplo do módulo saem.
"""
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from . import config
from .config import PROJETO, SEED, modulos
from .db import conectar, migrar
from .servicos.manuais import gravar_no_banco


def slug(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def arquivo_catalogo(banco: str) -> Path:
    arq = PROJETO / "coletor" / "saida" / banco / "catalogo.json"
    if not arq.exists():  # sem coleta real, usa o banco de exemplo versionado
        arq = PROJETO / "coletor" / "exemplo" / banco / "catalogo.json"
    return arq


def catalogo_de_exemplo(banco: str | None) -> bool:
    """O módulo mostra o sistema de exemplo versionado (e não um banco real coletado)?"""
    return bool(banco) and arquivo_catalogo(banco).resolve().is_relative_to((PROJETO / "coletor" / "exemplo").resolve())


def arquivos_de_menus() -> list[Path]:
    """seed/menus_<módulo>.json (exemplo), substituído pelo de mesmo nome em dados/ ou em menus_reais/ (sistema real)."""
    por_nome = {arq.name: arq for arq in SEED.glob("menus_*.json")}
    for pasta in (config.DADOS, config.MENUS_REAIS):
        por_nome.update({arq.name: arq for arq in pasta.glob("menus_*.json")})
    return [por_nome[n] for n in sorted(por_nome)]


def importar_catalogo(con, banco: str) -> None:
    arq = arquivo_catalogo(banco)
    if not arq.exists():
        print(f"  catálogo não encontrado ({arq}); rode o coletor antes")
        return
    cat = json.loads(arq.read_text(encoding="utf-8"))
    for t in ("relacoes", "colunas", "tabelas"):
        con.execute(f"DELETE FROM {t} WHERE banco = ?", (banco,))
    for nome, t in cat["tables"].items():
        linhas = int(t["rows"]) if str(t.get("rows", "")).isdigit() else None
        con.execute("INSERT INTO tabelas (banco, nome, engine, linhas) VALUES (?, ?, ?, ?)", (banco, nome, t.get("engine"), linhas))
        con.executemany("INSERT INTO colunas (banco, tabela, nome, tipo, pk, ordem) VALUES (?, ?, ?, ?, ?, ?)",
                        [(banco, nome, c["name"], c["type"], int(c["pk"]), i) for i, c in enumerate(t["cols"])])
    con.executemany("INSERT INTO relacoes (banco, id, origem, destino, colunas, tipo, regra, motivo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [(banco, e["id"], e["source"], e["target"], json.dumps(e["cols"]), e["kind"], e.get("regra"), e.get("reason")) for e in cat["edges"]])
    resumo = f"{len(cat['tables'])} tabelas, {len(cat['edges'])} relações"
    con.execute("INSERT OR REPLACE INTO importacoes (banco, em, resumo) VALUES (?, ?, ?)", (banco, cat.get("importadoEm") or datetime.now().strftime("%d/%m/%Y %H:%M"), resumo))
    print(f"  catálogo {banco}: {resumo}")


def importar_menus(con, arquivo: Path) -> None:
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    modulo = dados["modulo"]
    existentes = {r["tabela"] for r in con.execute("SELECT nome AS tabela FROM tabelas WHERE banco = (SELECT banco FROM modulos WHERE id = ?)", (modulo,))}
    vistos = []

    def gravar(item, pai, ordem):
        mid = f"{pai}.{slug(item['titulo'])}" if pai else f"{modulo}.{slug(item['titulo'])}"
        con.execute("""INSERT INTO menus (id, modulo, pai, titulo, atalho, tela_codigo, desabilitado, submenu, ordem) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(id) DO UPDATE SET pai = excluded.pai, titulo = excluded.titulo, atalho = excluded.atalho,
                       tela_codigo = excluded.tela_codigo, desabilitado = excluded.desabilitado, submenu = excluded.submenu, ordem = excluded.ordem""",
                    (mid, modulo, pai, item["titulo"], item.get("atalho"), item.get("tela_codigo"), int(item.get("desabilitado", False)),
                     int(item.get("submenu", False)), ordem))
        vistos.append(mid)
        for t in item.get("tabelas", []):
            if t in existentes:
                con.execute("INSERT OR IGNORE INTO menu_tabelas (menu, tabela, origem) VALUES (?, ?, 'sugerido')", (mid, t))
        for i, filho in enumerate(item.get("itens", [])):
            gravar(filho, mid, i)

    for i, m in enumerate(dados["menus"]):
        gravar(m, None, i)
    # itens que saíram do arquivo (ex.: troca do exemplo pelo sistema real): manuais ficam sem tela, vínculos saem
    sobra = [r["id"] for r in con.execute("SELECT id FROM menus WHERE modulo = ?", (modulo,)) if r["id"] not in set(vistos)]
    if sobra:
        marcas = ",".join("?" * len(sobra))
        con.execute(f"UPDATE manuais SET menu = NULL WHERE menu IN ({marcas})", sobra)
        for mid in sorted(sobra, key=lambda x: x.count("."), reverse=True):  # filhos antes dos pais
            con.execute("DELETE FROM menus WHERE id = ?", (mid,))  # menu_tabelas sai junto (ON DELETE CASCADE)
        print(f"  menus {modulo}: {len(sobra)} itens que não estão mais no arquivo foram removidos")
    print(f"  menus {modulo}: {len(vistos)} itens")


def arquivos_de_manuais() -> list[Path]:
    """Exemplos de seed/manuais e conteúdo real de dados/manuais; com o mesmo código, vale o de dados/."""
    por_codigo = {}
    for pasta in (SEED / "manuais", config.DADOS / "manuais"):
        for arq in sorted(pasta.glob("*.json")):
            por_codigo[arq.stem] = arq
    return [por_codigo[c] for c in sorted(por_codigo)]


def importar_manuais(con) -> None:
    menus = {r["id"] for r in con.execute("SELECT id FROM menus")}
    # manuais de exemplo (seed/manuais) descrevem o sistema fictício: só entram nos módulos que ainda o mostram
    exemplo = {r["id"] for r in con.execute("SELECT id, banco FROM modulos") if catalogo_de_exemplo(r["banco"])}
    n = 0
    for arq in arquivos_de_manuais():
        m = json.loads(arq.read_text(encoding="utf-8"))
        if arq.parent == SEED / "manuais" and m["modulo"] not in exemplo:
            con.execute("DELETE FROM manuais WHERE codigo = ?", (m["codigo"],))
            continue
        menu = m.get("menu") if m.get("menu") in menus else None
        if m.get("menu") and not menu:
            print(f"  aviso: {m['codigo']} aponta para o menu inexistente {m['menu']}")
        gravar_no_banco(con, m, menu)
        n += 1
    print(f"  manuais: {n}")


def main():
    con = conectar()
    for m in migrar(con):
        print(f"  migração aplicada: {m}")
    mods = modulos()
    con.executemany("INSERT INTO modulos (id, nome, banco) VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET nome = excluded.nome, banco = excluded.banco", mods)
    for _, _, banco in mods:
        if banco:
            importar_catalogo(con, banco)
    for arq in arquivos_de_menus():
        importar_menus(con, arq)
    importar_manuais(con)
    con.commit()
    con.close()
    print("Pronto.")


if __name__ == "__main__":
    main()
