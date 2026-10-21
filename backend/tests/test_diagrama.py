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


def recortar_referencia(foco, rels, nivel=1, apoio=False, limite=40, apoio_minimo=40):
    """O algoritmo da 0.1.0 (varre todas as relações a cada nível), com o mesmo desempate por nome."""
    apoio_tab = tabelas_de_apoio(rels, apoio_minimo)
    incluidas, fronteira, apoio_ocultas = set(foco), set(foco), set()
    for _ in range(max(0, min(nivel, 3))):
        nova = set()
        for r in rels:
            for a, b in ((r["origem"], r["destino"]), (r["destino"], r["origem"])):
                if a in fronteira and b not in incluidas and (apoio or a not in apoio_tab):
                    if b in apoio_tab and not apoio:
                        apoio_ocultas.add(b)
                    else:
                        nova.add(b)
        incluidas |= nova
        fronteira = nova
    if len(incluidas) > limite:
        conexoes = {t: sum(1 for r in rels if {r["origem"], r["destino"]} & set(foco) and t in (r["origem"], r["destino"])) for t in incluidas}
        incluidas = set(foco) | set(sorted(incluidas - set(foco), key=lambda t: (-conexoes[t], t))[: max(0, limite - len(foco))])
    arestas = [r for r in rels if r["origem"] in incluidas and r["destino"] in incluidas]
    return incluidas, arestas, sorted(apoio_ocultas - incluidas)


def test_igual_ao_algoritmo_da_0_1_0_em_grafos_aleatorios():
    import random
    rnd = random.Random(7)
    for _ in range(300):
        n = rnd.randint(2, 120)
        nomes = [f"t{i}" for i in range(n)]
        hubs = nomes[: rnd.randint(0, 3)]
        rels = []
        for _ in range(rnd.randint(0, 4 * n)):
            o = rnd.choice(nomes)
            d = rnd.choice(hubs) if hubs and rnd.random() < 0.4 else rnd.choice(nomes)
            rels.append(rel(o, d))  # inclui laços (o == d) e ligações repetidas de propósito
        foco = rnd.sample(nomes, rnd.randint(1, min(5, n)))
        args = dict(nivel=rnd.randint(-1, 5), apoio=rnd.random() < 0.5, limite=rnd.choice([5, 15, 40]), apoio_minimo=rnd.choice([3, 8, 40]))
        r = recortar(foco, rels, **args)
        assert (r.incluidas, r.arestas, r.apoio_ocultas) == recortar_referencia(foco, rels, **args), args
