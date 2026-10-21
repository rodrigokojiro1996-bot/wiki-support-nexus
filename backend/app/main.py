"""Support Nexus · API.

Rodar (dentro de backend/):
    .venv\\Scripts\\uvicorn app.main:app --reload --port 8010
"""
import json
import sqlite3
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import pdf
from .config import pasta_conteudo
from .db import caminho_menu, conectar

app = FastAPI(title="Support Nexus", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])

# prints dos manuais: backend/dados/imagens (real) ou backend/seed/imagens (exemplo) → /api/imagens/<código>/<arquivo>
IMAGENS = pasta_conteudo("imagens")
IMAGENS.mkdir(parents=True, exist_ok=True)
app.mount("/api/imagens", StaticFiles(directory=IMAGENS), name="imagens")


def db():
    con = conectar()
    try:
        yield con
    finally:
        con.close()


def banco_do_modulo(con: sqlite3.Connection, modulo: str) -> str | None:
    r = con.execute("SELECT banco FROM modulos WHERE id = ?", (modulo,)).fetchone()
    if not r:
        raise HTTPException(404, f"Módulo {modulo} não existe")
    return r["banco"]


def relacao_dict(r: sqlite3.Row) -> dict:
    estado = "confirmada" if r["tipo"] == "fk" else (r["status"] or "sugerida")
    return {"id": r["id"], "origem": r["origem"], "destino": r["destino"], "colunas": json.loads(r["colunas"]),
            "estado": estado, "regra": r["regra"], "motivo": r["motivo"]}


SQL_RELACOES = """SELECT r.*, s.status FROM relacoes r
                  LEFT JOIN relacao_status s ON s.banco = r.banco AND s.id = r.id
                  WHERE r.banco = ?"""


# ---------------- módulos e menus ----------------
@app.get("/api/modulos")
def modulos(con=Depends(db)):
    return [dict(r) for r in con.execute("""SELECT m.*, i.em AS catalogo_em, i.resumo AS catalogo_resumo
                                           FROM modulos m LEFT JOIN importacoes i ON i.banco = m.banco ORDER BY m.rowid""")]


@app.get("/api/modulos/{modulo}/menus")
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


@app.get("/api/menus/{menu_id}")
def menu(menu_id: str, con=Depends(db)):
    r = con.execute("SELECT * FROM menus WHERE id = ?", (menu_id,)).fetchone()
    if not r:
        raise HTTPException(404, "Item de menu não encontrado")
    banco = banco_do_modulo(con, r["modulo"])
    tabelas = [dict(t) for t in con.execute("""SELECT mt.tabela, mt.origem, t.engine, t.linhas, t.descricao, (t.nome IS NOT NULL) AS existe
                                              FROM menu_tabelas mt LEFT JOIN tabelas t ON t.banco = ? AND t.nome = mt.tabela
                                              WHERE mt.menu = ? ORDER BY mt.tabela""", (banco, menu_id))]
    nomes = [t["tabela"] for t in tabelas]
    relacoes = []
    if nomes:
        marca = ",".join("?" * len(nomes))
        relacoes = [relacao_dict(x) for x in con.execute(SQL_RELACOES + f" AND (r.origem IN ({marca}) OR r.destino IN ({marca}))", (banco, *nomes, *nomes))]
    manuais = [dict(m) for m in con.execute("SELECT codigo, titulo, subtitulo, versao, atualizado_em FROM manuais WHERE menu = ? ORDER BY codigo", (menu_id,))]
    filhos = [dict(f) for f in con.execute("SELECT id, titulo, atalho FROM menus WHERE pai = ? ORDER BY ordem", (menu_id,))]
    return {**dict(r), "desabilitado": bool(r["desabilitado"]), "banco": banco, "caminho": caminho_menu(con, menu_id),
            "tabelas": tabelas, "relacoes": [x for x in relacoes if x["estado"] != "descartada"], "manuais": manuais, "filhos": filhos}


class VinculoTabelas(BaseModel):
    tabelas: list[str]


