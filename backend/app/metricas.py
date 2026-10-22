"""Métricas da API no formato do Prometheus (GET /metrics).

Convenções do Prometheus: nomes em inglês, snake_case, com a unidade no nome (_seconds) e _total nos contadores.
O rótulo "route" é o MODELO da rota (/api/menus/{menu_id}), nunca a URL real: cada valor de rótulo vira uma série
guardada no Prometheus, e usar a URL criaria uma série por tela/manual ("explosão de cardinalidade").
"""
import time

from prometheus_client import REGISTRY, Counter, Histogram, Info
from prometheus_client.core import GaugeMetricFamily
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import db
from .config import VERSAO
from .servicos import cobertura

REQUISICOES = Counter("nexus_http_requests_total", "Requisições HTTP atendidas", ["method", "route", "status"])
DURACAO = Histogram("nexus_http_request_duration_seconds", "Tempo de resposta das requisições HTTP", ["method", "route"],
                    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10))
PDF_DURACAO = Histogram("nexus_pdf_generation_duration_seconds", "Tempo para gerar o PDF de um manual",
                        buckets=(0.5, 1, 2, 3, 5, 8, 13, 20, 30))
PDF_FALHAS = Counter("nexus_pdf_generation_failures_total", "Falhas ao gerar o PDF de um manual")
# formato: pdf, docx, txt, md (ou doc, docm, desconhecido nas recusas); resultado: ok, recusado
IMPORTACOES = Counter("nexus_importacoes_total", "Documentos enviados para virar manual", ["formato", "resultado"])
IMPORTACAO_DURACAO = Histogram("nexus_importacao_duration_seconds", "Tempo para converter um documento em rascunho de manual",
                               ["formato"], buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30))
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


class CoberturaWiki:
    """Coletor personalizado: a cada leitura de /metrics, calcula a cobertura da wiki no banco (gauges).

    O Prometheus guarda cada leitura, então o histórico mostra a cobertura evoluindo ao longo das semanas.
    Definições em servicos/cobertura.py. Se o banco falhar, /metrics continua respondendo, com nexus_wiki_up 0.
    """

    TELAS = [("telas", "nexus_wiki_screens", "Telas (itens de menu sem subitens)"),
             ("com_manual", "nexus_wiki_screens_with_manual", "Telas com pelo menos um manual"),
             ("com_tabelas", "nexus_wiki_screens_with_tables", "Telas com pelo menos uma tabela vinculada"),
             ("tabelas_confirmadas", "nexus_wiki_screens_tables_confirmed", "Telas com todos os vínculos de tabela confirmados pela equipe"),
             ("a_detalhar", "nexus_wiki_screens_to_detail", "Telas com submenu ainda não mapeado")]

    def describe(self):
        return []  # nomes dinâmicos por consulta: o registro não precisa conhecê-los antes

    def collect(self):
        up = GaugeMetricFamily("nexus_wiki_up", "1 se a cobertura da wiki foi calculada nesta coleta")
        try:
            con = db.conectar()
            try:
                c = cobertura.calcular(con)
            finally:
                con.close()
        except Exception:
            up.add_metric([], 0)
            yield up
            return
        up.add_metric([], 1)
        yield up
        for chave, nome, ajuda in self.TELAS:
            g = GaugeMetricFamily(nome, ajuda, labels=["module", "menu"])
            for t in c.telas:
                g.add_metric([t["modulo"], t["menu"]], t[chave])
            yield g
        g = GaugeMetricFamily("nexus_wiki_manuals", "Manuais por módulo", labels=["module"])
        for modulo, n in c.manuais.items():
            g.add_metric([modulo], n)
        yield g
        g = GaugeMetricFamily("nexus_wiki_relations", "Relações entre tabelas por estado", labels=["module", "state"])
        for r in c.relacoes:
            g.add_metric([r["modulo"], r["estado"]], r["n"])
        yield g
        g = GaugeMetricFamily("nexus_wiki_contributions_7d", "Contribuições nos últimos 7 dias, por autor e tipo",
                              labels=["author", "kind"])
        for r in c.contribuicoes:
            g.add_metric([r["autor"], r["tipo"]], r["n"])
        yield g


REGISTRY.register(CoberturaWiki())
