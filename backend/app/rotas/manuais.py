from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, field_validator, model_validator

import time

from .. import pdf
from ..metricas import PDF_DURACAO, PDF_FALHAS
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
    sql = "SELECT codigo, titulo, subtitulo, versao, modulo, menu, atualizado_em FROM manuais"
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
        conteudo = pdf.gerar(codigo)
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

    @field_validator("titulo")
    @classmethod
    def titulo_preenchido(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("o manual precisa de título")
        return v


def _conferir_destino(con, corpo: ManualEntrada) -> None:
    if not con.execute("SELECT 1 FROM modulos WHERE id = ? AND banco IS NOT NULL", (corpo.modulo,)).fetchone():
        raise HTTPException(422, f"Módulo {corpo.modulo} não existe ou ainda não tem banco mapeado")
    if corpo.menu and not con.execute("SELECT 1 FROM menus WHERE id = ? AND modulo = ?", (corpo.menu, corpo.modulo)).fetchone():
        raise HTTPException(422, f"Tela {corpo.menu} não existe no módulo {corpo.modulo}")


@router.post("/manuais", status_code=201)
def criar_manual(corpo: ManualEntrada, con=Depends(db), por: str = Depends(usuario)):
    _conferir_destino(con, corpo)
    m = servico.salvar(con, corpo.model_dump(), por)
    return {"codigo": m["codigo"], "versao": m["versao"]}


@router.put("/manuais/{codigo}")
def editar_manual(codigo: str, corpo: ManualEntrada, con=Depends(db), por: str = Depends(usuario)):
    _manual(con, codigo)
    _conferir_destino(con, corpo)
    m = servico.salvar(con, corpo.model_dump(), por, codigo)
    return {"codigo": m["codigo"], "versao": m["versao"]}


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
