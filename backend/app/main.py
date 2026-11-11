"""Support Nexus · API.

Rodar (dentro de backend/):
    .venv\\Scripts\\uvicorn app.main:app --reload --port 8010
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .config import ORIGENS_CORS, VERSAO
from .db import conectar, migrar
from .metricas import MetricasHTTP
from .rotas import auth, catalogo, descricoes, frontend, manuais, menus, metricas, modulos, saude, trechos
from .servicos import entra, sessoes


@asynccontextmanager
async def ciclo(_app):
    # login ligado com meia configuração: não sobe, e o log diz o que falta (melhor que um erro no meio do login)
    if entra.login_ligado() and (problemas := entra.problemas_config()):
        raise RuntimeError("Login Microsoft ligado (MICROSOFT_AUTH_ENABLED=true), mas a configuração está "
                           f"incompleta: {'; '.join(problemas)}. Corrija o .env e reinicie, ou desligue com "
                           "MICROSOFT_AUTH_ENABLED=false.")
    # código novo com banco antigo: aplica as migrações que faltam antes de atender
    con = conectar()
    try:
        migrar(con)
    finally:
        con.close()
    yield


app = FastAPI(title="Support Nexus", version=VERSAO, lifespan=ciclo)

# rotas da API que respondem sem sessão: monitoramento e o próprio login
LIVRES = {"/api/saude", "/api/auth/eu", "/api/auth/entrar", "/api/auth/retorno", "/api/auth/sair"}


def _sessao(token: str | None) -> dict | None:
    con = conectar()
    try:
        return sessoes.ler(con, token)
    finally:
        con.close()


async def exige_login(request: Request, chamar):
    """Com o login Microsoft ligado, toda a API pede sessão (menos LIVRES), inclusive rotas que surgirem depois.

    As páginas do app abrem sem sessão: o HTML e o JavaScript não trazem dados, só a tela de entrar. Os dados vêm
    da API. /metrics fica de fora (o Prometheus coleta pela rede interna; o Caddy já o bloqueia na internet).
    """
    if entra.login_ligado():
        caminho = request.url.path
        if (caminho == "/api" or caminho.startswith("/api/")) and caminho not in LIVRES:
            sessao = await run_in_threadpool(_sessao, request.cookies.get(sessoes.COOKIE))
            if not sessao:
                return JSONResponse({"detail": "Entre com a sua conta Microsoft para continuar."}, status_code=401)
            request.state.sessao = sessao  # a autoria (rotas.usuario) passa a ser quem entrou
    return await chamar(request)


# o primeiro middleware registrado é o mais interno: métricas e cabeçalhos também valem para o 401
app.middleware("http")(exige_login)
app.add_middleware(CORSMiddleware, allow_origins=ORIGENS_CORS, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(MetricasHTTP)


@app.middleware("http")
async def fora_dos_buscadores(request: Request, chamar):
    """Wiki interna: nenhuma página entra no Google, mesmo que o endereço vaze (junto do robots.txt do frontend)."""
    resposta = await chamar(request)
    resposta.headers["X-Robots-Tag"] = "noindex, nofollow"
    return resposta

for r in (saude, auth, metricas, modulos, menus, catalogo, manuais, descricoes, trechos):
    app.include_router(r.router)

# por último: o build do frontend (modo de produção) responde o que não for da API
app.include_router(frontend.router)
