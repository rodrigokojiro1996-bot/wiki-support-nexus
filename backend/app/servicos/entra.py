"""Login com a conta Microsoft da empresa (Entra ID), pelo fluxo de código com PKCE (OpenID Connect).

Três regras moldam este arquivo:

1. **Desligado é desligado.** Sem MICROSOFT_AUTH_ENABLED=true nada aqui é lido e o Support Nexus funciona como
   antes (autoria pelo nome digitado no topo). É também o caminho de volta: uma variável e um restart.
2. **A fronteira é o tenant.** O tenant precisa ser o GUID da empresa (nunca "common" nem "organizations", que
   aceitariam conta de qualquer empresa) e o token precisa declarar esse mesmo `tid`.
3. **Só entra @farmaciasassociadas.com.br**, conferido no UPN (`preferred_username`), o login da conta. O tenant
   tem outros domínios verificados e eles ficam de fora. A claim `email` não é usada: ela pode ser de outro
   domínio que o login e não vale como prova de quem é a conta.

A criptografia é do PyJWT: a assinatura do ID token é conferida contra as chaves públicas do tenant.
"""
import base64
import hashlib
import json
import logging
import os
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

import jwt

log = logging.getLogger("nexus.login")

# Domínio aceito, comparado com o UPN inteiro (com o @). Exato: subdomínio e domínio parecido não passam.
DOMINIO_PERMITIDO = "farmaciasassociadas.com.br"

ESCOPOS = "openid profile email"  # só identidade: nada de Microsoft Graph
ALGORITMOS = ["RS256"]            # o Entra assina ID token com RS256; lista fechada barra "none" e HS256
TOLERANCIA_RELOGIO_S = 60         # desvio normal entre o relógio do Entra e o do servidor
TEMPO_LIMITE_S = 10               # ida à Microsoft (troca do código e chaves públicas)

_GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


class FalhaLogin(Exception):
    """Login recusado ou impossível. `codigo` vai para a tela (genérico de propósito); `motivo` só para o log.

    Códigos: config, indisponivel, negado, expirado, cancelado, invalido.
    """

    def __init__(self, codigo: str, motivo: str = ""):
        super().__init__(f"{codigo}: {motivo}" if motivo else codigo)
        self.codigo = codigo
        self.motivo = motivo


# ---------------- configuração ----------------
def login_ligado() -> bool:
    return os.environ.get("MICROSOFT_AUTH_ENABLED", "").strip().lower() == "true"


@dataclass(frozen=True)
class ConfigEntra:
    tenant_id: str
    client_id: str
    client_secret: str
    redirect_uri: str

    @property
    def _base(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}"

    @property
    def issuer(self) -> str:
        return f"{self._base}/v2.0"

    @property
    def url_autorizacao(self) -> str:
        return f"{self._base}/oauth2/v2.0/authorize"

    @property
    def url_token(self) -> str:
        return f"{self._base}/oauth2/v2.0/token"

    @property
    def url_chaves(self) -> str:
        return f"{self._base}/discovery/v2.0/keys"

    @property
    def cookie_seguro(self) -> bool:
        """Retorno em HTTPS = servidor publicado: os cookies só trafegam cifrados."""
        return self.redirect_uri.startswith("https://")


def _ler() -> ConfigEntra:
    return ConfigEntra(tenant_id=os.environ.get("MICROSOFT_TENANT_ID", "").strip(),
                       client_id=os.environ.get("MICROSOFT_CLIENT_ID", "").strip(),
                       client_secret=os.environ.get("MICROSOFT_CLIENT_SECRET", ""),
                       redirect_uri=os.environ.get("MICROSOFT_REDIRECT_URI", "").strip())


