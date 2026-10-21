"""Relações do catálogo com o estado decidido pela equipe."""
import json
import sqlite3

SQL_RELACOES = """SELECT r.*, s.status, s.por, s.em AS status_em FROM relacoes r
                  LEFT JOIN relacao_status s ON s.banco = r.banco AND s.id = r.id
                  WHERE r.banco = ?"""


def relacao_dict(r: sqlite3.Row) -> dict:
    estado = "confirmada" if r["tipo"] == "fk" else (r["status"] or "sugerida")
    return {"id": r["id"], "origem": r["origem"], "destino": r["destino"], "colunas": json.loads(r["colunas"]),
            "estado": estado, "regra": r["regra"], "motivo": r["motivo"],
            "por": r["por"] or None, "em": r["status_em"]}  # quem validou/descartou e quando


def listar(con: sqlite3.Connection, banco: str, filtro: str = "", args: tuple = ()) -> list[dict]:
    """Relações do banco; `filtro` é um trecho SQL extra (ex.: " AND r.origem = ?")."""
    return [relacao_dict(r) for r in con.execute(SQL_RELACOES + filtro, (banco, *args))]
