from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..db import caminho_menu
from ..servicos import descricoes, registro, relacoes
from ..servicos.diagrama import recortar
from . import banco_do_modulo, db, usuario

router = APIRouter(prefix="/api/modulos/{modulo}")


@router.get("/catalogo")
def catalogo(modulo: str, con=Depends(db)):
    """Tabelas e relações para o grafo (sem colunas, para ficar leve)."""
    banco = banco_do_modulo(con, modulo)
    desc = descricoes.das_tabelas(con, modulo)
    tabelas = [dict(t) | {"descricao": desc.get(t["nome"], "")}
               for t in con.execute("SELECT nome, engine, linhas FROM tabelas WHERE banco = ? ORDER BY nome", (banco,))]
    return {"banco": banco, "tabelas": tabelas, "relacoes": relacoes.listar(con, banco)}


@router.get("/tabelas")
def tabelas_do_modulo(modulo: str, con=Depends(db)):
    """Nome e descrição de todas as tabelas do módulo (a busca do "Adicionar tabela" do diagrama)."""
    banco = banco_do_modulo(con, modulo)
    desc = descricoes.das_tabelas(con, modulo)
    return [{"nome": t["nome"], "descricao": desc.get(t["nome"], "")}
            for t in con.execute("SELECT nome FROM tabelas WHERE banco = ? ORDER BY nome", (banco,))]


def _migrar_chave(con, modulo: str, tabelas: str, chave: str | None) -> str:
    """A organização era guardada pela lista de tabelas da tela; passa a ser pela tela. Na primeira vez que a tela
    abre com a chave nova, o que estava guardado pela lista vai para ela (nada se perde)."""
    if not chave or chave == tabelas:
        return tabelas
    tem = any(con.execute(f"SELECT 1 FROM {t} WHERE modulo = ? AND chave = ? LIMIT 1", (modulo, chave)).fetchone()
              for t in ("posicoes_diagrama", "diagrama_tabelas"))
    if not tem:
        mexeu = 0
        for t in ("posicoes_diagrama", "diagrama_tabelas"):
            mexeu += con.execute(f"UPDATE {t} SET chave = ? WHERE modulo = ? AND chave = ?", (chave, modulo, tabelas)).rowcount
        if mexeu:
            con.commit()
    return chave


