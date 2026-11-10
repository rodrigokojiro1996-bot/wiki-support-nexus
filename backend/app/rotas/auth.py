"""Login com a conta Microsoft da empresa: entrar, voltar do Entra, quem sou eu e sair.

Fluxo: o botão "Entrar" abre /api/auth/entrar, que guarda a tentativa (state, nonce, verificador do PKCE) e manda
o navegador para a Microsoft. A Microsoft devolve em /api/auth/retorno, que confere a tentativa, troca o código
pelo ID token, verifica o token e o domínio e abre a sessão. Erros voltam para a tela com ?erro_login=<código>,
genérico de propósito; o motivo detalhado vai só para o log.
"""
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from ..servicos import entra, sessoes
from . import db

log = logging.getLogger("nexus.login")
router = APIRouter(prefix="/api/auth")

COOKIE_LOGIN = "nexus_login"  # amarra a tentativa a este navegador; só vai para /api/auth
CAMINHO_LOGIN = "/api/auth"


def _ligado():
    if not entra.login_ligado():
        raise HTTPException(404, "Login Microsoft desligado neste servidor")


def _sem_tentativa(resposta: Response) -> Response:
    resposta.delete_cookie(COOKIE_LOGIN, path=CAMINHO_LOGIN, secure=entra.cookie_seguro(), httponly=True,
                           samesite="lax")
    return resposta


def _volta_com_erro(falha: entra.FalhaLogin) -> Response:
    (log.error if falha.codigo == "config" else log.warning)("login recusado: %s (%s)", falha.codigo, falha.motivo)
    return _sem_tentativa(RedirectResponse(f"/?erro_login={falha.codigo}", status_code=302))


@router.get("/eu")
def eu(request: Request, con=Depends(db)):
    """Para a tela decidir o que mostrar: login desligado, pedir para entrar, ou quem entrou."""
    if not entra.login_ligado():
        return {"login": False, "usuario": None}
    s = sessoes.ler(con, request.cookies.get(sessoes.COOKIE))
    return {"login": True, "usuario": {"nome": s["nome"], "email": s["email"]} if s else None}


@router.get("/entrar", dependencies=[Depends(_ligado)])
def entrar(voltar: str | None = None, con=Depends(db)):
    try:
        cfg = entra.config_entra()
    except entra.FalhaLogin as e:
        return _volta_com_erro(e)
    tentativa = entra.nova_tentativa()
    chave = sessoes.guardar_login(con, tentativa, entra.caminho_local(voltar))
    r = RedirectResponse(entra.url_de_login(cfg, tentativa), status_code=302)
    # Lax e não Strict: a volta da Microsoft é uma navegação vinda de outro site, e Strict descartaria o cookie
    r.set_cookie(COOKIE_LOGIN, chave, max_age=sessoes.LOGIN_PENDENTE_S, path=CAMINHO_LOGIN, httponly=True,
                 secure=cfg.cookie_seguro, samesite="lax")
    return r


@router.get("/retorno", dependencies=[Depends(_ligado)])
def retorno(request: Request, code: str | None = None, state: str | None = None, error: str | None = None,
            con=Depends(db)):
    # consumida logo de saída: com erro ou sem, esta tentativa não serve para outra volta
    pendente = sessoes.consumir_login(con, request.cookies.get(COOKIE_LOGIN))
    try:
        cfg = entra.config_entra()
        if error:
            raise entra.FalhaLogin("cancelado" if error == "access_denied" else "invalido", f"Entra devolveu {error}")
        if not pendente or not state or not secrets.compare_digest(state, pendente.tentativa.state):
            raise entra.FalhaLogin("expirado", "tentativa ausente, vencida ou de outro navegador")
        if not code:
            raise entra.FalhaLogin("invalido", "volta sem código")
        token = entra.trocar_codigo(cfg, code, pendente.tentativa.verificador)
        pessoa = entra.extrair_identidade(entra.verificar_id_token(token, cfg, pendente.tentativa.nonce))
    except entra.FalhaLogin as e:
        return _volta_com_erro(e)
    sessao = sessoes.criar(con, pessoa.oid, pessoa.email, pessoa.nome)
    log.info("login: %s", pessoa.email)
    r = _sem_tentativa(RedirectResponse(pendente.voltar, status_code=302))
    r.set_cookie(sessoes.COOKIE, sessao, max_age=sessoes.DURACAO_S, path="/", httponly=True,
                 secure=cfg.cookie_seguro, samesite="lax")
    return r


@router.post("/sair", status_code=204)
def sair(request: Request, con=Depends(db)):
    sessoes.encerrar(con, request.cookies.get(sessoes.COOKIE))
    r = Response(status_code=204)
    r.delete_cookie(sessoes.COOKIE, path="/", secure=entra.cookie_seguro(), httponly=True, samesite="lax")
    return r