@app.put("/api/menus/{menu_id}/tabelas")
def salvar_tabelas(menu_id: str, corpo: VinculoTabelas, con=Depends(db)):
    if not con.execute("SELECT 1 FROM menus WHERE id = ?", (menu_id,)).fetchone():
        raise HTTPException(404, "Item de menu não encontrado")
    atuais = {r["tabela"]: r["origem"] for r in con.execute("SELECT tabela, origem FROM menu_tabelas WHERE menu = ?", (menu_id,))}
    con.execute("DELETE FROM menu_tabelas WHERE menu = ?", (menu_id,))
    # o que a equipe manteve ou adicionou passa a ser vínculo da equipe
    con.executemany("INSERT INTO menu_tabelas (menu, tabela, origem) VALUES (?, ?, 'equipe')", [(menu_id, t) for t in dict.fromkeys(corpo.tabelas)])
    con.commit()
    return {"ok": True, "antes": atuais}


# ---------------- catálogo do banco ----------------
@app.get("/api/modulos/{modulo}/catalogo")
def catalogo(modulo: str, con=Depends(db)):
    """Tabelas e relações para o grafo (sem colunas, para ficar leve)."""
    banco = banco_do_modulo(con, modulo)
    tabelas = [dict(t) for t in con.execute("SELECT nome, engine, linhas, descricao FROM tabelas WHERE banco = ? ORDER BY nome", (banco,))]
    relacoes = [relacao_dict(r) for r in con.execute(SQL_RELACOES, (banco,))]
    return {"banco": banco, "tabelas": tabelas, "relacoes": relacoes}


APOIO_MINIMO = 40  # tabelas referenciadas por tantas outras (empresas, usuarios…) ficam ocultas por padrão


@app.get("/api/modulos/{modulo}/diagrama")
def diagrama(modulo: str, tabelas: str, nivel: int = 1, apoio: bool = False, con=Depends(db)):
    """Diagrama ER em volta das tabelas de uma tela: as tabelas da tela, as vizinhas até `nivel` e as ligações entre todas."""
    banco = banco_do_modulo(con, modulo)
    existentes = {r["nome"] for r in con.execute("SELECT nome FROM tabelas WHERE banco = ?", (banco,))}
    foco = [t for t in dict.fromkeys(tabelas.split(",")) if t in existentes]
    rels = [x for x in (relacao_dict(r) for r in con.execute(SQL_RELACOES, (banco,))) if x["estado"] != "descartada"]
    grau = {}
    for r in rels:
        grau[r["destino"]] = grau.get(r["destino"], 0) + 1
    apoio_tab = {t for t, n in grau.items() if n >= APOIO_MINIMO}
    incluidas, fronteira, apoio_ocultas = set(foco), set(foco), set()
    for _ in range(max(0, min(nivel, 3))):
        nova = set()
        for r in rels:
            for a, b in ((r["origem"], r["destino"]), (r["destino"], r["origem"])):
                # a expansão não passa por tabelas de apoio (clientes, usuarios…): elas trariam dezenas de vizinhas
                if a in fronteira and b not in incluidas and (apoio or a not in apoio_tab):
                    if b in apoio_tab and not apoio:
                        apoio_ocultas.add(b)
                    else:
                        nova.add(b)
        incluidas |= nova
        fronteira = nova
    # limite para o diagrama continuar legível: mantém as mais conectadas ao foco
    if len(incluidas) > 40:
        conexoes = {t: sum(1 for r in rels if {r["origem"], r["destino"]} & set(foco) and t in (r["origem"], r["destino"])) for t in incluidas}
        incluidas = set(foco) | set(sorted(incluidas - set(foco), key=lambda t: -conexoes[t])[: max(0, 40 - len(foco))])
    arestas = [r for r in rels if r["origem"] in incluidas and r["destino"] in incluidas]
    saida = []
    for nome in sorted(incluidas):
        t = con.execute("SELECT engine, linhas FROM tabelas WHERE banco = ? AND nome = ?", (banco, nome)).fetchone()
        cols = [{"nome": c["nome"], "tipo": c["tipo"], "pk": bool(c["pk"])} for c in con.execute(
            "SELECT nome, tipo, pk FROM colunas WHERE banco = ? AND tabela = ? ORDER BY ordem", (banco, nome))]
        saida.append({"nome": nome, "engine": t["engine"], "linhas": t["linhas"], "foco": nome in foco, "apoio": nome in apoio_tab, "colunas": cols})
    return {"foco": foco, "tabelas": saida, "relacoes": arestas, "apoio_ocultas": sorted(apoio_ocultas - incluidas)}


