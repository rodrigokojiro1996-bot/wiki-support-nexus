"""Dicionário de dados: descrição das tabelas e das colunas (o balão do diagrama).

A equipe confere a planilha gerada por coletor/rascunho_descricoes.py e a devolve; `importar` grava só as linhas
com Conferido = S. Uma coluna sem exceção usa a descrição do nome, que vale para todas as tabelas.
"""
import io
import sqlite3

from openpyxl import load_workbook

# cabeçalhos da planilha (a ordem das colunas pode mudar; o nome não)
DESCRICAO, CONFERIDO = "Descrição (edite aqui)", "Conferido (S/N)"


class PlanilhaInvalida(ValueError):
    pass


def _linhas(wb, aba: str, obrigatorias: list[str]):
    """Linhas conferidas de uma aba, como dicts pelos cabeçalhos; a aba é opcional (planilha mandada por partes)."""
    if aba not in wb.sheetnames:
        return [], 0
    ws = wb[aba]
    linhas = ws.iter_rows(values_only=True)
    cab = [str(c or "").strip() for c in next(linhas, ())]
    faltam = [c for c in [*obrigatorias, DESCRICAO, CONFERIDO] if c not in cab]
    if faltam:
        raise PlanilhaInvalida(f"A aba {aba} não tem a coluna {', '.join(faltam)}")
    conferidas, ignoradas = [], 0
    for valores in linhas:
        d = {c: ("" if v is None else str(v).strip()) for c, v in zip(cab, valores)}
        if not any(d.values()):
            continue
        if d[CONFERIDO].upper() == "S" and d[DESCRICAO]:
            conferidas.append(d)
        else:
            ignoradas += 1
    return conferidas, ignoradas


def importar(con: sqlite3.Connection, dados: bytes, por: str) -> dict:
    """Grava as descrições conferidas da planilha. Devolve a contagem por aba e o que ficou de fora."""
    try:
        wb = load_workbook(io.BytesIO(dados), read_only=True, data_only=True)
    except Exception as e:  # zip corrompido, outro formato...
        raise PlanilhaInvalida("O arquivo não é uma planilha do Excel (.xlsx)") from e
    modulos = {r["id"].upper(): r["id"] for r in con.execute("SELECT id FROM modulos")}
    tabelas, ign_t = _linhas(wb, "Tabelas", ["Módulo", "Tabela"])
    colunas, ign_c = _linhas(wb, "Colunas", ["Coluna"])
    excecoes, ign_e = _linhas(wb, "Exceções", ["Módulo", "Tabela", "Coluna"])
    gravar, fora = [], []
    for d in tabelas:
        modulo = modulos.get(d["Módulo"].upper())
        if modulo and d["Tabela"]:
            gravar.append((modulo, d["Tabela"], "", d[DESCRICAO]))
        else:
            fora.append(f"Tabelas: módulo {d['Módulo'] or '(vazio)'} não existe ou tabela em branco ({d['Tabela']})")
    for d in colunas:
        gravar.append(("", "", d["Coluna"].lower(), d[DESCRICAO]))
    for d in excecoes:
        modulo = modulos.get(d["Módulo"].upper())
        if modulo and d["Tabela"] and d["Coluna"]:
            gravar.append((modulo, d["Tabela"], d["Coluna"].lower(), d[DESCRICAO]))
        else:
            fora.append(f"Exceções: linha incompleta ou módulo que não existe ({d['Tabela']}.{d['Coluna']})")
    with con:
        con.executemany("""INSERT INTO descricoes (modulo, tabela, coluna, texto, por) VALUES (?, ?, ?, ?, ?)
                           ON CONFLICT (modulo, tabela, coluna) DO UPDATE SET texto = excluded.texto, por = excluded.por,
                           em = datetime('now', 'localtime')""", [(*g, por) for g in gravar])
    return {"tabelas": sum(1 for g in gravar if not g[2]), "colunas": sum(1 for g in gravar if not g[0]),
            "excecoes": sum(1 for g in gravar if g[0] and g[2]), "nao_conferidas": ign_t + ign_c + ign_e, "fora": fora[:50]}


def das_tabelas(con: sqlite3.Connection, modulo: str) -> dict[str, str]:
    return {r["tabela"]: r["texto"] for r in con.execute("SELECT tabela, texto FROM descricoes WHERE modulo = ? AND coluna = ''", (modulo,))}


def das_colunas(con: sqlite3.Connection, modulo: str, banco: str, tabelas: list[str]) -> dict[tuple[str, str], str]:
    """{(tabela, coluna): texto} das colunas dessas tabelas: a exceção da tabela ganha da descrição do nome."""
    if not tabelas:
        return {}
    marca = ",".join("?" * len(tabelas))
    sql = f"""SELECT c.tabela, c.nome, COALESCE(e.texto, g.texto) AS texto
              FROM colunas c
              LEFT JOIN descricoes e ON e.modulo = ? AND e.tabela = c.tabela AND e.coluna = lower(c.nome)
              LEFT JOIN descricoes g ON g.modulo = '' AND g.tabela = '' AND g.coluna = lower(c.nome)
              WHERE c.banco = ? AND c.tabela IN ({marca}) AND COALESCE(e.texto, g.texto) IS NOT NULL"""
    return {(r["tabela"], r["nome"]): r["texto"] for r in con.execute(sql, (modulo, banco, *tabelas))}


if __name__ == "__main__":
    # dentro do servidor, sem passar pelo login: python -m app.servicos.descricoes planilha.xlsx "Quem conferiu"
    import json
    import sys
    from pathlib import Path

    from ..db import conectar, migrar

    con = conectar()
    migrar(con)
    print(json.dumps(importar(con, Path(sys.argv[1]).read_bytes(), sys.argv[2] if len(sys.argv) > 2 else ""), ensure_ascii=False))