@router.get("/diagrama")
def diagrama(modulo: str, tabelas: str, nivel: int = 1, apoio: bool = False, chave: str | None = None, con=Depends(db)):
    """Diagrama ER em volta das tabelas de uma tela: as tabelas da tela, as vizinhas até `nivel` e as ligações entre todas.

    `chave` (o id da tela): onde fica o que a equipe organizou (posições e tabelas adicionadas), para a organização
    sobreviver a vincular ou desvincular tabelas. Sem ela, vale a lista de tabelas, como antes.
    """
    banco = banco_do_modulo(con, modulo)
    chave = _migrar_chave(con, modulo, tabelas, chave)
    existentes = {r["nome"] for r in con.execute("SELECT nome FROM tabelas WHERE banco = ?", (banco,))}
    foco = [t for t in dict.fromkeys(tabelas.split(",")) if t in existentes]
    rels = [x for x in relacoes.listar(con, banco) if x["estado"] != "descartada"]
    rec = recortar(foco, rels, nivel, apoio)
    # tabelas que a equipe adicionou à mão nesta tela: entram sempre, com as ligações delas com as que já estão
    extras = [r["tabela"] for r in con.execute(
        "SELECT tabela FROM diagrama_tabelas WHERE modulo = ? AND chave = ? ORDER BY em, tabela", (modulo, chave))
        if r["tabela"] in existentes]
    if set(extras) - rec.incluidas:
        rec.incluidas |= set(extras)
        rec.arestas = [r for r in rels if r["origem"] in rec.incluidas and r["destino"] in rec.incluidas]
        rec.apoio_ocultas = [t for t in rec.apoio_ocultas if t not in rec.incluidas]
    # uma consulta para as tabelas e uma para as colunas (não duas por tabela)
    nomes = sorted(rec.incluidas)
    marca = ",".join("?" * len(nomes))
    info = {t["nome"]: t for t in con.execute(f"SELECT nome, engine, linhas FROM tabelas WHERE banco = ? AND nome IN ({marca})", (banco, *nomes))}
    colunas: dict[str, list[dict]] = {n: [] for n in nomes}
    for c in con.execute(f"SELECT tabela, nome, tipo, pk FROM colunas WHERE banco = ? AND tabela IN ({marca}) ORDER BY tabela, ordem", (banco, *nomes)):
        colunas[c["tabela"]].append({"nome": c["nome"], "tipo": c["tipo"], "pk": bool(c["pk"])})
    # o balão do diagrama: o que a tabela e cada coluna guardam (dicionário de dados da equipe); só vai quando existe
    desc_t, desc_c = descricoes.das_tabelas(con, modulo), descricoes.das_colunas(con, modulo, banco, nomes)
    for n in nomes:
        for c in colunas[n]:
            if (n, c["nome"]) in desc_c:
                c["descricao"] = desc_c[(n, c["nome"])]
    # o balão da tabela: as telas deste módulo que a usam (o FIN e o ADM dividem o banco, por isso o filtro do módulo)
    telas: dict[str, list[list[str]]] = {n: [] for n in nomes}
    for m in con.execute(f"""SELECT mt.tabela, mt.menu FROM menu_tabelas mt JOIN menus m ON m.id = mt.menu
                             WHERE m.modulo = ? AND mt.tabela IN ({marca}) ORDER BY mt.menu""", (modulo, *nomes)):
        telas[m["tabela"]].append([p["titulo"] for p in caminho_menu(con, m["menu"])])
    saida = [{"nome": n, "engine": info[n]["engine"], "linhas": info[n]["linhas"], "foco": n in foco, "apoio": n in rec.apoio,
              "adicionada": n in extras and n not in foco, "descricao": desc_t.get(n, ""), "telas": telas[n], "colunas": colunas[n]} for n in nomes]
    # o que a equipe organizou: posições arrastadas desta tela e o informativo (post-it) de cada ligação
    posicoes = {r["tabela"]: {"x": r["x"], "y": r["y"]} for r in con.execute(
        "SELECT tabela, x, y FROM posicoes_diagrama WHERE modulo = ? AND chave = ?", (modulo, chave))}
    notas = {r["id"]: dict(r) for r in con.execute("SELECT id, texto, posicao, por, em FROM relacao_notas WHERE banco = ?", (banco,))}
    for r in rec.arestas:
        if r["id"] in notas:
            r["nota"] = {k: v for k, v in notas[r["id"]].items() if k != "id"}
    return {"foco": foco, "tabelas": saida, "relacoes": rec.arestas, "apoio_ocultas": rec.apoio_ocultas, "posicoes": posicoes}


class Posicao(BaseModel):
    tabela: str = Field(max_length=200)
    x: float
    y: float


class Posicoes(BaseModel):
    chave: str = Field(max_length=20000)  # as tabelas da tela, exatamente como o GET /diagrama recebe
    posicoes: list[Posicao] = Field(max_length=500)


@router.put("/diagrama/posicoes")
def salvar_posicoes(modulo: str, corpo: Posicoes, con=Depends(db), por: str = Depends(usuario)):
    """Tabelas arrastadas pela equipe: a posição vale para todos que abrirem essa tela."""
    banco_do_modulo(con, modulo)
    antes = {r["tabela"]: {"x": r["x"], "y": r["y"]} for r in con.execute(
        "SELECT tabela, x, y FROM posicoes_diagrama WHERE modulo = ? AND chave = ?", (modulo, corpo.chave))}
    con.executemany("""INSERT INTO posicoes_diagrama (modulo, chave, tabela, x, y, por) VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(modulo, chave, tabela) DO UPDATE SET x = excluded.x, y = excluded.y, por = excluded.por,
                       em = datetime('now', 'localtime')""",
                    [(modulo, corpo.chave, p.tabela, p.x, p.y, por) for p in corpo.posicoes])
    if corpo.posicoes:
        nomes = ", ".join(p.tabela for p in corpo.posicoes)
        registro.registrar(con, por, "moveu", "diagrama", f"Organizou o {registro.tela_da_chave(con, modulo, corpo.chave)}: "
                           f"mudou de lugar {nomes}", alvo=corpo.chave, modulo=modulo,
                           detalhe={p.tabela: {"antes": antes.get(p.tabela), "depois": {"x": p.x, "y": p.y}} for p in corpo.posicoes})
    con.commit()
    return {"ok": True}


