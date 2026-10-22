"""Métricas da API no formato do Prometheus (GET /metrics).

Convenções do Prometheus: nomes em inglês, snake_case, com a unidade no nome (_seconds) e _total nos contadores.
O rótulo "route" é o MODELO da rota (/api/menus/{menu_id}), nunca a URL real: cada valor de rótulo vira uma série
guardada no Prometheus, e usar a URL criaria uma série por tela/manual ("explosão de cardinalidade").
"""
import time

from prometheus_client import Counter, Histogram, Info
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .config import VERSAO

REQUISICOES = Counter("nexus_http_requests_total", "Requisições HTTP atendidas", ["method", "route", "status"])
DURACAO = Histogram("nexus_http_request_duration_seconds", "Tempo de resposta das requisições HTTP", ["method", "route"],
                    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10))
PDF_DURACAO = Histogram("nexus_pdf_generation_duration_seconds", "Tempo para gerar o PDF de um manual",
                        buckets=(0.5, 1, 2, 3, 5, 8, 13, 20, 30))
PDF_FALHAS = Counter("nexus_pdf_generation_failures_total", "Falhas ao gerar o PDF de um manual")
Info("nexus", "Versão do Support Nexus").info({"version": VERSAO})

SEM_ROTA = "(sem rota)"
IGNORADAS = {"/metrics"}  # a coleta do próprio Prometheus não entra nas métricas


class MetricasHTTP:
    """Middleware ASGI: mede cada requisição HTTP e registra método, modelo da rota e status."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in IGNORADAS:
            await self.app(scope, receive, send)
            return
        inicio = time.perf_counter()
        status = 500  # se a aplicação quebrar antes de responder, conta como erro

        async def enviar(msg: Message) -> None:
            nonlocal status
            if msg["type"] == "http.response.start":
                status = msg["status"]
            await send(msg)

        try:
            await self.app(scope, receive, enviar)
        finally:
            rota = getattr(scope.get("route"), "path", SEM_ROTA)  # o roteamento grava a rota escolhida no scope
            DURACAO.labels(scope["method"], rota).observe(time.perf_counter() - inicio)
            REQUISICOES.labels(scope["method"], rota, str(status)).inc()
