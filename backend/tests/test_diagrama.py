from app.servicos.diagrama import recortar, tabelas_de_apoio


def rel(origem, destino):
    return {"id": f"{origem}>{destino}", "origem": origem, "destino": destino}


CADEIA = [rel("a", "b"), rel("b", "c"), rel("c", "d"), rel("d", "e"), rel("e", "f")]


def test_nivel_zero_traz_so_o_foco():
    r = recortar(["c"], CADEIA, nivel=0)
    assert r.incluidas == {"c"}
    assert r.arestas == []


def test_expande_nos_dois_sentidos():
    assert recortar(["c"], CADEIA, nivel=1).incluidas == {"b", "c", "d"}


def test_nivel_limitado_a_3():
    assert recortar(["a"], CADEIA, nivel=10).incluidas == {"a", "b", "c", "d"}


def test_nivel_negativo_vira_zero():
    assert recortar(["a"], CADEIA, nivel=-2).incluidas == {"a"}


def test_arestas_so_entre_incluidas():
    r = recortar(["c"], CADEIA, nivel=1)
    assert {x["id"] for x in r.arestas} == {"b>c", "c>d"}


# "lojas" recebe 40 referências: é tabela de apoio
APOIO = [rel(f"t{i:02d}", "lojas") for i in range(40)] + [rel("lojas", "cidades"), rel("t00", "vendas")]


def test_tabela_de_apoio_a_partir_de_40_ligacoes():
    assert tabelas_de_apoio(APOIO) == {"lojas"}
    assert tabelas_de_apoio(APOIO[1:]) == set()


def test_apoio_oculta_e_listada():
    r = recortar(["t00"], APOIO, nivel=2)
    assert "lojas" not in r.incluidas
    assert r.apoio_ocultas == ["lojas"]
    assert r.incluidas == {"t00", "vendas"}


def test_apoio_visivel_quando_pedido():
    r = recortar(["t00"], APOIO, nivel=1, apoio=True)
    assert "lojas" in r.incluidas
    assert r.apoio_ocultas == []


def test_expansao_nao_passa_pela_tabela_de_apoio():
    # foco na própria tabela de apoio: não puxa as 40 que a referenciam
    r = recortar(["lojas"], APOIO, nivel=1)
    assert r.incluidas == {"lojas"}


def test_corte_em_40_mantem_foco_e_as_mais_conectadas():
    # foco "f" ligado a 50 tabelas; "forte" tem 2 ligações com o foco, as outras 1
    rels = [rel(f"v{i:02d}", "f") for i in range(50)] + [rel("forte", "f"), rel("f", "forte")]
    r = recortar(["f"], rels, nivel=1, apoio=True, apoio_minimo=1000)
    assert len(r.incluidas) == 40
    assert {"f", "forte"} <= r.incluidas


def test_corte_com_foco_maior_que_o_limite():
    foco = [f"x{i}" for i in range(45)]
    r = recortar(foco, [rel("x0", "y")], nivel=1, limite=40)
    assert r.incluidas == set(foco)


def test_rota_ignora_tabela_inexistente(cliente):
    d = cliente.get("/api/modulos/pdv/diagrama", params={"tabelas": "vendas,nao_existe,vendas", "nivel": 1}).json()
    assert d["foco"] == ["vendas"]
    nomes = {t["nome"] for t in d["tabelas"]}
    assert "vendas" in nomes and "nao_existe" not in nomes
    assert all(r["origem"] in nomes and r["destino"] in nomes for r in d["relacoes"])
    assert all(c.keys() == {"nome", "tipo", "pk"} for t in d["tabelas"] for c in t["colunas"])


def test_rota_modulo_inexistente(cliente):
    assert cliente.get("/api/modulos/zz/diagrama", params={"tabelas": "vendas"}).status_code == 404
