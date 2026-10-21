import pytest


def uma_sugerida(cliente):
    rels = cliente.get("/api/modulos/pdv/catalogo").json()["relacoes"]
    return next(r for r in rels if r["estado"] == "sugerida")


def menu_com(cliente, con, rel):
    """Um menu cuja ficha mostra a relação."""
    linha = con.execute("SELECT menu FROM menu_tabelas WHERE tabela IN (?, ?) LIMIT 1", (rel["origem"], rel["destino"])).fetchone()
    assert linha, "o exemplo deveria ter uma tela usando a tabela"
    return linha["menu"]


def estado(cliente, rel_id):
    return next(r["estado"] for r in cliente.get("/api/modulos/pdv/catalogo").json()["relacoes"] if r["id"] == rel_id)


def put(cliente, rel_id, status):
    return cliente.put("/api/modulos/pdv/relacoes/status", json={"id": rel_id, "status": status})


def test_documentar_e_desfazer(cliente, con):
    r = uma_sugerida(cliente)
    assert put(cliente, r["id"], "documentada").status_code == 200
    assert estado(cliente, r["id"]) == "documentada"
    assert put(cliente, r["id"], "sugerida").status_code == 200
    assert estado(cliente, r["id"]) == "sugerida"
    # "sugerida" apaga o registro em vez de gravar um terceiro estado
    assert con.execute("SELECT COUNT(*) FROM relacao_status WHERE id = ?", (r["id"],)).fetchone()[0] == 0


def test_descartada_some_da_ficha_da_tela(cliente, con):
    r = uma_sugerida(cliente)
    menu = menu_com(cliente, con, r)
    assert r["id"] in {x["id"] for x in cliente.get(f"/api/menus/{menu}").json()["relacoes"]}
    put(cliente, r["id"], "descartada")
    assert r["id"] not in {x["id"] for x in cliente.get(f"/api/menus/{menu}").json()["relacoes"]}
    # continua registrada no catálogo
    assert estado(cliente, r["id"]) == "descartada"


def test_relacao_inexistente_404(cliente):
    assert put(cliente, "nao>existe", "documentada").status_code == 404


def test_modulo_inexistente_404(cliente):
    assert cliente.put("/api/modulos/zz/relacoes/status", json={"id": "x", "status": "documentada"}).status_code == 404


@pytest.mark.parametrize("status", ["confirmada", "", "DOCUMENTADA"])
def test_status_invalido_422(cliente, status):
    assert put(cliente, uma_sugerida(cliente)["id"], status).status_code == 422


def test_fk_aparece_como_confirmada(cliente):
    rels = cliente.get("/api/modulos/pdv/catalogo").json()["relacoes"]
    fks = [r for r in rels if r["regra"] == "fk"]
    assert fks and all(r["estado"] == "confirmada" for r in fks)