def problemas_config() -> list[str]:
    """O que falta ou está errado na configuração, em frases para quem opera o servidor (sem valor de segredo)."""
    cfg, problemas = _ler(), []
    if not _GUID.match(cfg.tenant_id):
        problemas.append("MICROSOFT_TENANT_ID precisa ser o GUID do tenant da empresa (não 'common' nem 'organizations')")
    if not _GUID.match(cfg.client_id):
        problemas.append("MICROSOFT_CLIENT_ID precisa ser o ID do aplicativo (um GUID)")
    segredo = cfg.client_secret.strip()
    if not segredo:
        problemas.append("MICROSOFT_CLIENT_SECRET ausente")
    elif segredo[0] in "\"'" or segredo[-1] in "\"'":
        problemas.append("MICROSOFT_CLIENT_SECRET está entre aspas: escreva o valor sem aspas no .env")
    elif _GUID.match(segredo):
        problemas.append("MICROSOFT_CLIENT_SECRET parece o ID do segredo (um GUID): use a coluna 'Valor' de "
                         "Certificados e segredos, não o 'ID secreto'")
    url = urllib.parse.urlparse(cfg.redirect_uri)
    local = url.hostname in ("localhost", "127.0.0.1")
    if not (url.scheme in ("http", "https") and url.netloc):
        problemas.append("MICROSOFT_REDIRECT_URI precisa ser uma URL completa (https://.../api/auth/retorno)")
    elif url.scheme != "https" and not local:
        problemas.append("MICROSOFT_REDIRECT_URI precisa ser HTTPS (o Entra só aceita http em localhost)")
    return problemas


def config_entra() -> ConfigEntra:
    problemas = problemas_config()
    if problemas:
        raise FalhaLogin("config", "; ".join(problemas))
    return _ler()


def cookie_seguro() -> bool:
    """Mesmo critério de ConfigEntra.cookie_seguro, para quando a configuração não pôde ser validada."""
    return _ler().cookie_seguro


# ---------------- ida ao Entra ----------------
@dataclass(frozen=True)
class Tentativa:
    """Segredos de uma tentativa de login: guardados no servidor entre a ida ao Entra e a volta."""
    state: str
    nonce: str
    verificador: str  # code_verifier do PKCE


def nova_tentativa() -> Tentativa:
    return Tentativa(state=secrets.token_urlsafe(32), nonce=secrets.token_urlsafe(32),
                     verificador=secrets.token_urlsafe(64))


def _desafio_pkce(verificador: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).rstrip(b"=").decode()


def url_de_login(cfg: ConfigEntra, t: Tentativa) -> str:
    return cfg.url_autorizacao + "?" + urllib.parse.urlencode({
        "client_id": cfg.client_id, "response_type": "code", "redirect_uri": cfg.redirect_uri,
        "response_mode": "query", "scope": ESCOPOS, "state": t.state, "nonce": t.nonce,
        "code_challenge": _desafio_pkce(t.verificador), "code_challenge_method": "S256",
        "prompt": "select_account",  # quem usa mais de uma conta Microsoft escolhe a da empresa
    })


# ---------------- troca do código ----------------
def _post_formulario(url: str, campos: dict) -> dict:
    """POST application/x-www-form-urlencoded e resposta JSON. Erro de rede ou HTTP vira FalhaLogin."""
    pedido = urllib.request.Request(url, data=urllib.parse.urlencode(campos).encode(), method="POST",
                                    headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE_S) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            erro = json.loads(e.read()).get("error", "")  # invalid_client, invalid_grant… nunca o segredo
        except Exception:
            erro = ""
        raise FalhaLogin("indisponivel", f"token endpoint respondeu {e.code} {erro}".strip()) from e
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise FalhaLogin("indisponivel", f"token endpoint fora do ar: {type(e).__name__}") from e


def trocar_codigo(cfg: ConfigEntra, codigo: str, verificador: str) -> str:
    """Troca o código da volta do Entra pelo ID token (ainda não verificado)."""
    resposta = _post_formulario(cfg.url_token, {
        "grant_type": "authorization_code", "client_id": cfg.client_id, "client_secret": cfg.client_secret,
        "code": codigo, "redirect_uri": cfg.redirect_uri, "code_verifier": verificador, "scope": ESCOPOS,
    })
    token = resposta.get("id_token")
    if not isinstance(token, str) or not token:
        raise FalhaLogin("indisponivel", "resposta da Microsoft sem id_token")
    return token


