"""Relações do catálogo com o estado decidido pela equipe, e as ligadas pela equipe no diagrama."""
import json
import sqlite3

# catálogo (fk/sug, regravadas a cada importação) + ligadas pela equipe; se o catálogo passar a ter o mesmo id,
# vale a do catálogo (a decisão "documentada" em relacao_status continua valendo para ela)
TODAS = """SELECT banco, id, origem, destino, colunas, tipo, regra, motivo FROM relacoes
           UNION ALL
           SELECT e.banco, e.id, e.origem, e.destino, e.colunas, 'equipe', NULL, NULLIF(e.observacao, '') FROM relacoes_equipe e
           WHERE NOT EXISTS (SELECT 1 FROM relacoes c WHERE c.banco = e.banco AND c.id = e.id)"""

SQL_RELACOES = f"""SELECT r.*, s.status, s.por, s.em AS status_em FROM ({TODAS}) r
                   LEFT JOIN relacao_status s ON s.banco = r.banco AND s.id = r.id
                   WHERE r.banco = ?"""


class LigacaoInvalida(ValueError):
    """Tabela ou coluna inexistente, ou a mesma coluna nas duas pontas."""


class LigacaoExistente(ValueError):
    """As colunas já estão ligadas (pelo banco ou pela equipe)."""


def relacao_dict(r: sqlite3.Row) -> dict:
    estado = "confirmada" if r["tipo"] == "fk" else (r["status"] or "sugerida")
    return {"id": r["id"], "origem": r["origem"], "destino": r["destino"], "colunas": json.loads(r["colunas"]),
            "estado": estado, "regra": r["regra"], "motivo": r["motivo"], "equipe": r["tipo"] == "equipe",
            "por": r["por"] or None, "em": r["status_em"]}  # quem validou/descartou e quando


def listar(con: sqlite3.Connection, banco: str, filtro: str = "", args: tuple = ()) -> list[dict]:
    """Relações do banco; `filtro` é um trecho SQL extra (ex.: " AND r.origem = ?")."""
    return [relacao_dict(r) for r in con.execute(SQL_RELACOES + filtro, (banco, *args))]


def existe(con: sqlite3.Connection, banco: str, rel_id: str) -> sqlite3.Row | None:
    """A relação (do catálogo ou da equipe) com o tipo: fk, sug ou equipe."""
    return con.execute(f"SELECT tipo FROM ({TODAS}) WHERE banco = ? AND id = ?", (banco, rel_id)).fetchone()


def _coluna_existe(con: sqlite3.Connection, banco: str, tabela: str, coluna: str) -> bool:
    return con.execute("SELECT 1 FROM colunas WHERE banco = ? AND tabela = ? AND nome = ?", (banco, tabela, coluna)).fetchone() is not None


def ligar(con: sqlite3.Connection, banco: str, origem: str, col_origem: str, destino: str, col_destino: str,
          por: str, observacao: str = "") -> dict:
    """Liga origem.col_origem (lado N) a destino.col_destino (lado 1) como relação documentada pela equipe.
    Se o catálogo já sugeria essa ligação, só valida a sugestão em vez de criar outra."""
    for t, c in ((origem, col_origem), (destino, col_destino)):
        if not _coluna_existe(con, banco, t, c):
            raise LigacaoInvalida(f"A coluna {t}.{c} não existe em {banco}")
    if origem == destino and col_origem == col_destino:
        raise LigacaoInvalida("Escolha duas colunas diferentes")
    par = [[col_origem, col_destino]]
    # a mesma ligação já existe, em qualquer sentido?
    for r in con.execute(f"SELECT id, tipo, origem, destino, colunas FROM ({TODAS}) WHERE banco = ? AND "
                         "((origem = ? AND destino = ?) OR (origem = ? AND destino = ?))", (banco, origem, destino, destino, origem)):
        pares = json.loads(r["colunas"])
        mesmo_sentido = r["origem"] == origem and r["destino"] == destino and [col_origem, col_destino] in pares
        invertida = r["origem"] == destino and r["destino"] == origem and [col_destino, col_origem] in pares
        if mesmo_sentido or invertida:
            if r["tipo"] == "sug":
                _documentar(con, banco, r["id"], por, observacao)
                return listar(con, banco, " AND r.id = ?", (r["id"],))[0]
            raise LigacaoExistente("Essas colunas já estão ligadas" + (" pelo banco" if r["tipo"] == "fk" else ""))
    rel_id = f"{origem}.{col_origem}>{destino}"
    if existe(con, banco, rel_id):  # outra coluna de destino com a mesma origem (raro): id próprio
        rel_id = f"{origem}.{col_origem}>{destino}.{col_destino}"
    con.execute("INSERT INTO relacoes_equipe (banco, id, origem, destino, colunas, observacao, por) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (banco, rel_id, origem, destino, json.dumps(par), observacao, por))
    _documentar(con, banco, rel_id, por, observacao)
    return listar(con, banco, " AND r.id = ?", (rel_id,))[0]


def _documentar(con: sqlite3.Connection, banco: str, rel_id: str, por: str, observacao: str) -> None:
    con.execute("""INSERT INTO relacao_status (banco, id, status, observacao, por) VALUES (?, ?, 'documentada', ?, ?)
                   ON CONFLICT(banco, id) DO UPDATE SET status = excluded.status, observacao = excluded.observacao,
                   por = excluded.por, em = datetime('now', 'localtime')""", (banco, rel_id, observacao, por))
    con.commit()