class TabelaAdicionada(BaseModel):
    chave: str = Field(max_length=20000)  # as tabelas da tela, exatamente como o GET /diagrama recebe
    tabela: str = Field(min_length=1, max_length=200)
    x: float | None = None  # onde a pessoa clicou com o botão direito (coordenadas do diagrama)
    y: float | None = None


@router.post("/diagrama/tabelas", status_code=201)
def adicionar_tabela(modulo: str, corpo: TabelaAdicionada, con=Depends(db), por: str = Depends(usuario)):
    """Põe uma tabela no diagrama da tela (para todos), no ponto em que a pessoa clicou, para ligar colunas com ela."""
    banco = banco_do_modulo(con, modulo)
    if not con.execute("SELECT 1 FROM tabelas WHERE banco = ? AND nome = ?", (banco, corpo.tabela)).fetchone():
        raise HTTPException(404, f"Tabela {corpo.tabela} não existe em {banco}")
    nova = con.execute("INSERT OR IGNORE INTO diagrama_tabelas (modulo, chave, tabela, por) VALUES (?, ?, ?, ?)",
                       (modulo, corpo.chave, corpo.tabela, por)).rowcount
    if nova:
        registro.registrar(con, por, "criou", "diagrama", f"Adicionou a tabela {corpo.tabela} ao "
                           f"{registro.tela_da_chave(con, modulo, corpo.chave)}", alvo=corpo.tabela, modulo=modulo)
    if corpo.x is not None and corpo.y is not None:
        con.execute("""INSERT INTO posicoes_diagrama (modulo, chave, tabela, x, y, por) VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(modulo, chave, tabela) DO UPDATE SET x = excluded.x, y = excluded.y, por = excluded.por,
                       em = datetime('now', 'localtime')""",
                    (modulo, corpo.chave, corpo.tabela, round(corpo.x), round(corpo.y), por))
    con.commit()
    return {"ok": True}


@router.delete("/diagrama/tabelas")
def remover_tabela(modulo: str, chave: str, tabela: str, con=Depends(db), por: str = Depends(usuario)):
    """Tira do diagrama da tela uma tabela adicionada à mão (as ligações feitas com ela continuam valendo)."""
    banco_do_modulo(con, modulo)
    apagou = con.execute("DELETE FROM diagrama_tabelas WHERE modulo = ? AND chave = ? AND tabela = ?", (modulo, chave, tabela)).rowcount
    if not apagou:
        raise HTTPException(404, f"{tabela} não foi adicionada a este diagrama")
    con.execute("DELETE FROM posicoes_diagrama WHERE modulo = ? AND chave = ? AND tabela = ?", (modulo, chave, tabela))
    registro.registrar(con, por, "excluiu", "diagrama", f"Removeu a tabela {tabela} do {registro.tela_da_chave(con, modulo, chave)} "
                       "(as ligações feitas com ela continuam valendo)", alvo=tabela, modulo=modulo)
    con.commit()
    return {"ok": True}


@router.delete("/diagrama/posicoes")
def reorganizar(modulo: str, chave: str, con=Depends(db), por: str = Depends(usuario)):
    """Volta a tela ao layout automático."""
    banco_do_modulo(con, modulo)
    antes = {r["tabela"]: {"x": r["x"], "y": r["y"]} for r in con.execute(
        "SELECT tabela, x, y FROM posicoes_diagrama WHERE modulo = ? AND chave = ?", (modulo, chave))}
    con.execute("DELETE FROM posicoes_diagrama WHERE modulo = ? AND chave = ?", (modulo, chave))
    if antes:
        registro.registrar(con, por, "alterou", "diagrama", f"Reorganizou o {registro.tela_da_chave(con, modulo, chave)}: "
                           f"apagou as posições de {', '.join(sorted(antes))} e voltou ao layout automático",
                           alvo=chave, modulo=modulo, detalhe={t: {"antes": p, "depois": None} for t, p in antes.items()})
    con.commit()
    return {"ok": True}


class NotaRelacao(BaseModel):
    id: str
    texto: str | None = Field(default=None, max_length=1000)  # None: só move o post-it
    posicao: float | None = Field(default=None, ge=0, le=1)


