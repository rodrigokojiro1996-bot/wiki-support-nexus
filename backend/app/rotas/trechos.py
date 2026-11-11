"""Trechos do manual da tela ligados a uma tabela (selecionados no painel ao lado do diagrama).

Um trecho pode pegar vários blocos do manual (passos, parágrafos, observações, de uma ou mais seções). Cada bloco
vira uma linha em `manual_trechos`, e as linhas da mesma seleção dividem o `grupo` (o id da primeira): na tela, o
grupo é um trecho só.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from ..servicos import registro
from ..servicos.manuais import manual_completo
from . import db, usuario

router = APIRouter(prefix="/api/manuais/{codigo}/trechos")
CAMPOS = "id, grupo, tabela, secao, bloco, texto, versao, por, em"


class Parte(BaseModel):
    secao: int = Field(ge=1)
    bloco: int = Field(ge=0)
    texto: str = Field(min_length=1, max_length=4000)


class NovoTrecho(BaseModel):
    tabela: str = Field(min_length=1, max_length=200)
    # vários blocos (seleção que atravessa passos e parágrafos) ...
    partes: list[Parte] | None = Field(default=None, max_length=300)
    # ... ou um só, no formato de antes
    secao: int | None = Field(default=None, ge=1)
    bloco: int | None = Field(default=None, ge=0)
    texto: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def uma_forma(self):
        if self.partes is None:
            if self.secao is None or self.bloco is None or self.texto is None:
                raise ValueError("informe as partes do trecho (ou seção, bloco e texto)")
            self.partes = [Parte(secao=self.secao, bloco=self.bloco, texto=self.texto)]
        if not self.partes:
            raise ValueError("selecione um trecho do manual")
        return self


def _manual(con, codigo: str) -> dict:
    m = manual_completo(con, codigo)
    if not m:
        raise HTTPException(404, "Manual não encontrado")
    return m


def _onde(partes: list[dict]) -> str:
    """'seção 2' ou 'seções 1 a 3', e quantos blocos."""
    secoes = sorted({p["secao"] for p in partes})
    s = f"seção {secoes[0]}" if len(secoes) == 1 else f"seções {secoes[0]} a {secoes[-1]}"
    return s + (f", {len(partes)} blocos" if len(partes) > 1 else "")


def _texto(partes: list[dict], n: int = 600) -> str:
    t = " … ".join(p["texto"] for p in partes)
    return t if len(t) <= n else t[: n - 1] + "…"


@router.get("")
def listar(codigo: str, tabela: str | None = None, con=Depends(db)):
    """Trechos do manual (uma linha por bloco, com o grupo); com `tabela`, só os ligados a ela."""
    _manual(con, codigo)
    sql, args = f"SELECT {CAMPOS} FROM manual_trechos WHERE manual = ?", [codigo]
    if tabela:
        sql += " AND tabela = ?"
        args.append(tabela)
    return [dict(r) for r in con.execute(sql + " ORDER BY grupo, secao, bloco, id", args)]


@router.post("", status_code=201)
def ligar(codigo: str, corpo: NovoTrecho, con=Depends(db), por: str = Depends(usuario)):
    m = _manual(con, codigo)
    partes = []
    for p in corpo.partes:
        texto = " ".join(p.texto.split())
        if not texto:
            continue
        if p.secao > len(m["secoes"]) or p.bloco >= len(m["secoes"][p.secao - 1]["blocos"]):
            raise HTTPException(422, "O trecho não está neste manual (seção ou bloco inexistente)")
        partes.append({"secao": p.secao, "bloco": p.bloco, "texto": texto})
    if not partes:
        raise HTTPException(422, "Selecione um trecho do manual")
    banco = con.execute("SELECT banco FROM modulos WHERE id = ?", (m["modulo"],)).fetchone()
    if not banco or not con.execute("SELECT 1 FROM tabelas WHERE banco = ? AND nome = ?", (banco["banco"], corpo.tabela)).fetchone():
        raise HTTPException(422, f"A tabela {corpo.tabela} não existe no banco deste módulo")
    if all(con.execute("SELECT 1 FROM manual_trechos WHERE manual = ? AND tabela = ? AND secao = ? AND bloco = ? AND texto = ?",
                       (codigo, corpo.tabela, p["secao"], p["bloco"], p["texto"])).fetchone() for p in partes):
        raise HTTPException(409, "Este trecho já está ligado a esta tabela")
    grupo = None
    for p in partes:
        cur = con.execute("INSERT INTO manual_trechos (manual, tabela, secao, bloco, texto, versao, por, grupo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                          (codigo, corpo.tabela, p["secao"], p["bloco"], p["texto"], m["versao"], por, grupo))
        if grupo is None:
            grupo = cur.lastrowid
            con.execute("UPDATE manual_trechos SET grupo = ? WHERE id = ?", (grupo, grupo))
    registro.registrar(con, por, "validou", "trecho", f"Validou que o trecho do manual {codigo} ({_onde(partes)}, versão {m['versao']}) "
                       f"corresponde à tabela {corpo.tabela}: “{_texto(partes)}”", alvo=f"{codigo} · {corpo.tabela}", modulo=m["modulo"],
                       detalhe={"manual": codigo, "tabela": corpo.tabela, "partes": partes})
    con.commit()
    linhas = [dict(r) for r in con.execute(f"SELECT {CAMPOS} FROM manual_trechos WHERE grupo = ? ORDER BY id", (grupo,))]
    return {**linhas[0], "partes": linhas}


@router.delete("/{trecho_id}")
def desligar(codigo: str, trecho_id: int, con=Depends(db), por: str = Depends(usuario)):
    """Desliga o trecho inteiro (todas as partes do grupo do `trecho_id`)."""
    t = con.execute("SELECT * FROM manual_trechos WHERE manual = ? AND id = ?", (codigo, trecho_id)).fetchone()
    if not t:
        raise HTTPException(404, "Trecho não encontrado")
    grupo = t["grupo"] or t["id"]
    partes = [dict(r) for r in con.execute("SELECT secao, bloco, texto FROM manual_trechos WHERE manual = ? AND (grupo = ? OR id = ?) ORDER BY id",
                                           (codigo, grupo, grupo))]
    con.execute("DELETE FROM manual_trechos WHERE manual = ? AND (grupo = ? OR id = ?)", (codigo, grupo, grupo))
    m = con.execute("SELECT modulo FROM manuais WHERE codigo = ?", (codigo,)).fetchone()
    registro.registrar(con, por, "excluiu", "trecho", f"Desligou o trecho do manual {codigo} ({_onde(partes)}) da tabela {t['tabela']}: "
                       f"“{_texto(partes)}” (tinha sido validado por {t['por'] or 'alguém sem nome'})", alvo=f"{codigo} · {t['tabela']}",
                       modulo=m["modulo"] if m else "",
                       detalhe={"tabela": t["tabela"], "partes": partes, "versao": t["versao"], "por": t["por"], "em": t["em"]})
    con.commit()
    return {"ok": True}
