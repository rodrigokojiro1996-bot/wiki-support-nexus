"""Dependências comuns aos routers."""
import sqlite3
from urllib.parse import unquote

from fastapi import Header, HTTPException

from ..db import conectar


def db():
    con = conectar()
    try:
        yield con
    finally:
        con.close()


def banco_do_modulo(con: sqlite3.Connection, modulo: str) -> str | None:
    r = con.execute("SELECT banco FROM modulos WHERE id = ?", (modulo,)).fetchone()
    if not r:
        raise HTTPException(404, f"Módulo {modulo} não existe")
    return r["banco"]


def usuario(x_usuario: str = Header("", alias="X-Usuario")) -> str:
    """Autor das alterações. Até ter login, é o nome que a pessoa informou na interface (URL-encoded)."""
    return unquote(x_usuario).strip()[:80]
