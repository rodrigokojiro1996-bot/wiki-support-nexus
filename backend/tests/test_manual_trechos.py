"""Trechos do manual da tela ligados a uma tabela, e os informativos das ligações na ficha da tabela."""
from app import seed

EU = {"X-Usuario": "Ana%20Lima"}


def um_manual(con):
    """Um manual do exemplo com uma tabela do banco do módulo dele."""
    m = con.execute("SELECT codigo, modulo FROM manuais ORDER BY codigo LIMIT 1").fetchone()
    banco = con.execute("SELECT banco FROM modulos WHERE id = ?", (m["modulo"],)).fetchone()[0]
    tabela = con.execute("SELECT nome FROM tabelas WHERE banco = ? ORDER BY nome LIMIT 1", (banco,)).fetchone()[0]
    return m["codigo"], m["modulo"], tabela


def test_ligar_listar_e_desligar_trecho(cliente, con):
    codigo, _, tabela = um_manual(con)
    url = f"/api/manuais/{codigo}/trechos"
    r = cliente.post(url, json={"tabela": tabela, "secao": 1, "bloco": 0, "texto": "  Abra   a tela\n de clientes "}, headers=EU)
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["texto"] == "Abra a tela de clientes" and t["por"] == "Ana Lima" and t["versao"]
    assert [x["id"] for x in cliente.get(url, params={"tabela": tabela}).json()] == [t["id"]]
    assert cliente.get(url, params={"tabela": "outra"}).json() == []
    # o mesmo trecho de novo: recusado; sobrevive a reimportar o catálogo e os manuais
    assert cliente.post(url, json={"tabela": tabela, "secao": 1, "bloco": 0, "texto": "Abra a tela de clientes"}).status_code == 409
    seed.main()
    assert len(cliente.get(url).json()) == 1
    assert cliente.delete(f"{url}/{t['id']}").status_code == 200
    assert cliente.get(url).json() == []
    assert cliente.delete(f"{url}/{t['id']}").status_code == 404


def test_trecho_recusa_secao_bloco_tabela_e_manual_inexistentes(cliente, con):
    codigo, _, tabela = um_manual(con)
    url = f"/api/manuais/{codigo}/trechos"
    assert cliente.post(url, json={"tabela": tabela, "secao": 99, "bloco": 0, "texto": "x"}).status_code == 422
    assert cliente.post(url, json={"tabela": tabela, "secao": 1, "bloco": 999, "texto": "x"}).status_code == 422
    assert cliente.post(url, json={"tabela": "nao_existe", "secao": 1, "bloco": 0, "texto": "x"}).status_code == 422
    assert cliente.post(url, json={"tabela": tabela, "secao": 1, "bloco": 0, "texto": "   "}).status_code == 422
    assert cliente.post("/api/manuais/NADA.999/trechos", json={"tabela": tabela, "secao": 1, "bloco": 0, "texto": "x"}).status_code == 404


def test_ficha_da_tabela_traz_o_informativo_das_ligacoes(cliente):
    rel = cliente.get("/api/modulos/pdv/diagrama", params={"tabelas": "vendas"}).json()["relacoes"][0]
    cliente.put("/api/modulos/pdv/relacoes/nota", json={"id": rel["id"], "texto": "Apagar o cliente quebra a venda"})
    ficha = cliente.get(f"/api/modulos/pdv/tabelas/{rel['origem']}").json()
    assert next(r for r in ficha["relacoes"] if r["id"] == rel["id"])["nota"]["texto"] == "Apagar o cliente quebra a venda"


def test_trecho_de_varios_blocos_e_um_trecho_so(cliente, con):
    """Seleção que atravessa passos e seções: uma linha por bloco, mesmo grupo; desliga tudo de uma vez."""
    codigo, _, tabela = um_manual(con)
    m = cliente.get(f"/api/manuais/{codigo}").json()
    pos = [(s + 1, b) for s, sec in enumerate(m["secoes"]) for b in range(len(sec["blocos"]))]
    assert len({s for s, _ in pos}) >= 2, "o exemplo precisa de um manual com 2 seções"
    escolhidos = [pos[0], pos[1], next(p for p in pos if p[0] == 2)]
    partes = [{"secao": s, "bloco": b, "texto": f"parte {i}  do\n trecho"} for i, (s, b) in enumerate(escolhidos)]
    url = f"/api/manuais/{codigo}/trechos"
    r = cliente.post(url, json={"tabela": tabela, "partes": partes + [{"secao": 1, "bloco": 0, "texto": "   "}]}, headers=EU)
    assert r.status_code == 201, r.text
    t = r.json()
    assert len(t["partes"]) == 3 and {p["grupo"] for p in t["partes"]} == {t["id"]}
    assert [p["texto"] for p in t["partes"]] == ["parte 0 do trecho", "parte 1 do trecho", "parte 2 do trecho"]
    linhas = cliente.get(url, params={"tabela": tabela}).json()
    assert len(linhas) == 3 and {x["grupo"] for x in linhas} == {t["id"]}
    # a mesma seleção de novo é recusada; o histórico tem uma linha só, com as seções
    assert cliente.post(url, json={"tabela": tabela, "partes": partes}).status_code == 409
    h = cliente.get("/api/registro", params={"area": "trecho"}).json()["itens"]
    assert len(h) == 1 and "seções 1 a 2, 3 blocos" in h[0]["resumo"] and "parte 0 do trecho … parte 1 do trecho" in h[0]["resumo"]
    # desligar por qualquer parte tira o trecho inteiro
    assert cliente.delete(f"{url}/{t['partes'][2]['id']}", headers=EU).status_code == 200
    assert cliente.get(url).json() == []
    assert "3 blocos" in cliente.get("/api/registro", params={"area": "trecho", "acao": "excluiu"}).json()["itens"][0]["resumo"]


def test_trecho_recusa_parte_fora_do_manual_e_sem_partes(cliente, con):
    codigo, _, tabela = um_manual(con)
    url = f"/api/manuais/{codigo}/trechos"
    assert cliente.post(url, json={"tabela": tabela, "partes": [{"secao": 1, "bloco": 0, "texto": "ok"}, {"secao": 99, "bloco": 0, "texto": "x"}]}).status_code == 422
    assert cliente.post(url, json={"tabela": tabela, "partes": []}).status_code == 422
    assert cliente.post(url, json={"tabela": tabela}).status_code == 422
    assert cliente.get(url).json() == []  # nada gravado pela metade
