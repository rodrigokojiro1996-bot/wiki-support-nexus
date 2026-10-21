import json
import sqlite3

from ..db import caminho_menu


def manual_completo(con: sqlite3.Connection, codigo: str) -> dict | None:
    m = con.execute("SELECT m.*, mo.nome AS modulo_nome FROM manuais m JOIN modulos mo ON mo.id = m.modulo WHERE codigo = ?", (codigo,)).fetchone()
    if not m:
        return None
    return {**dict(m), "secoes": json.loads(m["conteudo"]), "tabelas": json.loads(m["tabelas"]), "conteudo": None,
            "fontes": json.loads(m["fontes"] or "[]"),
            "caminho": caminho_menu(con, m["menu"]) if m["menu"] else []}
