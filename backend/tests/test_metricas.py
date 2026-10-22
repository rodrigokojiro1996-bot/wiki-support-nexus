from prometheus_client import REGISTRY

from app import pdf


def valor(nome: str, **rotulos) -> float:
    """Valor atual de uma série (os contadores são globais ao processo: os testes comparam antes e depois)."""
    return REGISTRY.get_sample_value(nome, rotulos) or 0.0


def test_metrics_no_formato_do_prometheus(cliente):
    r = cliente.get("/metrics")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    assert "# TYPE nexus_http_requests_total counter" in r.text
    assert 'nexus_info{version="' in r.text


def test_conta_requisicao_pelo_modelo_da_rota(cliente):
    antes = valor("nexus_http_requests_total", method="GET", route="/api/menus/{menu_id}", status="200")
    cliente.get("/api/menus/pdv.caixa.fechamento-de-caixa")
    cliente.get("/api/menus/pdv.caixa.abertura-de-caixa")
    # duas telas diferentes = a mesma série (sem explosão de cardinalidade)
    assert valor("nexus_http_requests_total", method="GET", route="/api/menus/{menu_id}", status="200") == antes + 2
    assert "pdv.caixa" not in cliente.get("/metrics").text


def test_registra_status_de_erro(cliente):
    antes = valor("nexus_http_requests_total", method="GET", route="/api/menus/{menu_id}", status="404")
    cliente.get("/api/menus/nao.existe")
    assert valor("nexus_http_requests_total", method="GET", route="/api/menus/{menu_id}", status="404") == antes + 1


def test_mede_duracao(cliente):
    antes = valor("nexus_http_request_duration_seconds_count", method="GET", route="/api/modulos")
    cliente.get("/api/modulos")
    assert valor("nexus_http_request_duration_seconds_count", method="GET", route="/api/modulos") == antes + 1


def test_coleta_do_prometheus_nao_entra_nas_metricas(cliente):
    cliente.get("/metrics")
    assert 'route="/metrics"' not in cliente.get("/metrics").text


def test_pdf_ok_e_falha(cliente, monkeypatch):
    ok, falhas = valor("nexus_pdf_generation_duration_seconds_count"), valor("nexus_pdf_generation_failures_total")
    monkeypatch.setattr(pdf, "gerar", lambda codigo: b"%PDF-1.7")
    cliente.get("/api/manuais/DEMO.001/pdf")

    def quebra(codigo):
        raise RuntimeError("sem navegador")
    monkeypatch.setattr(pdf, "gerar", quebra)
    cliente.get("/api/manuais/DEMO.001/pdf")
    assert valor("nexus_pdf_generation_duration_seconds_count") == ok + 1
    assert valor("nexus_pdf_generation_failures_total") == falhas + 1
