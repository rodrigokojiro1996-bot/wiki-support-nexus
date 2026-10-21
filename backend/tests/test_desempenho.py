"""Catálogo sintético do tamanho de um ERP real: o diagrama precisa continuar rápido."""
import json
import random
import time

import pytest

TABELAS, RELACOES, COLUNAS = 500, 2000, 12


@pytest.fixture
def catalogo_grande(con):
    rnd = random.Random(42)
    nomes = [f"t{i:03d}" for i in range(TABELAS)]
    con.execute("INSERT INTO modulos (id, nome, banco) VALUES ('big', 'Grande', 'big')")
    con.executemany("INSERT INTO tabelas (banco, nome, engine, linhas) VALUES ('big', ?, 'InnoDB', 1000)", [(n,) for n in nomes])
    con.executemany("INSERT INTO colunas (banco, tabela, nome, tipo, pk, ordem) VALUES ('big', ?, ?, 'int(11)', ?, ?)",
                    [(n, f"c{j}", int(j == 0), j) for n in nomes for j in range(COLUNAS)])
    # poucas tabelas muito referenciadas (apoio) e o resto espalhado, como num ERP
    hubs = nomes[:5]
    rels = set()
    while len(rels) < RELACOES:
        o = rnd.choice(nomes)
        d = rnd.choice(hubs) if rnd.random() < 0.3 else rnd.choice(nomes)
        if o != d:
            rels.add((o, d, f"c{rnd.randrange(1, COLUNAS)}"))
    con.executemany("INSERT INTO relacoes (banco, id, origem, destino, colunas, tipo, regra) VALUES ('big', ?, ?, ?, ?, 'sug', 'pk_igual')",
                    [(f"{o}.{c}>{d}", o, d, json.dumps([[c, "c0"]])) for o, d, c in rels])
    con.commit()
    return nomes


@pytest.mark.parametrize("nivel, apoio", [(1, False), (2, False), (3, True)])
def test_diagrama_grande_responde_rapido(cliente, catalogo_grande, nivel, apoio):
    foco = ",".join(catalogo_grande[100:104])
    cliente.get("/api/modulos/big/diagrama", params={"tabelas": foco, "nivel": nivel, "apoio": apoio})  # aquece
    inicio = time.perf_counter()
    r = cliente.get("/api/modulos/big/diagrama", params={"tabelas": foco, "nivel": nivel, "apoio": apoio})
    ms = (time.perf_counter() - inicio) * 1000
    assert r.status_code == 200
    d = r.json()
    assert len(d["tabelas"]) <= 40 and set(d["foco"]) <= {t["nome"] for t in d["tabelas"]}
    assert all(len(t["colunas"]) == COLUNAS for t in d["tabelas"])
    print(f"nivel={nivel} apoio={apoio}: {ms:.0f} ms, {len(d['tabelas'])} tabelas, {len(d['relacoes'])} ligações")
    assert ms < 500
