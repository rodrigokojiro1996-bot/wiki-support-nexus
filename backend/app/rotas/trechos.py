"""Trechos do manual da tela ligados a uma tabela (selecionados no painel ao lado do diagrama)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..servicos.manuais import manual_completo
from . import db, usuario

router = APIRouter(prefix="/api/manuais/{codigo}/trechos")


class NovoTrecho(BaseModel):
    tabela: str = Field(min_length=1, max_length=200)
    secao: int = Field(ge=1)
    bloco: int = Field(ge=0)
    texto: str = Field(min_length=1, max_length=2000)


def _manual(con, codigo: str) -> dict:
    m = manual_completo(con, codigo)
    if not m:
        raise HTTPException(404, "Manual não encontrado")
    return m


@router.get("")
def listar(codigo: str, tabela: str | None = None, con=Depends(db)):
    """Trechos do manual; com `tabela`, só os ligados a ela."""
    _manual(con, codigo)
    sql, args = "SELECT id, tabela, secao, bloco, texto, versao, por, em FROM manual_trechos WHERE manual = ?", [codigo]
    if tabela:
        sql += " AND tabela = ?"
        args.append(tabela)
    return [dict(r) for r in con.execute(sql + " ORDER BY secao, bloco, id", args)]


@router.post("", status_code=201)
def ligar(codigo: str, corpo: NovoTrecho, con=Depends(db), por: str = Depends(usuario)):
    m = _manual(con, codigo)
    texto = " ".join(corpo.texto.split())
    if not texto:
        raise HTTPException(422, "Selecione um trecho do manual")
    if corpo.secao > len(m["secoes"]) or corpo.bloco >= len(m["secoes"][corpo.secao - 1]["blocos"]):
        raise HTTPException(422, "O trecho não está neste manual (seção ou bloco inexistente)")
    banco = con.execute("SELECT banco FROM modulos WHERE id = ?", (m["modulo"],)).fetchone()
    if not banco or not con.execute("SELECT 1 FROM tabelas WHERE banco = ? AND nome = ?", (banco["banco"], corpo.tabela)).fetchone():
        raise HTTPException(422, f"A tabela {corpo.tabela} não existe no banco deste módulo")
    if con.execute("SELECT 1 FROM manual_trechos WHERE manual = ? AND tabela = ? AND secao = ? AND bloco = ? AND texto = ?",
                   (codigo, corpo.tabela, corpo.secao, corpo.bloco, texto)).fetchone():
        raise HTTPException(409, "Este trecho já está ligado a esta tabela")
    cur = con.execute("INSERT INTO manual_trechos (manual, tabela, secao, bloco, texto, versao, por) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (codigo, corpo.tabela, corpo.secao, corpo.bloco, texto, m["versao"], por))
    con.commit()
    return dict(con.execute("SELECT id, tabela, secao, bloco, texto, versao, por, em FROM manual_trechos WHERE id = ?",
                            (cur.lastrowid,)).fetchone())


@router.delete("/{trecho_id}")
def desligar(codigo: str, trecho_id: int, con=Depends(db)):
    if not con.execute("DELETE FROM manual_trechos WHERE manual = ? AND id = ?", (codigo, trecho_id)).rowcount:
        raise HTTPException(404, "Trecho não encontrado")
    con.commit()
    return {"ok": True}
