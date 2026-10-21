import sqlite3
from pathlib import Path

from .config import DADOS, RAIZ  # noqa: F401  (RAIZ reexportado)

ARQUIVO = DADOS / "nexus.db"


def conectar() -> sqlite3.Connection:
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ARQUIVO, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def criar_schema(con: sqlite3.Connection) -> None:
    con.executescript((Path(__file__).parent / "schema.sql").read_text(encoding="utf-8"))


def caminho_menu(con: sqlite3.Connection, menu_id: str) -> list[dict]:
    """Do módulo até o item: [{id, titulo, atalho}, ...]."""
    trilha = []
    atual = menu_id
    while atual:
        r = con.execute("SELECT id, pai, titulo, atalho FROM menus WHERE id = ?", (atual,)).fetchone()
        if not r:
            break
        trilha.append({"id": r["id"], "titulo": r["titulo"], "atalho": r["atalho"]})
        atual = r["pai"]
    return list(reversed(trilha))
