"""Modo de produção: a própria API serve o build do frontend (frontend/dist), sem o Vite.

Qualquer caminho que não seja arquivo do build devolve o index.html, para o React Router resolver
(/manuais/DEMO.001, /manuais/DEMO.001/imprimir…). Precisa ser o último router incluído.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import config

router = APIRouter(include_in_schema=False)


@router.get("/{caminho:path}")
def frontend(caminho: str):
    if caminho == "api" or caminho.startswith("api/"):
        raise HTTPException(404, "Rota da API não encontrada")
    dist = config.DIST.resolve()
    if not (dist / "index.html").exists():
        raise HTTPException(404, "Frontend não compilado: rode \"npm run build\" em frontend/ (ou use o Vite na 5173)")
    arq = (dist / caminho).resolve()
    if caminho and arq.is_file() and arq.is_relative_to(dist):
        return FileResponse(arq)
    return FileResponse(dist / "index.html")
