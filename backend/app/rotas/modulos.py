from fastapi import APIRouter, Depends

from . import db

router = APIRouter(prefix="/api/modulos")


@router.get("")
def modulos(con=Depends(db)):
    return [dict(r) for r in con.execute("""SELECT m.*, i.em AS catalogo_em, i.resumo AS catalogo_resumo
                                           FROM modulos m LEFT JOIN importacoes i ON i.banco = m.banco ORDER BY m.rowid""")]


@router.get("/{modulo}/menus")
def arvore_menus(modulo: str, con=Depends(db)):
    """Árvore completa do módulo, com contagem de tabelas e manuais por item."""
    rows = con.execute("""SELECT m.*, (SELECT COUNT(*) FROM menu_tabelas t WHERE t.menu = m.id) AS n_tabelas,
                                 (SELECT COUNT(*) FROM manuais d WHERE d.menu = m.id) AS n_manuais
                          FROM menus m WHERE m.modulo = ? ORDER BY m.ordem""", (modulo,)).fetchall()
    nos = {r["id"]: {"id": r["id"], "titulo": r["titulo"], "atalho": r["atalho"], "tela_codigo": r["tela_codigo"],
                     "desabilitado": bool(r["desabilitado"]), "submenu": bool(r["submenu"]),
                     "n_tabelas": r["n_tabelas"], "n_manuais": r["n_manuais"], "itens": []} for r in rows}
    raiz = []
    for r in rows:
        (nos[r["pai"]]["itens"] if r["pai"] in nos else raiz).append(nos[r["id"]])
    return raiz