@router.put("/relacoes/nota")
def nota_relacao(modulo: str, corpo: NotaRelacao, con=Depends(db), por: str = Depends(usuario)):
    """Informativo de incidentes de uma ligação (o post-it): o que acontece com as tabelas ligadas se o valor sumir."""
    banco = banco_do_modulo(con, modulo)
    if not relacoes.existe(con, banco, corpo.id):
        raise HTTPException(404, "Relação não encontrada")
    atual = con.execute("SELECT texto, posicao FROM relacao_notas WHERE banco = ? AND id = ?", (banco, corpo.id)).fetchone()
    texto = (corpo.texto if corpo.texto is not None else (atual["texto"] if atual else "")).strip()
    if not texto:
        raise HTTPException(422, "Escreva o informativo")
    posicao = corpo.posicao if corpo.posicao is not None else (atual["posicao"] if atual else 0.5)
    # mover não troca a autoria: só quem escreve o texto vira autor
    autor = por if corpo.texto is not None or not atual else None
    con.execute("""INSERT INTO relacao_notas (banco, id, texto, posicao, por) VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(banco, id) DO UPDATE SET texto = excluded.texto, posicao = excluded.posicao,
                   por = COALESCE(?, relacao_notas.por), em = CASE WHEN ? IS NULL THEN relacao_notas.em ELSE datetime('now', 'localtime') END""",
                (banco, corpo.id, texto, posicao, autor or "", autor, autor))
    ligacao = registro.relacao(con, banco, corpo.id)
    if not atual:
        registro.registrar(con, por, "criou", "informativo", f"Incluiu o informativo de incidentes da ligação {ligacao}: “{texto}”",
                           alvo=ligacao, modulo=modulo, detalhe={"antes": None, "depois": texto})
    elif texto != atual["texto"]:
        registro.registrar(con, por, "alterou", "informativo", f"Alterou o informativo de incidentes da ligação {ligacao}",
                           alvo=ligacao, modulo=modulo, detalhe={"antes": atual["texto"], "depois": texto})
    elif posicao != atual["posicao"]:
        registro.registrar(con, por, "moveu", "informativo", f"Moveu o post-it do informativo da ligação {ligacao} "
                           f"({round(atual['posicao'] * 100)}% → {round(posicao * 100)}% da linha)",
                           alvo=ligacao, modulo=modulo, detalhe={"antes": atual["posicao"], "depois": posicao})
    con.commit()
    r = con.execute("SELECT texto, posicao, por, em FROM relacao_notas WHERE banco = ? AND id = ?", (banco, corpo.id)).fetchone()
    return dict(r)


@router.delete("/relacoes/nota")
def apagar_nota(modulo: str, id: str, con=Depends(db), por: str = Depends(usuario)):
    banco = banco_do_modulo(con, modulo)
    atual = con.execute("SELECT texto FROM relacao_notas WHERE banco = ? AND id = ?", (banco, id)).fetchone()
    con.execute("DELETE FROM relacao_notas WHERE banco = ? AND id = ?", (banco, id))
    if atual:
        ligacao = registro.relacao(con, banco, id)
        registro.registrar(con, por, "excluiu", "informativo", f"Excluiu o informativo de incidentes da ligação {ligacao}: “{atual['texto']}”",
                           alvo=ligacao, modulo=modulo, detalhe={"antes": atual["texto"], "depois": None})
    con.commit()
    return {"ok": True}


