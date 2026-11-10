"""Dicionário de dados: importação da planilha conferida pela equipe."""
from fastapi import APIRouter, Depends, HTTPException

from ..servicos import descricoes
from . import db, usuario
from .manuais import _documento

router = APIRouter(prefix="/api/descricoes")


@router.post("/importar")
def importar(dados: bytes = Depends(_documento), con=Depends(db), por: str = Depends(usuario)):
    """Corpo = bytes da planilha (.xlsx) gerada por coletor/rascunho_descricoes.py. Grava só as linhas com Conferido = S."""
    try:
        return descricoes.importar(con, dados, por)
    except descricoes.PlanilhaInvalida as e:
        raise HTTPException(422, str(e)) from e
