"""Troca do sistema de exemplo pelo real (fora do git): catálogo coletado, modulos.json e dados/menus_<módulo>.json."""
import json

from app import config, db, seed

CATALOGO_REAL = {"banco": "erp_real", "tables": {
    "caixa": {"engine": "InnoDB", "rows": "10", "cols": [{"name": "seq", "type": "int", "pk": True},
                                                         {"name": "loja", "type": "int", "pk": True}]},
    "clientes": {"engine": "MyISAM", "rows": "5", "cols": [{"name": "codigo", "type": "int", "pk": True}]},
}, "edges": []}
MENUS_REAL = {"modulo": "pdv", "menus": [
    {"titulo": "Cadastros", "itens": [{"titulo": "Clientes", "tabelas": ["clientes"]}]},
    {"titulo": "Atendimento", "itens": [{"titulo": "Caixa", "tabelas": ["caixa"]}]},
]}


def usar_sistema_real(banco, monkeypatch):
    """O que fica no servidor, fora do git: modulos.json, o catálogo coletado e os menus reais em dados/."""
    saida = banco / "saida" / "erp_real"
    saida.mkdir(parents=True)
    (saida / "catalogo.json").write_text(json.dumps(CATALOGO_REAL), encoding="utf-8")
    config.MODULOS_REAL.write_text(json.dumps([{"id": "pdv", "nome": "PDV", "banco": "erp_real"}]), encoding="utf-8")
    (banco / "menus_pdv.json").write_text(json.dumps(MENUS_REAL), encoding="utf-8")
    exemplo = seed.arquivo_catalogo
    monkeypatch.setattr(seed, "arquivo_catalogo", lambda b: saida / "catalogo.json" if b == "erp_real" else exemplo(b))
    seed.main()


def consultar(sql, *args):
    con = db.conectar()
    try:
        return [tuple(r) for r in con.execute(sql, args)]
    finally:
        con.close()


def test_exemplo_avisa_que_e_exemplo(cliente):
    assert cliente.get("/api/modulos").json()[0]["exemplo"] is True


def test_menus_e_catalogo_reais_substituem_o_exemplo(cliente, banco, monkeypatch):
    usar_sistema_real(banco, monkeypatch)
    ids = {r[0] for r in consultar("SELECT id FROM menus WHERE modulo = 'pdv'")}
    assert ids == {"pdv.cadastros", "pdv.cadastros.clientes", "pdv.atendimento", "pdv.atendimento.caixa"}
    assert consultar("SELECT tabela FROM menu_tabelas WHERE menu = 'pdv.atendimento.caixa'") == [("caixa",)]
    assert [c[0] for c in consultar("SELECT nome FROM colunas WHERE tabela = 'caixa' ORDER BY ordem")] == ["seq", "loja"]
    assert cliente.get("/api/modulos").json()[0]["exemplo"] is False


def test_manuais_de_exemplo_saem_e_os_da_equipe_ficam(cliente, banco, monkeypatch):
    (banco / "manuais").mkdir(exist_ok=True)
    feito_pela_equipe = {"editado": True, "codigo": "PDV.001", "titulo": "Desfazer devolução", "modulo": "pdv",
                         "secoes": [{"titulo": "A", "blocos": [{"tipo": "texto", "texto": "x"}]}]}
    for codigo, menu in (("PDV.001", "pdv.cadastros.clientes"), ("PDV.002", "pdv.vendas")):
        (banco / "manuais" / f"{codigo}.json").write_text(json.dumps({**feito_pela_equipe, "codigo": codigo, "menu": menu}),
                                                         encoding="utf-8")
    seed.main()
    usar_sistema_real(banco, monkeypatch)
    manuais = dict(consultar("SELECT codigo, menu FROM manuais"))
    assert not any(c.startswith("DEMO.") for c in manuais)       # descreviam o sistema fictício
    assert manuais == {"PDV.001": "pdv.cadastros.clientes",       # a tela existe no sistema real
                       "PDV.002": None}                           # a tela sumiu: o manual fica guardado, sem tela
    assert (banco / "manuais" / "PDV.002.json").exists()


def test_rodar_de_novo_nao_muda_nada(banco, monkeypatch):
    usar_sistema_real(banco, monkeypatch)
    antes = consultar("SELECT id, pai, ordem FROM menus ORDER BY id")
    seed.main()
    assert consultar("SELECT id, pai, ordem FROM menus ORDER BY id") == antes
