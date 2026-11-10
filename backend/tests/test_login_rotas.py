"""Login Microsoft de ponta a ponta pela API: portão, ida ao Entra, volta, sessão, sair, autoria e PDF."""
from urllib.parse import parse_qs, quote, urlparse

import pytest
from fastapi.testclient import TestClient

from app import config, db, pdf
from app.main import app
from app.servicos import entra, sessoes
from conftest import TENANT


@pytest.fixture
def web(banco, entra_ligado, microsoft):
    """Navegador de teste em HTTPS (os cookies são Secure) com o login Microsoft ligado."""
    return TestClient(app, base_url="https://nexus.exemplo.com.br", follow_redirects=False)


def entrar(web, voltar=None) -> dict:
    """Clica em "Entrar": devolve os parâmetros que foram para a Microsoft."""
    r = web.get("/api/auth/entrar", params={"voltar": voltar} if voltar else None)
    assert r.status_code == 302
    return {k: v[0] for k, v in parse_qs(urlparse(r.headers["location"]).query).items()}


def voltar_do_entra(web, microsoft, ida, **claims):
    """A Microsoft devolve o navegador com o código; o token que ela entregará na troca leva `claims`."""
    microsoft.proximo_token = microsoft.token(ida["nonce"], **claims)
    return web.get("/api/auth/retorno", params={"code": "codigo-do-entra", "state": ida["state"]})


def logar(web, microsoft, **claims):
    r = voltar_do_entra(web, microsoft, entrar(web), **claims)
    assert r.headers["location"] == "/"
    return r


def cookie(resposta, nome) -> str:
    """O Set-Cookie de `nome` em minúsculas ('' se não veio)."""
    return next((c.lower() for c in resposta.headers.get_list("set-cookie") if c.startswith(f"{nome}=")), "")


# ---------------- desligado ----------------
def test_desligado_nada_muda(cliente):
    assert cliente.get("/api/modulos").status_code == 200
    assert cliente.get("/api/auth/eu").json() == {"login": False, "usuario": None}
    assert cliente.get("/api/auth/entrar", follow_redirects=False).status_code == 404


def test_desligado_autoria_continua_pelo_nome(cliente):
    r = next(x for x in cliente.get("/api/modulos/pdv/catalogo").json()["relacoes"] if x["estado"] == "sugerida")
    cliente.put("/api/modulos/pdv/relacoes/status", json={"id": r["id"], "status": "documentada"},
                headers={"X-Usuario": quote("Ana")})
    assert next(x for x in cliente.get("/api/modulos/pdv/catalogo").json()["relacoes"] if x["id"] == r["id"])["por"] == "Ana"


# ---------------- portão ----------------
@pytest.mark.parametrize("metodo, url", [
    ("get", "/api/modulos"), ("get", "/api/manuais/DEMO.001"), ("get", "/api/manuais/DEMO.001/pdf"),
    ("get", "/api/imagens/DEMO.001/x.png"), ("put", "/api/modulos/pdv/relacoes/status"), ("post", "/api/manuais"),
])
def test_sem_sessao_a_api_responde_401(web, metodo, url):
    assert getattr(web, metodo)(url).status_code == 401


def test_ficam_abertos_saude_metricas_e_a_tela(web, tmp_path, monkeypatch):
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<div id=root></div>", encoding="utf-8")
    monkeypatch.setattr(config, "DIST", tmp_path / "dist")
    assert web.get("/api/saude").status_code == 200          # monitores de disponibilidade
    assert web.get("/metrics").status_code == 200            # Prometheus, pela rede interna
    assert web.get("/manuais/DEMO.001").status_code == 200   # o app abre para mostrar a tela de entrar
    assert web.get("/api/auth/eu").json() == {"login": True, "usuario": None}