@app.get("/api/modulos/{modulo}/tabelas/{nome}")
def tabela(modulo: str, nome: str, con=Depends(db)):
    banco = banco_do_modulo(con, modulo)
    t = con.execute("SELECT * FROM tabelas WHERE banco = ? AND nome = ?", (banco, nome)).fetchone()
    if not t:
        raise HTTPException(404, f"Tabela {nome} não existe em {banco}")
    colunas = [dict(c) | {"pk": bool(c["pk"])} for c in con.execute("SELECT nome, tipo, pk FROM colunas WHERE banco = ? AND tabela = ? ORDER BY ordem", (banco, nome))]
    relacoes = [relacao_dict(r) for r in con.execute(SQL_RELACOES + " AND (r.origem = ? OR r.destino = ?)", (banco, nome, nome))]
    menus = [{"id": m["menu"], "caminho": caminho_menu(con, m["menu"])} for m in con.execute("SELECT menu FROM menu_tabelas WHERE tabela = ?", (nome,))]
    manuais = [dict(m) for m in con.execute("SELECT codigo, titulo FROM manuais WHERE modulo = ? AND tabelas LIKE ?", (modulo, f'%"{nome}"%'))]
    return {**dict(t), "colunas": colunas, "relacoes": relacoes, "menus": menus, "manuais": manuais}


class StatusRelacao(BaseModel):
    id: str
    status: Literal["documentada", "descartada", "sugerida"]
    observacao: str = ""


@app.put("/api/modulos/{modulo}/relacoes/status")
def status_relacao(modulo: str, corpo: StatusRelacao, con=Depends(db)):
    banco = banco_do_modulo(con, modulo)
    if not con.execute("SELECT 1 FROM relacoes WHERE banco = ? AND id = ?", (banco, corpo.id)).fetchone():
        raise HTTPException(404, "Relação não encontrada")
    if corpo.status == "sugerida":
        con.execute("DELETE FROM relacao_status WHERE banco = ? AND id = ?", (banco, corpo.id))
    else:
        con.execute("""INSERT INTO relacao_status (banco, id, status, observacao) VALUES (?, ?, ?, ?)
                       ON CONFLICT(banco, id) DO UPDATE SET status = excluded.status, observacao = excluded.observacao, em = datetime('now', 'localtime')""",
                    (banco, corpo.id, corpo.status, corpo.observacao))
    con.commit()
    return {"ok": True}


# ---------------- manuais ----------------
def manual_completo(con: sqlite3.Connection, codigo: str) -> dict:
    m = con.execute("SELECT m.*, mo.nome AS modulo_nome FROM manuais m JOIN modulos mo ON mo.id = m.modulo WHERE codigo = ?", (codigo,)).fetchone()
    if not m:
        raise HTTPException(404, "Manual não encontrado")
    return {**dict(m), "secoes": json.loads(m["conteudo"]), "tabelas": json.loads(m["tabelas"]), "conteudo": None,
            "fontes": json.loads(m["fontes"] or "[]"),
            "caminho": caminho_menu(con, m["menu"]) if m["menu"] else []}


@app.get("/api/manuais")
def manuais(modulo: str | None = None, con=Depends(db)):
    sql = "SELECT codigo, titulo, subtitulo, versao, modulo, menu, atualizado_em FROM manuais"
    args = ()
    if modulo:
        sql += " WHERE modulo = ?"
        args = (modulo,)
    return [dict(m) for m in con.execute(sql + " ORDER BY codigo", args)]


@app.get("/api/manuais/{codigo}")
def manual(codigo: str, con=Depends(db)):
    return manual_completo(con, codigo)


@app.get("/api/manuais/{codigo}/pdf")
def manual_pdf(codigo: str, con=Depends(db)):
    m = manual_completo(con, codigo)
    try:
        conteudo = pdf.gerar(codigo)
    except Exception as e:  # sem Edge/Chromium ou frontend fora do ar
        raise HTTPException(503, f"Não foi possível gerar o PDF: {e}") from e
    nome = f"{codigo} - {m['modulo_nome']} - {m['titulo']}.pdf".replace("/", "-")
    return Response(conteudo, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{pdf.quote(nome)}"})
