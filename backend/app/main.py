"""Support Nexus · API.

Rodar (dentro de backend/):
    .venv\\Scripts\\uvicorn app.main:app --reload --port 8010
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import ORIGENS_CORS, VERSAO
from .db import conectar, migrar
from .metricas import MetricasHTTP
from .rotas import catalogo, frontend, manuais, menus, metricas, modulos, saude


@asynccontextmanager
async def ciclo(_app):
    # código novo com banco antigo: aplica as migrações que faltam antes de atender
    con = conectar()
    try:
        migrar(con)
    finally:
        con.close()
    yield


app = FastAPI(title="Support Nexus", version=VERSAO, lifespan=ciclo)
app.add_middleware(CORSMiddleware, allow_origins=ORIGENS_CORS, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(MetricasHTTP)


@app.middleware("http")
async def fora_dos_buscadores(request: Request, chamar):
    """Wiki interna: nenhuma página entra no Google, mesmo que o endereço vaze (junto do robots.txt do frontend)."""
    resposta = await chamar(request)
    resposta.headers["X-Robots-Tag"] = "noindex, nofollow"
    return resposta

for r in (saude, metricas, modulos, menus, catalogo, manuais):
    app.include_router(r.router)

# por último: o build do frontend (modo de produção) responde o que não for da API
app.include_router(frontend.router)
