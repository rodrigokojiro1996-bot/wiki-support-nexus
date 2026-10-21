def primeiro_menu_com_tabelas(con):
    return con.execute("SELECT menu FROM menu_tabelas GROUP BY menu ORDER BY menu LIMIT 1").fetchone()["menu"]


def test_arvore_tem_contagens(cliente):
    arvore = cliente.get("/api/modulos/pdv/menus").json()
    assert arvore and all({"id", "itens", "n_tabelas", "n_manuais"} <= set(n) for n in arvore)


def test_salvar_remove_duplicadas_e_marca_equipe(cliente, con):
    menu = primeiro_menu_com_tabelas(con)
    r = cliente.put(f"/api/menus/{menu}/tabelas", json={"tabelas": ["vendas", "lojas", "vendas"]})
    assert r.status_code == 200
    ficha = cliente.get(f"/api/menus/{menu}").json()
    assert [(t["tabela"], t["origem"]) for t in ficha["tabelas"]] == [("lojas", "equipe"), ("vendas", "equipe")]


def test_salvar_devolve_vinculos_anteriores(cliente, con):
    menu = primeiro_menu_com_tabelas(con)
    antes = {t["tabela"]: t["origem"] for t in cliente.get(f"/api/menus/{menu}").json()["tabelas"]}
    assert cliente.put(f"/api/menus/{menu}/tabelas", json={"tabelas": []}).json()["antes"] == antes


def test_menu_inexistente_404(cliente):
    assert cliente.get("/api/menus/nao.existe").status_code == 404
    assert cliente.put("/api/menus/nao.existe/tabelas", json={"tabelas": []}).status_code == 404


def test_ficha_tem_caminho_ate_o_item(cliente, con):
    menu = primeiro_menu_com_tabelas(con)
    ficha = cliente.get(f"/api/menus/{menu}").json()
    assert ficha["caminho"][-1]["id"] == menu
