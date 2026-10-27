from app import pdf


def test_lista_e_filtro(cliente):
    todos = cliente.get("/api/manuais").json()
    assert len(todos) == 6
    assert cliente.get("/api/manuais", params={"modulo": "pdv"}).json() == todos
    assert cliente.get("/api/manuais", params={"modulo": "fin"}).json() == []


def test_manual_completo(cliente):
    m = cliente.get("/api/manuais/DEMO.001").json()
    assert m["codigo"] == "DEMO.001"
    assert isinstance(m["secoes"], list) and m["conteudo"] is None
    assert isinstance(m["tabelas"], list) and isinstance(m["fontes"], list)


def test_manual_inexistente_404(cliente):
    assert cliente.get("/api/manuais/NAO.000").status_code == 404
    assert cliente.get("/api/manuais/NAO.000/pdf").status_code == 404


def test_pdf_indisponivel_503(cliente, monkeypatch):
    def falha(codigo, *_):
        raise RuntimeError("sem navegador")
    monkeypatch.setattr(pdf, "gerar", falha)
    r = cliente.get("/api/manuais/DEMO.001/pdf")
    assert r.status_code == 503 and "sem navegador" in r.json()["detail"]


def test_pdf_ok(cliente, monkeypatch):
    monkeypatch.setattr(pdf, "gerar", lambda codigo, *_: b"%PDF-1.7 teste")
    r = cliente.get("/api/manuais/DEMO.001/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "DEMO.001" in r.headers["content-disposition"]