# ---------------- verificação do ID token ----------------
_jwks: dict[str, jwt.PyJWKClient] = {}


def _chave_publica(token: str, cfg: ConfigEntra):
    """Chave pública que assinou o token, das chaves do tenant (com cache). A URL vem da configuração, nunca do token."""
    cliente = _jwks.get(cfg.url_chaves)
    if cliente is None:
        cliente = _jwks[cfg.url_chaves] = jwt.PyJWKClient(cfg.url_chaves, cache_keys=True, lifespan=600,
                                                          timeout=TEMPO_LIMITE_S)
    try:
        return cliente.get_signing_key_from_jwt(token).key
    except jwt.PyJWKClientConnectionError as e:
        raise FalhaLogin("indisponivel", "chaves públicas do tenant fora do ar") from e
    except jwt.PyJWTError as e:
        raise FalhaLogin("invalido", f"chave do token: {type(e).__name__}") from e


def verificar_id_token(token: str, cfg: ConfigEntra, nonce: str) -> dict:
    """Confere assinatura, emissor, aplicativo, validade, tenant e nonce. Devolve as claims verificadas."""
    try:
        chave = _chave_publica(token, cfg)
        claims = jwt.decode(token, chave, algorithms=ALGORITMOS, audience=cfg.client_id, issuer=cfg.issuer,
                            leeway=TOLERANCIA_RELOGIO_S, options={"require": ["exp", "iat", "iss", "aud"]})
    except jwt.PyJWTError as e:
        raise FalhaLogin("invalido", f"token: {type(e).__name__}") from e
    if claims.get("tid") != cfg.tenant_id:
        raise FalhaLogin("negado", "token de outro tenant")
    recebido = claims.get("nonce")
    if not isinstance(recebido, str) or not secrets.compare_digest(recebido, nonce):
        raise FalhaLogin("invalido", "nonce não confere com a tentativa")
    if not isinstance(claims.get("oid"), str) or not claims["oid"].strip():
        raise FalhaLogin("invalido", "token sem oid")
    return claims


# ---------------- quem pode entrar ----------------
@dataclass(frozen=True)
class Identidade:
    oid: str    # identificador estável da pessoa no tenant
    email: str  # o UPN, minúsculo
    nome: str   # só para mostrar e para a autoria


def _email_da_empresa(bruto: object) -> str | None:
    """UPN normalizado se for exatamente @farmaciasassociadas.com.br; senão None.

    Só ASCII visível: um domínio com acento ou letra de outro alfabeto parece igual ao nosso e não é.
    """
    if not isinstance(bruto, str):
        return None
    email = bruto.strip().lower()
    if not email or re.search(r"[^\x21-\x7e]", email) or email.count("@") != 1:
        return None
    local, dominio = email.split("@")
    return email if local and dominio == DOMINIO_PERMITIDO else None


def extrair_identidade(claims: dict) -> Identidade:
    """Identidade a partir das claims JÁ verificadas por verificar_id_token."""
    email = _email_da_empresa(claims.get("preferred_username"))
    if not email:
        raise FalhaLogin("negado", "conta fora do domínio permitido")
    nome = claims.get("name")
    nome = nome.strip() if isinstance(nome, str) and nome.strip() else email
    return Identidade(oid=str(claims["oid"]), email=email, nome=nome[:80])


# ---------------- destino depois do login ----------------
def caminho_local(bruto: str | None) -> str:
    """Caminho interno para onde voltar depois do login; qualquer coisa suspeita vira "/".

    Barra endereço de outro site (https://, //, /\\), as rotas da API e qualquer caractere de controle ou espaço:
    quebra de linha seria injeção de cabeçalho, e o navegador descarta tabulação, então "/<tab>/site" viraria "//site".
    """
    if not bruto or len(bruto) > 2000 or "\\" in bruto or re.search(r"[\x00-\x20\x7f]", bruto):
        return "/"
    if not bruto.startswith("/") or bruto.startswith("//"):
        return "/"
    if bruto == "/api" or bruto.startswith("/api/"):
        return "/"
    return bruto