@router.get("/tabelas/{nome}")
def tabela(modulo: str, nome: str, con=Depends(db)):
    banco = banco_do_modulo(con, modulo)
    t = con.execute("SELECT * FROM tabelas WHERE banco = ? AND nome = ?", (banco, nome)).fetchone()
    if not t:
        raise HTTPException(404, f"Tabela {nome} não existe em {banco}")
    desc_c = descricoes.das_colunas(con, modulo, banco, [nome])
    colunas = [dict(c) | {"pk": bool(c["pk"]), "descricao": desc_c.get((nome, c["nome"]), "")}
               for c in con.execute("SELECT nome, tipo, pk FROM colunas WHERE banco = ? AND tabela = ? ORDER BY ordem", (banco, nome))]
    rels = relacoes.listar(con, banco, " AND (r.origem = ? OR r.destino = ?)", (nome, nome))
    # informativos de incidentes das ligações desta tabela (os post-its do diagrama)
    notas = {r["id"]: dict(r) for r in con.execute("SELECT id, texto, posicao, por, em FROM relacao_notas WHERE banco = ?", (banco,))}
    for r in rels:
        if r["id"] in notas:
            r["nota"] = {k: v for k, v in notas[r["id"]].items() if k != "id"}
    menus = [{"id": m["menu"], "caminho": caminho_menu(con, m["menu"])} for m in con.execute("SELECT menu FROM menu_tabelas WHERE tabela = ?", (nome,))]
    manuais = [dict(m) for m in con.execute("SELECT codigo, titulo FROM manuais WHERE modulo = ? AND tabelas LIKE ?", (modulo, f'%"{nome}"%'))]
    return {**dict(t), "descricao": descricoes.das_tabelas(con, modulo).get(nome, ""), "colunas": colunas, "relacoes": rels, "menus": menus, "manuais": manuais}


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
        rel = relacoes.ligar(con, banco, corpo.origem, corpo.coluna_origem, corpo.destino, corpo.coluna_destino,
                             por, corpo.observacao.strip())
        ligacao = registro.relacao(con, banco, rel["id"])
        obs = f" · observação: “{corpo.observacao.strip()}”" if corpo.observacao.strip() else ""
        registro.registrar(con, por, "validou", "ligacao", f"Validou a ligação {ligacao} (N → 1){obs}", alvo=ligacao, modulo=modulo,
                           detalhe={"origem": f"{corpo.origem}.{corpo.coluna_origem}", "destino": f"{corpo.destino}.{corpo.coluna_destino}",
                                    "observacao": corpo.observacao.strip()})
        con.commit()
        return rel
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
    ligacao = registro.relacao(con, banco, corpo.id)
    antes = con.execute("SELECT status FROM relacao_status WHERE banco = ? AND id = ?", (banco, corpo.id)).fetchone()
    nota = con.execute("SELECT texto FROM relacao_notas WHERE banco = ? AND id = ?", (banco, corpo.id)).fetchone()
    obs = f" · observação: “{corpo.observacao.strip()}”" if corpo.observacao.strip() else ""
    detalhe = {"antes": antes["status"] if antes else ("equipe" if rel["tipo"] == "equipe" else "sugerida"), "depois": corpo.status,
               "observacao": corpo.observacao.strip()}
    if corpo.status == "documentada":
        registro.registrar(con, por, "validou", "ligacao", f"Validou (documentou) a ligação {ligacao}{obs}", alvo=ligacao, modulo=modulo, detalhe=detalhe)
    elif corpo.status == "descartada":
        registro.registrar(con, por, "descartou", "ligacao", f"Descartou a ligação sugerida {ligacao}{obs}", alvo=ligacao, modulo=modulo, detalhe=detalhe)
    elif rel["tipo"] == "equipe":
        junto = f"; o informativo “{nota['texto']}” foi excluído junto" if nota else ""
        registro.registrar(con, por, "excluiu", "ligacao", f"Desfez a ligação {ligacao}, que tinha sido ligada pela equipe{junto}",
                           alvo=ligacao, modulo=modulo, detalhe=detalhe | {"informativo": nota["texto"] if nota else None})
    elif antes:
        registro.registrar(con, por, "alterou", "ligacao", f"Voltou a ligação {ligacao} para sugerida (desfez “{antes['status']}”)",
                           alvo=ligacao, modulo=modulo, detalhe=detalhe)
    if corpo.status == "sugerida":
        con.execute("DELETE FROM relacao_status WHERE banco = ? AND id = ?", (banco, corpo.id))
        if rel["tipo"] == "equipe":  # ligada à mão no diagrama: desfazer apaga a ligação (não vira sugestão)
            con.execute("DELETE FROM relacoes_equipe WHERE banco = ? AND id = ?", (banco, corpo.id))
            con.execute("DELETE FROM relacao_notas WHERE banco = ? AND id = ?", (banco, corpo.id))
    else:
        con.execute("""INSERT INTO relacao_status (banco, id, status, observacao, por) VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(banco, id) DO UPDATE SET status = excluded.status, observacao = excluded.observacao,
                       por = excluded.por, em = datetime('now', 'localtime')""",
                    (banco, corpo.id, corpo.status, corpo.observacao, por))
    con.commit()
    return {"ok": True}
