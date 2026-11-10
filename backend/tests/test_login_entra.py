"""Login Microsoft (Entra ID): configuração, ida ao Entra, troca do código, verificação do token e regra de domínio."""
import base64
import hashlib
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.servicos import entra
from conftest import CLIENTE, RETORNO, TENANT


def codigo_da_falha(funcao, *args) -> str:
    with pytest.raises(entra.FalhaLogin) as e:
        funcao(*args)
    return e.value.codigo


# ---------------- configuração ----------------
def test_desligado_sem_a_variavel(monkeypatch):
    monkeypatch.delenv("MICROSOFT_AUTH_ENABLED", raising=False)
    assert entra.login_ligado() is False


def test_ligado_so_com_true(monkeypatch):
    monkeypatch.setenv("MICROSOFT_AUTH_ENABLED", "sim")
    assert entra.login_ligado() is False
    monkeypatch.setenv("MICROSOFT_AUTH_ENABLED", "True")
    assert entra.login_ligado() is True


def test_configuracao_completa_aponta_para_o_tenant(entra_ligado):
    cfg = entra.config_entra()
    assert cfg.issuer == f"https://login.microsoftonline.com/{TENANT}/v2.0"
    assert cfg.url_autorizacao == f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/authorize"
    assert cfg.url_token == f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/token"
    assert cfg.url_chaves == f"https://login.microsoftonline.com/{TENANT}/discovery/v2.0/keys"
    assert cfg.cookie_seguro is True


@pytest.mark.parametrize("tenant", ["common", "organizations", "consumers", "", "farmaciasassociadas.com.br"])
def test_tenant_precisa_ser_o_guid(entra_ligado, monkeypatch, tenant):
    # "common"/"organizations" aceitariam conta Microsoft de qualquer empresa do mundo
    monkeypatch.setenv("MICROSOFT_TENANT_ID", tenant)
    assert any("MICROSOFT_TENANT_ID" in p for p in entra.problemas_config())
    assert codigo_da_falha(entra.config_entra) == "config"


@pytest.mark.parametrize("variavel", ["MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET", "MICROSOFT_REDIRECT_URI"])
def test_variavel_obrigatoria_ausente(entra_ligado, monkeypatch, variavel):
    monkeypatch.delenv(variavel)
    assert any(variavel in p for p in entra.problemas_config())


def test_retorno_em_http_so_no_localhost(entra_ligado, monkeypatch):
    monkeypatch.setenv("MICROSOFT_REDIRECT_URI", "http://nexus.exemplo.com.br/api/auth/retorno")
    assert any("MICROSOFT_REDIRECT_URI" in p for p in entra.problemas_config())
    monkeypatch.setenv("MICROSOFT_REDIRECT_URI", "http://localhost:5173/api/auth/retorno")
    assert entra.problemas_config() == []
    assert entra.config_entra().cookie_seguro is False


def test_id_do_segredo_no_lugar_do_valor(entra_ligado, monkeypatch):
    # o Entra mostra "Valor" e "ID secreto" lado a lado; o ID (um GUID) não autentica e a Microsoft só diria
    # AADSTS7000215 depois de a pessoa já ter ido e voltado da tela de login
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "9f1c2d3e-4b5a-4c6d-8e7f-0a1b2c3d4e5f")
    assert any("ID do segredo" in p for p in entra.problemas_config())


def test_aspas_no_segredo_sao_recusadas(entra_ligado, monkeypatch):
    # o --env-file do Docker não tira aspas: o app receberia a secret com 2 caracteres a mais (já derrubou a Feira)
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", '"abc"')
    assert any("MICROSOFT_CLIENT_SECRET" in p for p in entra.problemas_config())


# ---------------- ida ao Entra ----------------
def test_url_de_login_leva_state_nonce_e_pkce(entra_ligado):
    cfg = entra.config_entra()
    t = entra.nova_tentativa()
    url = urlparse(entra.url_de_login(cfg, t))
    q = {k: v[0] for k, v in parse_qs(url.query).items()}
    assert f"{url.scheme}://{url.netloc}{url.path}" == f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/authorize"
    assert q["client_id"] == CLIENTE and q["redirect_uri"] == RETORNO
    assert q["response_type"] == "code" and q["scope"] == "openid profile email"
    assert q["state"] == t.state and q["nonce"] == t.nonce
    esperado = base64.urlsafe_b64encode(hashlib.sha256(t.verificador.encode()).digest()).rstrip(b"=").decode()
    assert q["code_challenge"] == esperado and q["code_challenge_method"] == "S256"


def test_cada_tentativa_tem_segredos_proprios():
    a, b = entra.nova_tentativa(), entra.nova_tentativa()
    assert len({a.state, b.state, a.nonce, b.nonce, a.verificador, b.verificador}) == 6
    assert 43 <= len(a.verificador) <= 128  # limite do PKCE (RFC 7636)


# ---------------- troca do código ----------------
def test_troca_envia_codigo_verificador_e_segredo(entra_ligado, microsoft):
    microsoft.proximo_token = "id-token"
    assert entra.trocar_codigo(entra.config_entra(), "codigo-123", "verificador-xyz") == "id-token"
    url, campos = microsoft.pedidos[0]
    assert url == f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/token"
    assert campos == {"grant_type": "authorization_code", "client_id": CLIENTE, "client_secret": "segredo-de-teste",
                      "code": "codigo-123", "redirect_uri": RETORNO, "code_verifier": "verificador-xyz",
                      "scope": "openid profile email"}


