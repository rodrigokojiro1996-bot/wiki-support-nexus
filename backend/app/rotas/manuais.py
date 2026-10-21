from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from .. import pdf
from ..servicos.manuais import manual_completo
from . import db

router = APIRouter(prefix="/api/manuais")


def _manual(con, codigo: str) -> dict:
    m = manual_completo(con, codigo)
    if not m:
        raise HTTPException(404, "Manual não encontrado")
    return m


@router.get("")
def manuais(modulo: str | None = None, con=Depends(db)):
    sql = "SELECT codigo, titulo, subtitulo, versao, modulo, menu, atualizado_em FROM manuais"
    args = ()
    if modulo:
        sql += " WHERE modulo = ?"
        args = (modulo,)
    return [dict(m) for m in con.execute(sql + " ORDER BY codigo", args)]


@router.get("/{codigo}")
def manual(codigo: str, con=Depends(db)):
    return _manual(con, codigo)


@router.get("/{codigo}/pdf")
def manual_pdf(codigo: str, con=Depends(db)):
    m = _manual(con, codigo)
    try:
        conteudo = pdf.gerar(codigo)
    except Exception as e:  # sem Edge/Chromium ou frontend fora do ar
        raise HTTPException(503, f"Não foi possível gerar o PDF: {e}") from e
    nome = f"{codigo} - {m['modulo_nome']} - {m['titulo']}.pdf".replace("/", "-")
    return Response(conteudo, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{pdf.quote(nome)}"})
