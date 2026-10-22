from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter(include_in_schema=False)


@router.get("/metrics")
def metricas():
    """Lido pelo Prometheus a cada 15 s. Fica fora de /api por convenção (é o caminho que o Prometheus procura)."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
