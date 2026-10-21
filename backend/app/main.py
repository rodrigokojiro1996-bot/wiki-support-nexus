"""Support Nexus · API.

Rodar (dentro de backend/):
    .venv\\Scripts\\uvicorn app.main:app --reload --port 8010
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import ORIGENS_CORS, VERSAO
from .db import conectar, migrar
from .rotas import catalogo, frontend, manuais, menus, modulos, saude


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

for r in (saude, modulos, menus, catalogo, manuais):
    app.include_router(r.router)

# por último: o build do frontend (modo de produção) responde o que não for da API
app.include_router(frontend.router)
