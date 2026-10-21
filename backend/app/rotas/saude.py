from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..config import VERSAO
from ..db import conectar, versao_atual

router = APIRouter(prefix="/api")


@router.get("/saude")
def saude():
    """Para monitoramento e HEALTHCHECK: o banco responde e em que versão está."""
    try:
        con = conectar()
        try:
            con.execute("SELECT 1").fetchone()
            banco = versao_atual(con)
        finally:
            con.close()
    except Exception as e:
        return JSONResponse({"ok": False, "versao": VERSAO, "erro": str(e)}, status_code=503)
    return {"ok": True, "versao": VERSAO, "schema": banco}