# ---------------- ida ao Entra ----------------
def test_entrar_leva_ao_entra_do_tenant(web):
    r = web.get("/api/auth/entrar")
    assert r.headers["location"].startswith(f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/authorize?")
    c = cookie(r, "nexus_login")
    assert "httponly" in c and "secure" in c and "samesite=lax" in c and "path=/api/auth" in c


def test_configuracao_incompleta_avisa_na_tela(web, monkeypatch):
    monkeypatch.setenv("MICROSOFT_TENANT_ID", "common")
    assert web.get("/api/auth/entrar").headers["location"] == "/?erro_login=config"


def test_configuracao_incompleta_impede_a_subida(banco, entra_ligado, monkeypatch):
    monkeypatch.setenv("MICROSOFT_TENANT_ID", "common")
    with pytest.raises(RuntimeError, match="MICROSOFT_TENANT_ID"):
        with TestClient(app):
            pass


# ---------------- volta do Entra ----------------
def test_login_completo(web, microsoft):
    r = logar(web, microsoft)
    c = cookie(r, "nexus_sessao")
    assert "httponly" in c and "secure" in c and "samesite=lax" in c
    assert web.get("/api/auth/eu").json() == {"login": True, "usuario": {
        "nome": "Carla Exemplo", "email": "carla.exemplo@farmaciasassociadas.com.br"}}
    assert web.get("/api/modulos").status_code == 200


def test_volta_para_a_pagina_pedida(web, microsoft):
    r = voltar_do_entra(web, microsoft, entrar(web, "/manuais/DEMO.001"))
    assert r.headers["location"] == "/manuais/DEMO.001"


def test_destino_de_outro_site_vira_inicio(web, microsoft):
    r = voltar_do_entra(web, microsoft, entrar(web, "https://golpe.exemplo.com/"))
    assert r.headers["location"] == "/"


@pytest.mark.parametrize("upn", ["fulano@outra-empresa-do-grupo.com.br", "fulano@outrodominio.com.br"])
def test_conta_de_outro_dominio_nao_entra(web, microsoft, upn):
    r = voltar_do_entra(web, microsoft, entrar(web), preferred_username=upn)
    assert r.headers["location"] == "/?erro_login=negado"
    assert cookie(r, "nexus_sessao") == ""
    assert web.get("/api/modulos").status_code == 401


def test_conta_de_outro_tenant_nao_entra(web, microsoft):
    r = voltar_do_entra(web, microsoft, entrar(web), tid="99999999-9999-9999-9999-999999999999")
    assert r.headers["location"] == "/?erro_login=negado"


def test_state_trocado_nem_chega_a_trocar_o_codigo(web, microsoft):
    entrar(web)
    r = web.get("/api/auth/retorno", params={"code": "c", "state": "estado-de-outra-pessoa"})
    assert r.headers["location"] == "/?erro_login=expirado"
    assert microsoft.pedidos == []


def test_retorno_sem_ter_clicado_em_entrar(web, microsoft):
    r = web.get("/api/auth/retorno", params={"code": "c", "state": "s"})
    assert r.headers["location"] == "/?erro_login=expirado"
    assert microsoft.pedidos == []


def test_cancelou_na_tela_da_microsoft(web, microsoft):
    ida = entrar(web)
    r = web.get("/api/auth/retorno", params={"error": "access_denied", "state": ida["state"]})
    assert r.headers["location"] == "/?erro_login=cancelado"


def test_microsoft_fora_do_ar(web, microsoft, monkeypatch):
    def fora(url, campos):
        raise entra.FalhaLogin("indisponivel", "teste")
    monkeypatch.setattr(entra, "_post_formulario", fora)
    ida = entrar(web)
    r = web.get("/api/auth/retorno", params={"code": "c", "state": ida["state"]})
    assert r.headers["location"] == "/?erro_login=indisponivel"


# ---------------- sair ----------------
def test_sair_encerra_a_sessao(web, microsoft):
    logar(web, microsoft)
    r = web.post("/api/auth/sair")
    assert r.status_code == 204 and "max-age=0" in cookie(r, "nexus_sessao")
    assert web.get("/api/modulos").status_code == 401


# ---------------- autoria e PDF ----------------
def test_autoria_e_quem_entrou_e_nao_o_cabecalho(web, microsoft):
    logar(web, microsoft)
    r = next(x for x in web.get("/api/modulos/pdv/catalogo").json()["relacoes"] if x["estado"] == "sugerida")
    web.put("/api/modulos/pdv/relacoes/status", json={"id": r["id"], "status": "documentada"},
            headers={"X-Usuario": quote("Impostor")})
    assert next(x for x in web.get("/api/modulos/pdv/catalogo").json()["relacoes"] if x["id"] == r["id"])["por"] == "Carla Exemplo"


def test_pdf_abre_a_impressao_com_sessao_temporaria(web, microsoft, monkeypatch):
    # o navegador sem tela que gera o PDF também passa pelo portão: leva uma sessão que só existe durante a geração
    logar(web, microsoft)
    visto = {}

    def gerar(codigo, alterado_em, sessao):
        con = db.conectar()
        visto["durante"], visto["token"] = sessoes.ler(con, sessao), sessao
        con.close()
        return b"%PDF-1.7"
    monkeypatch.setattr(pdf, "gerar", gerar)
    assert web.get("/api/manuais/DEMO.001/pdf").status_code == 200
    assert visto["durante"] is not None
    con = db.conectar()
    assert sessoes.ler(con, visto["token"]) is None
    con.close()
