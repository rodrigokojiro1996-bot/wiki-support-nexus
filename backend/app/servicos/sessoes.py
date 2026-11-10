"""Sessões do login Microsoft e tentativas de login em andamento, no SQLite.

O navegador guarda um token aleatório num cookie HttpOnly; o banco guarda só o SHA-256 dele. Assim, uma cópia do
banco não traz sessões prontas para usar, e sair (ou apagar a linha) encerra a sessão na hora.
"""
import hashlib
import secrets
import sqlite3
import time
from dataclasses import dataclass

from .entra import Tentativa

COOKIE = "nexus_sessao"
DURACAO_S = 12 * 3600      # um dia de trabalho; depois, um clique em "Entrar" (a Microsoft já lembra a conta)
LOGIN_PENDENTE_S = 10 * 60  # tempo para ir ao Entra e voltar


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _agora(agora: int | None) -> int:
    return int(time.time()) if agora is None else agora


def criar(con: sqlite3.Connection, oid: str, email: str, nome: str, duracao: int = DURACAO_S,
          agora: int | None = None) -> str:
    """Abre uma sessão e devolve o token do cookie (o único lugar em que ele aparece)."""
    agora = _agora(agora)
    token = secrets.token_urlsafe(32)
    con.execute("DELETE FROM sessoes WHERE expira_em <= ?", (agora,))
    con.execute("INSERT INTO sessoes (token_hash, oid, email, nome, criada_em, expira_em) VALUES (?, ?, ?, ?, ?, ?)",
                (_hash(token), oid, email, nome, agora, agora + duracao))
    con.commit()
    return token


def ler(con: sqlite3.Connection, token: str | None, agora: int | None = None) -> dict | None:
    """{oid, email, nome} da sessão válida; None se não existe ou venceu (a vencida é apagada)."""
    if not token:
        return None
    agora = _agora(agora)
    r = con.execute("SELECT oid, email, nome, expira_em FROM sessoes WHERE token_hash = ?", (_hash(token),)).fetchone()
    if not r:
        return None
    if r["expira_em"] <= agora:
        encerrar(con, token)
        return None
    return {"oid": r["oid"], "email": r["email"], "nome": r["nome"]}


def encerrar(con: sqlite3.Connection, token: str | None) -> None:
    if token:
        con.execute("DELETE FROM sessoes WHERE token_hash = ?", (_hash(token),))
        con.commit()


# ---------------- tentativa de login em andamento ----------------
@dataclass(frozen=True)
class LoginPendente:
    tentativa: Tentativa
    voltar: str  # caminho interno para onde ir depois de entrar


def guardar_login(con: sqlite3.Connection, tentativa: Tentativa, voltar: str, agora: int | None = None) -> str:
    """Guarda a tentativa e devolve a chave do cookie que a amarra a este navegador."""
    agora = _agora(agora)
    chave = secrets.token_urlsafe(32)
    con.execute("DELETE FROM logins_pendentes WHERE criado_em <= ?", (agora - LOGIN_PENDENTE_S,))
    con.execute("INSERT INTO logins_pendentes (chave_hash, state, nonce, verificador, voltar, criado_em) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (_hash(chave), tentativa.state, tentativa.nonce, tentativa.verificador, voltar, agora))
    con.commit()
    return chave


def consumir_login(con: sqlite3.Connection, chave: str | None, agora: int | None = None) -> LoginPendente | None:
    """Tira a tentativa do banco (uso único, numa operação só) e devolve-a se ainda estiver no prazo."""
    if not chave:
        return None
    agora = _agora(agora)
    r = con.execute("DELETE FROM logins_pendentes WHERE chave_hash = ? "
                    "RETURNING state, nonce, verificador, voltar, criado_em", (_hash(chave),)).fetchone()
    con.commit()
    if not r or agora - r["criado_em"] >= LOGIN_PENDENTE_S:
        return None
    return LoginPendente(Tentativa(r["state"], r["nonce"], r["verificador"]), r["voltar"])