def test_troca_sem_id_token_e_indisponivel(entra_ligado, microsoft):
    microsoft.proximo_token = None
    assert codigo_da_falha(entra.trocar_codigo, entra.config_entra(), "c", "v") == "indisponivel"


# ---------------- verificação do ID token ----------------
def test_token_valido_devolve_as_claims(entra_ligado, microsoft):
    payload = entra.verificar_id_token(microsoft.token("n-1"), entra.config_entra(), "n-1")
    assert payload["oid"] == "0f0f0f0f-1111-2222-3333-444444444444"


def test_assinatura_de_outra_chave(entra_ligado, microsoft):
    outra = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode({"iss": entra.config_entra().issuer, "aud": CLIENTE, "tid": TENANT, "oid": "x", "nonce": "n",
                        "iat": 1, "exp": 4102444800}, outra, algorithm="RS256")
    assert codigo_da_falha(entra.verificar_id_token, token, entra.config_entra(), "n") == "invalido"


def test_algoritmo_simetrico_recusado(entra_ligado, microsoft):
    # HS256 com um segredo qualquer: só passaria se a lista de algoritmos aceitasse mais que RS256
    token = jwt.encode({"iss": entra.config_entra().issuer, "aud": CLIENTE, "tid": TENANT, "oid": "x", "nonce": "n",
                        "iat": 1, "exp": 4102444800}, "segredo-qualquer-com-32-bytes-ou-mais!!", algorithm="HS256")
    assert codigo_da_falha(entra.verificar_id_token, token, entra.config_entra(), "n") == "invalido"


@pytest.mark.parametrize("sobrepor, codigo", [
    ({"aud": "99999999-9999-9999-9999-999999999999"}, "invalido"),                          # token de outro app
    ({"iss": "https://login.microsoftonline.com/99999999-9999-9999-9999-999999999999/v2.0"}, "invalido"),
    ({"tid": "99999999-9999-9999-9999-999999999999"}, "negado"),                             # outro tenant
    ({"nonce": "de-outra-tentativa"}, "invalido"),
    ({"nonce": None}, "invalido"),
    ({"oid": None}, "invalido"),
    ({"exp": 1000, "iat": 900, "nbf": 900}, "invalido"),                                       # vencido
])
def test_token_recusado(entra_ligado, microsoft, sobrepor, codigo):
    token = microsoft.token("n-1", **sobrepor)
    assert codigo_da_falha(entra.verificar_id_token, token, entra.config_entra(), "n-1") == codigo


# ---------------- quem pode entrar ----------------
def claims(**extra):
    return {"oid": "0f0f0f0f-1111-2222-3333-444444444444", "name": "Carla Exemplo", **extra}


def test_conta_da_empresa_entra():
    i = entra.extrair_identidade(claims(preferred_username="Carla.Exemplo@FarmaciasAssociadas.com.br"))
    assert (i.oid, i.email, i.nome) == ("0f0f0f0f-1111-2222-3333-444444444444",
                                        "carla.exemplo@farmaciasassociadas.com.br", "Carla Exemplo")


def test_sem_nome_usa_o_email():
    i = entra.extrair_identidade({"oid": "o", "preferred_username": "ana@farmaciasassociadas.com.br"})
    assert i.nome == "ana@farmaciasassociadas.com.br"


@pytest.mark.parametrize("upn", [
    "fulano@outra-empresa-do-grupo.com.br",                           # mesmo tenant, outro domínio
    "fulano@outrodominio.com.br",
    "admin@associadas.exemplo.com.br",
    "fulano@nao-farmaciasassociadas.com.br",                          # passaria num "termina com" sem o @
    "fulano@farmaciasassociadas.com.br.exemplo.com",                  # passaria num "contém"
    "fulano@sub.farmaciasassociadas.com.br",                          # subdomínio não vale
    "fulano_gmail.com#EXT#@farmaciasassociadas.onmicrosoft.com",      # convidado de fora
    "fulano@farmáciasassociadas.com.br",                              # acento: visualmente igual, outro domínio
    "a@b@farmaciasassociadas.com.br",
    "",
])
def test_fora_do_dominio_e_negado(upn):
    assert codigo_da_falha(entra.extrair_identidade, claims(preferred_username=upn)) == "negado"


def test_email_de_contato_nao_substitui_o_upn():
    # a claim "email" é editável e pode ser de outro domínio que o login; a regra vale para a conta (UPN)
    c = claims(preferred_username="fulano@outrodominio.com.br", email="fulano.tal@farmaciasassociadas.com.br")
    assert codigo_da_falha(entra.extrair_identidade, c) == "negado"


# ---------------- destino depois do login ----------------
@pytest.mark.parametrize("bruto, destino", [
    ("/manuais/DEMO.001", "/manuais/DEMO.001"),
    ("/?modulo=pdv", "/?modulo=pdv"),
    (None, "/"),
    ("", "/"),
    ("https://golpe.exemplo.com", "/"),
    ("//golpe.exemplo.com", "/"),
    ("/\\golpe.exemplo.com", "/"),
    ("javascript:alert(1)", "/"),
    ("/manuais\r\nSet-Cookie: x=1", "/"),
    ("/\t/golpe.exemplo.com", "/"),                  # o navegador descarta a tabulação e leria //golpe...
    ("/ /golpe.exemplo.com", "/"),
    ("/\x00manuais", "/"),
    ("/api/auth/entrar", "/"),                       # não volta para o próprio login
])
def test_caminho_local(bruto, destino):
    assert entra.caminho_local(bruto) == destino
