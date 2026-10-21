from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db import caminho_menu
from ..servicos import relacoes
from . import banco_do_modulo, db

router = APIRouter(prefix="/api/menus")


@router.get("/{menu_id}")
def menu(menu_id: str, con=Depends(db)):
    r = con.execute("SELECT * FROM menus WHERE id = ?", (menu_id,)).fetchone()
    if not r:
        raise HTTPException(404, "Item de menu não encontrado")
    banco = banco_do_modulo(con, r["modulo"])
    tabelas = [dict(t) for t in con.execute("""SELECT mt.tabela, mt.origem, t.engine, t.linhas, t.descricao, (t.nome IS NOT NULL) AS existe
                                              FROM menu_tabelas mt LEFT JOIN tabelas t ON t.banco = ? AND t.nome = mt.tabela
                                              WHERE mt.menu = ? ORDER BY mt.tabela""", (banco, menu_id))]
    nomes = [t["tabela"] for t in tabelas]
    rels = []
    if nomes:
        marca = ",".join("?" * len(nomes))
        rels = relacoes.listar(con, banco, f" AND (r.origem IN ({marca}) OR r.destino IN ({marca}))", (*nomes, *nomes))
    manuais = [dict(m) for m in con.execute("SELECT codigo, titulo, subtitulo, versao, atualizado_em FROM manuais WHERE menu = ? ORDER BY codigo", (menu_id,))]
    filhos = [dict(f) for f in con.execute("SELECT id, titulo, atalho FROM menus WHERE pai = ? ORDER BY ordem", (menu_id,))]
    return {**dict(r), "desabilitado": bool(r["desabilitado"]), "banco": banco, "caminho": caminho_menu(con, menu_id),
            "tabelas": tabelas, "relacoes": [x for x in rels if x["estado"] != "descartada"], "manuais": manuais, "filhos": filhos}


class VinculoTabelas(BaseModel):
    tabelas: list[str]


@router.put("/{menu_id}/tabelas")
def salvar_tabelas(menu_id: str, corpo: VinculoTabelas, con=Depends(db)):
    if not con.execute("SELECT 1 FROM menus WHERE id = ?", (menu_id,)).fetchone():
        raise HTTPException(404, "Item de menu não encontrado")
    atuais = {r["tabela"]: r["origem"] for r in con.execute("SELECT tabela, origem FROM menu_tabelas WHERE menu = ?", (menu_id,))}
    con.execute("DELETE FROM menu_tabelas WHERE menu = ?", (menu_id,))
    # o que a equipe manteve ou adicionou passa a ser vínculo da equipe
    con.executemany("INSERT INTO menu_tabelas (menu, tabela, origem) VALUES (?, ?, 'equipe')", [(menu_id, t) for t in dict.fromkeys(corpo.tabelas)])
    con.commit()
    return {"ok": True, "antes": atuais}
