from urllib.parse import quote


def autor(nome):
    return {"X-Usuario": quote(nome)}


def sugerida(cliente):
    return next(r for r in cliente.get("/api/modulos/pdv/catalogo").json()["relacoes"] if r["estado"] == "sugerida")


def test_validacao_grava_quem_e_quando(cliente):
    r = sugerida(cliente)
    assert r["por"] is None and r["em"] is None
    cliente.put("/api/modulos/pdv/relacoes/status", json={"id": r["id"], "status": "documentada"}, headers=autor("João Conceição"))
    depois = next(x for x in cliente.get("/api/modulos/pdv/catalogo").json()["relacoes"] if x["id"] == r["id"])
    assert depois["por"] == "João Conceição" and depois["em"]


def test_quem_descarta_substitui_quem_validou(cliente):
    r = sugerida(cliente)
    cliente.put("/api/modulos/pdv/relacoes/status", json={"id": r["id"], "status": "documentada"}, headers=autor("Ana"))
    cliente.put("/api/modulos/pdv/relacoes/status", json={"id": r["id"], "status": "descartada"}, headers=autor("Bia"))
    assert next(x for x in cliente.get("/api/modulos/pdv/catalogo").json()["relacoes"] if x["id"] == r["id"])["por"] == "Bia"


def test_sem_nome_continua_aceito(cliente):
    r = sugerida(cliente)
    assert cliente.put("/api/modulos/pdv/relacoes/status", json={"id": r["id"], "status": "documentada"}).status_code == 200


def test_vinculo_grava_autor_e_preserva_o_original(cliente, con):
    menu = con.execute("SELECT id FROM menus ORDER BY id LIMIT 1").fetchone()["id"]
    cliente.put(f"/api/menus/{menu}/tabelas", json={"tabelas": ["vendas"]}, headers=autor("Ana"))
    cliente.put(f"/api/menus/{menu}/tabelas", json={"tabelas": ["vendas", "lojas"]}, headers=autor("Bia"))
    t = {x["tabela"]: x for x in cliente.get(f"/api/menus/{menu}").json()["tabelas"]}
    assert t["vendas"]["por"] == "Ana" and t["vendas"]["em"]
    assert t["lojas"]["por"] == "Bia"


def test_confirmar_sugerido_registra_quem_confirmou(cliente, con):
    linha = con.execute("SELECT menu, tabela FROM menu_tabelas WHERE origem = 'sugerido' LIMIT 1").fetchone()
    atuais = [x["tabela"] for x in cliente.get(f"/api/menus/{linha['menu']}").json()["tabelas"]]
    cliente.put(f"/api/menus/{linha['menu']}/tabelas", json={"tabelas": atuais}, headers=autor("Carla"))
    t = {x["tabela"]: x for x in cliente.get(f"/api/menus/{linha['menu']}").json()["tabelas"]}
    assert (t[linha["tabela"]]["origem"], t[linha["tabela"]]["por"]) == ("equipe", "Carla")
