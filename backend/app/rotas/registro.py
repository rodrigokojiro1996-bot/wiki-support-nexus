"""Histórico de alterações (só leitura): quem fez o quê no Support Nexus, e quando."""
from fastapi import APIRouter, Depends, Query

from ..servicos import registro
from . import db

router = APIRouter(prefix="/api/registro")


@router.get("")
def listar(por: str | None = None, area: str | None = None, acao: str | None = None, modulo: str | None = None,
           busca: str | None = Query(None, max_length=200), antes: int | None = None,
           limite: int = Query(100, ge=1, le=500), con=Depends(db)):
    """Mais recentes primeiro; `antes` = id da última linha recebida, para a próxima página."""
    return registro.listar(con, por=por, area=area, acao=acao, modulo=modulo, busca=(busca or "").strip() or None,
                           antes=antes, limite=limite)


@router.get("/filtros")
def filtros(con=Depends(db)):
    """Quem já alterou algo, e os nomes das áreas e ações (para os filtros da página)."""
    return {"pessoas": registro.pessoas(con), "areas": registro.AREAS, "acoes": list(registro.ACOES)}
