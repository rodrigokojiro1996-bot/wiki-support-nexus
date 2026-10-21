from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db import caminho_menu
from ..servicos import relacoes
from ..servicos.diagrama import recortar
from . import banco_do_modulo, db, usuario

router = APIRouter(prefix="/api/modulos/{modulo}")


@router.get("/catalogo")
def catalogo(modulo: str, con=Depends(db)):
    """Tabelas e relações para o grafo (sem colunas, para ficar leve)."""
    banco = banco_do_modulo(con, modulo)
    tabelas = [dict(t) for t in con.execute("SELECT nome, engine, linhas, descricao FROM tabelas WHERE banco = ? ORDER BY nome", (banco,))]
    return {"banco": banco, "tabelas": tabelas, "relacoes": relacoes.listar(con, banco)}


@router.get("/diagrama")
def diagrama(modulo: str, tabelas: str, nivel: int = 1, apoio: bool = False, con=Depends(db)):
    """Diagrama ER em volta das tabelas de uma tela: as tabelas da tela, as vizinhas até `nivel` e as ligações entre todas."""
    banco = banco_do_modulo(con, modulo)
    existentes = {r["nome"] for r in con.execute("SELECT nome FROM tabelas WHERE banco = ?", (banco,))}
    foco = [t for t in dict.fromkeys(tabelas.split(",")) if t in existentes]
    rels = [x for x in relacoes.listar(con, banco) if x["estado"] != "descartada"]
    rec = recortar(foco, rels, nivel, apoio)
    saida = []
    for nome in sorted(rec.incluidas):
        t = con.execute("SELECT engine, linhas FROM tabelas WHERE banco = ? AND nome = ?", (banco, nome)).fetchone()
        cols = [{"nome": c["nome"], "tipo": c["tipo"], "pk": bool(c["pk"])} for c in con.execute(
            "SELECT nome, tipo, pk FROM colunas WHERE banco = ? AND tabela = ? ORDER BY ordem", (banco, nome))]
        saida.append({"nome": nome, "engine": t["engine"], "linhas": t["linhas"], "foco": nome in foco, "apoio": nome in rec.apoio, "colunas": cols})
    return {"foco": foco, "tabelas": saida, "relacoes": rec.arestas, "apoio_ocultas": rec.apoio_ocultas}


@router.get("/tabelas/{nome}")
def tabela(modulo: str, nome: str, con=Depends(db)):
    banco = banco_do_modulo(con, modulo)
    t = con.execute("SELECT * FROM tabelas WHERE banco = ? AND nome = ?", (banco, nome)).fetchone()
    if not t:
        raise HTTPException(404, f"Tabela {nome} não existe em {banco}")
    colunas = [dict(c) | {"pk": bool(c["pk"])} for c in con.execute("SELECT nome, tipo, pk FROM colunas WHERE banco = ? AND tabela = ? ORDER BY ordem", (banco, nome))]
    rels = relacoes.listar(con, banco, " AND (r.origem = ? OR r.destino = ?)", (nome, nome))
    menus = [{"id": m["menu"], "caminho": caminho_menu(con, m["menu"])} for m in con.execute("SELECT menu FROM menu_tabelas WHERE tabela = ?", (nome,))]
    manuais = [dict(m) for m in con.execute("SELECT codigo, titulo FROM manuais WHERE modulo = ? AND tabelas LIKE ?", (modulo, f'%"{nome}"%'))]
    return {**dict(t), "colunas": colunas, "relacoes": rels, "menus": menus, "manuais": manuais}


class StatusRelacao(BaseModel):
    id: str
    status: Literal["documentada", "descartada", "sugerida"]
    observacao: str = ""


@router.put("/relacoes/status")
def status_relacao(modulo: str, corpo: StatusRelacao, con=Depends(db), por: str = Depends(usuario)):
    banco = banco_do_modulo(con, modulo)
    if not con.execute("SELECT 1 FROM relacoes WHERE banco = ? AND id = ?", (banco, corpo.id)).fetchone():
        raise HTTPException(404, "Relação não encontrada")
    if corpo.status == "sugerida":
        con.execute("DELETE FROM relacao_status WHERE banco = ? AND id = ?", (banco, corpo.id))
    else:
        con.execute("""INSERT INTO relacao_status (banco, id, status, observacao, por) VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(banco, id) DO UPDATE SET status = excluded.status, observacao = excluded.observacao,
                       por = excluded.por, em = datetime('now', 'localtime')""",
                    (banco, corpo.id, corpo.status, corpo.observacao, por))
    con.commit()
    return {"ok": True}
