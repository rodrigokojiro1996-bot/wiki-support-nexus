"""Support Nexus · API.

Rodar (dentro de backend/):
    .venv\\Scripts\\uvicorn app.main:app --reload --port 8010
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import ORIGENS_CORS, VERSAO, pasta_conteudo
from .db import conectar, migrar
from .rotas import catalogo, manuais, menus, modulos


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

for r in (modulos, menus, catalogo, manuais):
    app.include_router(r.router)

# prints dos manuais: backend/dados/imagens (real) ou backend/seed/imagens (exemplo) → /api/imagens/<código>/<arquivo>
IMAGENS = pasta_conteudo("imagens")
IMAGENS.mkdir(parents=True, exist_ok=True)
app.mount("/api/imagens", StaticFiles(directory=IMAGENS), name="imagens")
