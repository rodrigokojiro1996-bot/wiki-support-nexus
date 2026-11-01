from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

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
    # uma consulta para as tabelas e uma para as colunas (não duas por tabela)
    nomes = sorted(rec.incluidas)
    marca = ",".join("?" * len(nomes))
    info = {t["nome"]: t for t in con.execute(f"SELECT nome, engine, linhas FROM tabelas WHERE banco = ? AND nome IN ({marca})", (banco, *nomes))}
    colunas: dict[str, list[dict]] = {n: [] for n in nomes}
    for c in con.execute(f"SELECT tabela, nome, tipo, pk FROM colunas WHERE banco = ? AND tabela IN ({marca}) ORDER BY tabela, ordem", (banco, *nomes)):
        colunas[c["tabela"]].append({"nome": c["nome"], "tipo": c["tipo"], "pk": bool(c["pk"])})
    saida = [{"nome": n, "engine": info[n]["engine"], "linhas": info[n]["linhas"], "foco": n in foco, "apoio": n in rec.apoio, "colunas": colunas[n]}
             for n in nomes]
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


class NovaRelacao(BaseModel):
    origem: str = Field(min_length=1)          # tabela com a chave estrangeira (lado N)
    coluna_origem: str = Field(min_length=1)
    destino: str = Field(min_length=1)         # tabela referenciada (lado 1)
    coluna_destino: str = Field(min_length=1)
    observacao: str = Field("", max_length=500)


@router.post("/relacoes", status_code=201)
def ligar_colunas(modulo: str, corpo: NovaRelacao, con=Depends(db), por: str = Depends(usuario)):
    """Relação validada pela equipe no diagrama (duas colunas de tabelas diferentes)."""
    banco = banco_do_modulo(con, modulo)
    try:
        return relacoes.ligar(con, banco, corpo.origem, corpo.coluna_origem, corpo.destino, corpo.coluna_destino,
                              por, corpo.observacao.strip())
    except relacoes.LigacaoExistente as e:
        raise HTTPException(409, str(e)) from e
    except relacoes.LigacaoInvalida as e:
        raise HTTPException(422, str(e)) from e


@router.put("/relacoes/status")
def status_relacao(modulo: str, corpo: StatusRelacao, con=Depends(db), por: str = Depends(usuario)):
    banco = banco_do_modulo(con, modulo)
    rel = relacoes.existe(con, banco, corpo.id)
    if not rel:
        raise HTTPException(404, "Relação não encontrada")
    if corpo.status == "sugerida":
        con.execute("DELETE FROM relacao_status WHERE banco = ? AND id = ?", (banco, corpo.id))
        if rel["tipo"] == "equipe":  # ligada à mão no diagrama: desfazer apaga a ligação (não vira sugestão)
            con.execute("DELETE FROM relacoes_equipe WHERE banco = ? AND id = ?", (banco, corpo.id))
    else:
        con.execute("""INSERT INTO relacao_status (banco, id, status, observacao, por) VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(banco, id) DO UPDATE SET status = excluded.status, observacao = excluded.observacao,
                       por = excluded.por, em = datetime('now', 'localtime')""",
                    (banco, corpo.id, corpo.status, corpo.observacao, por))
    con.commit()
    return {"ok": True}
