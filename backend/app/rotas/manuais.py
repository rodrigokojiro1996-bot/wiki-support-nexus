import time
from typing import Annotated, Literal
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, field_validator, model_validator

from .. import pdf
from ..metricas import IMPORTACAO_DURACAO, IMPORTACOES, PDF_DURACAO, PDF_FALHAS
from ..servicos import importacao
from ..servicos import manuais as servico
from ..servicos.manuais import manual_completo
from . import db, usuario

router = APIRouter(prefix="/api")


def _manual(con, codigo: str) -> dict:
    m = manual_completo(con, codigo)
    if not m:
        raise HTTPException(404, "Manual não encontrado")
    return m


@router.get("/manuais")
def manuais(modulo: str | None = None, con=Depends(db)):
    sql = "SELECT codigo, titulo, subtitulo, versao, modulo, menu, tipo, atualizado_em FROM manuais"
    args = ()
    if modulo:
        sql += " WHERE modulo = ?"
        args = (modulo,)
    return [dict(m) for m in con.execute(sql + " ORDER BY codigo", args)]


@router.get("/manuais/{codigo}")
def manual(codigo: str, con=Depends(db)):
    return _manual(con, codigo)


@router.get("/manuais/{codigo}/pdf")
def manual_pdf(codigo: str, con=Depends(db)):
    m = _manual(con, codigo)
    inicio = time.perf_counter()
    try:
        conteudo = pdf.gerar(codigo, m.get("alterado_em"))
    except Exception as e:  # sem Edge/Chromium ou frontend fora do ar
        PDF_FALHAS.inc()
        raise HTTPException(503, f"Não foi possível gerar o PDF: {e}") from e
    PDF_DURACAO.observe(time.perf_counter() - inicio)
    nome = f"{codigo} - {m['modulo_nome']} - {m['titulo']}.pdf".replace("/", "-")
    return Response(conteudo, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{pdf.quote(nome)}"})


# ---------------- editor ----------------
class BlocoEntrada(BaseModel):
    tipo: Literal["passo", "texto", "subtitulo", "obs", "nota", "sql", "imagem"]
    texto: str = Field("", max_length=20000)
    rotulo: str | None = Field(None, max_length=20)  # numeração original de manuais importados
    arquivo: str = Field("", max_length=200)
    legenda: str = Field("", max_length=500)

    @model_validator(mode="after")
    def conteudo(self):
        if self.tipo == "imagem":
            if self.arquivo and not servico.caminho_imagem(self.arquivo):
                raise ValueError(f"imagem {self.arquivo} não encontrada; envie o print de novo")
        elif not self.texto.strip():
            raise ValueError(f"bloco {self.tipo} sem texto")
        return self


class SecaoEntrada(BaseModel):
    titulo: str = Field(max_length=200)
    blocos: list[BlocoEntrada] = Field(max_length=500)

    @field_validator("titulo")
    @classmethod
    def titulo_preenchido(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("toda seção precisa de título")
        return v


class ManualEntrada(BaseModel):
    titulo: str = Field(max_length=200)
    subtitulo: str = Field("", max_length=500)
    modulo: str
    menu: str | None = None
    secoes: list[SecaoEntrada] = Field(min_length=1, max_length=100)
    # documentos de origem (importação); vazio mantém os que o manual já tinha
    fontes: list[Annotated[str, Field(max_length=200)]] = Field(default_factory=list, max_length=20)
    # processo = o manual da tela (um por tela); chamado = chamado frequente da tela. Sem tipo: processo no novo,
    # o que já era na edição
    tipo: Literal["processo", "chamado"] | None = None

    @field_validator("titulo")
    @classmethod
    def titulo_preenchido(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("o manual precisa de título")
        return v


def _conferir_destino(con, corpo: ManualEntrada, codigo: str | None = None) -> None:
    if not con.execute("SELECT 1 FROM modulos WHERE id = ? AND banco IS NOT NULL", (corpo.modulo,)).fetchone():
        raise HTTPException(422, f"Módulo {corpo.modulo} não existe ou ainda não tem banco mapeado")
    if not corpo.menu:
        return
    menu = con.execute("SELECT titulo, submenu FROM menus WHERE id = ? AND modulo = ?", (corpo.menu, corpo.modulo)).fetchone()
    if not menu:
        raise HTTPException(422, f"Tela {corpo.menu} não existe no módulo {corpo.modulo}")
    # manual só em tela final: menu principal ou submenu (com opções depois dele) é só navegação
    if menu["submenu"] or con.execute("SELECT 1 FROM menus WHERE pai = ?", (corpo.menu,)).fetchone():
        raise HTTPException(422, f"{menu['titulo']} é um menu, não uma tela: escolha uma das opções dentro dele")
    # um manual de processos por tela; chamados frequentes, quantos forem preciso
    anterior = con.execute("SELECT tipo FROM manuais WHERE codigo = ?", (codigo,)).fetchone() if codigo else None
    tipo = corpo.tipo or (anterior["tipo"] if anterior else "processo")
    if tipo == "processo":
        outro = con.execute("SELECT codigo FROM manuais WHERE menu = ? AND tipo = 'processo' AND codigo <> ?",
                            (corpo.menu, codigo or "")).fetchone()
        if outro:
            raise HTTPException(409, f"{menu['titulo']} já tem o manual da tela ({outro['codigo']}): edite esse manual, "
                                     "ou cadastre este como chamado frequente")


@router.post("/manuais", status_code=201)
def criar_manual(corpo: ManualEntrada, con=Depends(db), por: str = Depends(usuario)):
    _conferir_destino(con, corpo)
    m = servico.salvar(con, corpo.model_dump(), por)
    return {"codigo": m["codigo"], "versao": m["versao"]}


@router.put("/manuais/{codigo}")
def editar_manual(codigo: str, corpo: ManualEntrada, con=Depends(db), por: str = Depends(usuario)):
    _manual(con, codigo)
    _conferir_destino(con, corpo, codigo)
    m = servico.salvar(con, corpo.model_dump(), por, codigo)
    return {"codigo": m["codigo"], "versao": m["versao"]}


async def _documento(request: Request) -> bytes:
    """Corpo da importação lido em partes: passou do limite, para na hora (não carrega 1 GB na memória)."""
    limite = importacao.TAMANHO_MAXIMO
    mensagem = f"Arquivo maior que {limite // 1024 // 1024} MB"
    total = int(request.headers.get("content-length") or 0)
    partes = []
    if total <= limite:
        total = 0
        async for parte in request.stream():
            total += len(parte)
            if total > limite:
                break
            partes.append(parte)
    if total > limite:
        IMPORTACOES.labels("desconhecido", "recusado").inc()
        raise HTTPException(413, mensagem)
    return b"".join(partes)


@router.post("/manuais/importar")
def importar_manual(modulo: str, dados: bytes = Depends(_documento), x_arquivo: str = Header("documento.txt"),
                    con=Depends(db)):
    """Corpo = bytes do documento; cabeçalho X-Arquivo = nome do arquivo (URL-encoded).

    Devolve o rascunho {titulo, subtitulo, secoes, fontes, tabelas, avisos} para revisar no editor. NÃO salva o
    manual: quem salva é o POST /api/manuais. Rota síncrona: o FastAPI roda numa thread e a conversão de um PDF
    grande não trava as outras requisições.
    """
    linha = con.execute("SELECT banco FROM modulos WHERE id = ?", (modulo,)).fetchone()
    if not linha:
        raise HTTPException(404, f"Módulo {modulo} não existe")
    nomes = {r[0].lower() for r in con.execute("SELECT nome FROM tabelas WHERE banco = ?", (linha["banco"],))}
    # só o nome, sem pastas: o valor vem do navegador e vai para o manual como fonte
    nome = unquote(x_arquivo).replace("\\", "/").rsplit("/", 1)[-1].strip()[:200] or "documento.txt"
    inicio = time.perf_counter()
    try:
        rascunho = importacao.converter(dados, nome, nomes)
    except importacao.ImportacaoRecusada as e:
        IMPORTACOES.labels(e.formato, "recusado").inc()
        raise HTTPException(e.status, e.mensagem) from e
    IMPORTACAO_DURACAO.labels(rascunho["formato"]).observe(time.perf_counter() - inicio)
    IMPORTACOES.labels(rascunho["formato"], "ok").inc()
    return rascunho


@router.post("/imagens", status_code=201)
async def enviar_imagem(request: Request):
    """Corpo = bytes da imagem (print colado ou arquivo). Fica em rascunho até o manual ser salvo."""
    dados = await request.body()
    if len(dados) > servico.TAMANHO_MAXIMO_IMAGEM:
        raise HTTPException(413, "Imagem maior que 8 MB")
    if not servico.extensao_imagem(dados):
        raise HTTPException(415, "Envie uma imagem PNG, JPG, GIF ou WebP")
    return {"arquivo": servico.guardar_rascunho(dados)}


@router.get("/imagens/{pasta}/{nome}")
def imagem(pasta: str, nome: str):
    """Prints dos manuais: backend/dados/imagens (real e rascunhos) ou backend/seed/imagens (exemplo)."""
    arq = servico.caminho_imagem(f"{pasta}/{nome}")
    if not arq:
        raise HTTPException(404, "Imagem não encontrada")
    return FileResponse(arq)
