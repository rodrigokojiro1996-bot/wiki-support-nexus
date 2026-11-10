"""Banco SQLite temporário carregado com o sistema de exemplo (demo_pdv), isolado de qualquer dado real."""
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app import config, db, seed
from app.main import app
from app.servicos import entra


@pytest.fixture
def banco(tmp_path, monkeypatch):
    # login desligado por padrão, mesmo que a máquina tenha as variáveis do Entra definidas
    monkeypatch.delenv("MICROSOFT_AUTH_ENABLED", raising=False)
    # dados/ vazio: manuais, imagens e módulos caem no exemplo versionado, mesmo que exista conteúdo real na máquina
    monkeypatch.setattr(config, "DADOS", tmp_path)
    monkeypatch.setattr(config, "MODULOS_REAL", tmp_path / "modulos.json")
    monkeypatch.setattr(config, "MENUS_REAIS", tmp_path / "menus_reais")
    monkeypatch.setattr(db, "ARQUIVO", tmp_path / "nexus.db")
    monkeypatch.setattr(seed, "arquivo_catalogo", lambda b: config.PROJETO / "coletor" / "exemplo" / b / "catalogo.json")
    seed.main()
    return tmp_path


@pytest.fixture
def cliente(banco):
    return TestClient(app)


@pytest.fixture
def con(banco):
    c = db.conectar()
    yield c
    c.close()


# ---------------- login Microsoft (Entra ID) ----------------
TENANT = "11111111-2222-3333-4444-555555555555"
CLIENTE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
RETORNO = "https://nexus.exemplo.com.br/api/auth/retorno"


@pytest.fixture
def entra_ligado(monkeypatch):
    """Login Microsoft ligado, com uma configuração válida de um tenant fictício."""
    for nome, valor in {"MICROSOFT_AUTH_ENABLED": "true", "MICROSOFT_TENANT_ID": TENANT,
                        "MICROSOFT_CLIENT_ID": CLIENTE, "MICROSOFT_CLIENT_SECRET": "segredo-de-teste",
                        "MICROSOFT_REDIRECT_URI": RETORNO}.items():
        monkeypatch.setenv(nome, valor)


@pytest.fixture(scope="session")
def chave_rsa():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class EntraFalso:
    """Faz o papel da Microsoft nos testes: assina ID tokens e responde a troca do código. Nada sai da máquina."""

    def __init__(self, chave):
        self.chave = chave
        self.pedidos: list[tuple[str, dict]] = []  # (url, campos) de cada troca de código
        self.proximo_token: str | None = None

    def token(self, nonce: str, /, **sobrepor) -> str:
        """ID token como o Entra emite (v2.0). `sobrepor` troca claims; valor None remove a claim."""
        agora = int(time.time())
        claims = {"iss": f"https://login.microsoftonline.com/{TENANT}/v2.0", "aud": CLIENTE, "tid": TENANT,
                  "oid": "0f0f0f0f-1111-2222-3333-444444444444", "nonce": nonce, "iat": agora, "nbf": agora,
                  "exp": agora + 3600, "name": "Carla Exemplo", "preferred_username": "carla.exemplo@farmaciasassociadas.com.br",
                  "ver": "2.0"}
        claims.update(sobrepor)
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode(claims, self.chave, algorithm="RS256", headers={"kid": "chave-de-teste"})

    def responder(self, url: str, campos: dict) -> dict:
        self.pedidos.append((url, campos))
        return {"token_type": "Bearer", "scope": "openid profile email", "expires_in": 3600,
                "access_token": "acesso-opaco", "id_token": self.proximo_token}


@pytest.fixture
def microsoft(monkeypatch, chave_rsa):
    """Substitui só as duas idas à internet: a chave pública do tenant e a troca do código por tokens."""
    falso = EntraFalso(chave_rsa)
    monkeypatch.setattr(entra, "_chave_publica", lambda token, cfg: chave_rsa.public_key())
    monkeypatch.setattr(entra, "_post_formulario", falso.responder)
    return falso
