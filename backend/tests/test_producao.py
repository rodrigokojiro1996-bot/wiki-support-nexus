from app import config


def test_paginas_e_api_fora_dos_buscadores(cliente):
    for url in ("/api/saude", "/api/modulos", "/qualquer-tela"):
        assert cliente.get(url).headers["X-Robots-Tag"] == "noindex, nofollow"


def test_saude_informa_o_ambiente(cliente, monkeypatch):
    from app.rotas import saude
    assert cliente.get("/api/saude").json()["ambiente"] == ""
    monkeypatch.setattr(saude, "AMBIENTE", "homologacao")
    assert cliente.get("/api/saude").json()["ambiente"] == "homologacao"


def test_saude(cliente):
    r = cliente.get("/api/saude")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["ok"] is True and corpo["versao"] == config.VERSAO and corpo["schema"] >= 2


def test_saude_com_banco_fora_do_ar(cliente, monkeypatch, tmp_path):
    from app import db
    monkeypatch.setattr(db, "ARQUIVO", tmp_path / "pasta_que_nao_existe" / "\0invalido.db")
    r = cliente.get("/api/saude")
    assert r.status_code == 503 and r.json()["ok"] is False


def test_frontend_sem_build(cliente, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DIST", tmp_path / "dist")
    r = cliente.get("/")
    assert r.status_code == 404 and "npm run build" in r.json()["detail"]


def test_frontend_servido_com_fallback(cliente, monkeypatch, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<div id=root></div>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "segredo.txt").write_text("nao", encoding="utf-8")
    monkeypatch.setattr(config, "DIST", dist)

    assert cliente.get("/").text == "<div id=root></div>"
    assert cliente.get("/assets/app.js").text == "console.log(1)"
    # rotas do React Router caem no index.html
    assert cliente.get("/manuais/DEMO.001/imprimir").text == "<div id=root></div>"
    # fora do dist, nunca
    assert "nao" not in cliente.get("/../segredo.txt").text
    assert "nao" not in cliente.get("/%2e%2e/segredo.txt").text


def test_api_inexistente_continua_404_json(cliente, monkeypatch, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("x", encoding="utf-8")
    monkeypatch.setattr(config, "DIST", dist)
    r = cliente.get("/api/nao-existe")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")
    # as rotas reais da API e os prints continuam acima do fallback
    assert cliente.get("/api/modulos").status_code == 200
    assert cliente.get("/docs").status_code == 200
