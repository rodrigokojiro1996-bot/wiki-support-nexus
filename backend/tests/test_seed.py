from app import seed


def test_seed_carrega_o_exemplo(con):
    contar = lambda t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]  # noqa: E731
    assert contar("tabelas") == 30
    assert contar("manuais") == 6
    assert contar("menus") > 0
    assert [r["id"] for r in con.execute("SELECT id FROM modulos ORDER BY rowid")] == ["pdv", "adm", "fin"]


def test_seed_de_novo_preserva_o_trabalho_da_equipe(cliente, con):
    rel = next(r for r in cliente.get("/api/modulos/pdv/catalogo").json()["relacoes"] if r["estado"] == "sugerida")
    cliente.put("/api/modulos/pdv/relacoes/status", json={"id": rel["id"], "status": "documentada", "observacao": "conferido"})
    menu = con.execute("SELECT id FROM menus ORDER BY id LIMIT 1").fetchone()["id"]
    cliente.put(f"/api/menus/{menu}/tabelas", json={"tabelas": ["vendas"]})

    seed.main()

    s = con.execute("SELECT status, observacao FROM relacao_status WHERE id = ?", (rel["id"],)).fetchone()
    assert (s["status"], s["observacao"]) == ("documentada", "conferido")
    assert con.execute("SELECT origem FROM menu_tabelas WHERE menu = ? AND tabela = 'vendas'", (menu,)).fetchone()["origem"] == "equipe"


def test_seed_de_novo_nao_duplica(con):
    antes = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("tabelas", "relacoes", "menus", "menu_tabelas", "manuais")}
    seed.main()
    depois = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in antes}
    assert antes == depois


def test_seed_carrega_exemplo_e_conteudo_real(banco, con):
    # manuais reais em dados/manuais entram junto com os DEMO.*; com o mesmo código, vale o de dados/
    real = banco / "manuais"
    real.mkdir()
    (real / "REAL.001.json").write_text('{"codigo": "REAL.001", "titulo": "Real", "modulo": "pdv", "secoes": []}', encoding="utf-8")
    (real / "DEMO.001.json").write_text('{"codigo": "DEMO.001", "titulo": "Editado", "modulo": "pdv", "secoes": []}', encoding="utf-8")
    seed.main()
    titulos = {r["codigo"]: r["titulo"] for r in con.execute("SELECT codigo, titulo FROM manuais")}
    assert titulos["REAL.001"] == "Real" and titulos["DEMO.001"] == "Editado"
    assert {"DEMO.002", "DEMO.006"} <= set(titulos)
