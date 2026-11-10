"""Dependências comuns aos routers."""
import sqlite3
from urllib.parse import unquote

from fastapi import Header, HTTPException, Request

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


def usuario(request: Request, x_usuario: str = Header("", alias="X-Usuario")) -> str:
    """Autor das alterações. Com o login Microsoft ligado, quem entrou (o cabeçalho é ignorado); desligado, o nome
    que a pessoa informou na interface (URL-encoded)."""
    sessao = getattr(request.state, "sessao", None)
    if sessao:
        return sessao["nome"]
    return unquote(x_usuario).strip()[:80]
