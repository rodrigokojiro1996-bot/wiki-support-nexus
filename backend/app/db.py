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


MIGRACOES = Path(__file__).parent / "migrations"


def migracoes() -> list[tuple[int, Path]]:
    """[(número, arquivo)] de migrations/NNN_nome.sql, em ordem."""
    return sorted((int(a.name.split("_", 1)[0]), a) for a in MIGRACOES.glob("[0-9][0-9][0-9]_*.sql"))


def versao_atual(con: sqlite3.Connection) -> int:
    tem = lambda tabela: con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (tabela,)).fetchone()  # noqa: E731
    if tem("schema_version"):
        return con.execute("SELECT COALESCE(MAX(versao), 0) FROM schema_version").fetchone()[0]
    if not tem("modulos"):
        return 0  # banco novo
    # banco criado pelo schema.sql da 0.1.0 (antes das migrações): reconhece a versão pela estrutura
    return 2 if any(c["name"] == "fontes" for c in con.execute("PRAGMA table_info(manuais)")) else 1


def migrar(con: sqlite3.Connection) -> list[str]:
    """Aplica, em ordem, as migrações que faltam, cada uma numa transação. Devolve os nomes aplicados."""
    atual = versao_atual(con)
    con.executescript("""CREATE TABLE IF NOT EXISTS schema_version (
                           versao INTEGER PRIMARY KEY, nome TEXT NOT NULL,
                           em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')))""")
    # banco antigo sem schema_version: registra as versões já presentes na estrutura
    con.executemany("INSERT OR IGNORE INTO schema_version (versao, nome) VALUES (?, ?)",
                    [(n, a.stem) for n, a in migracoes() if n <= atual])
    con.commit()
    aplicadas = []
    for n, arq in migracoes():
        if n <= atual:
            continue
        try:
            con.executescript("BEGIN;\n" + arq.read_text(encoding="utf-8")
                              + f"\nINSERT INTO schema_version (versao, nome) VALUES ({n}, '{arq.stem}');\nCOMMIT;")
        except Exception:
            con.rollback()
            raise
        aplicadas.append(arq.stem)
    return aplicadas


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
