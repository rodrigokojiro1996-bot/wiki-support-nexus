from urllib.parse import quote

from prometheus_client import REGISTRY

from app import db, seed
from app.servicos.cobertura import SEM_NOME, calcular

AUTOR = {"X-Usuario": quote("Ana")}


def por_menu(con, chave):
    return {t["menu"]: t[chave] for t in calcular(con).telas}


def total(con, chave):
    return sum(por_menu(con, chave).values())


def test_exemplo(con):
    c = calcular(con)
    assert total(con, "telas") == 32                     # itens de menu sem subitens
    assert total(con, "com_manual") == 6                 # os 6 DEMO.*
    assert {t["menu"] for t in c.telas} == {"Cadastros", "Vendas", "Caixa", "Estoque", "Fiscal", "Financeiro", "Relatórios", "Utilitários"}
    assert {r["estado"]: r["n"] for r in c.relacoes} == {"confirmada": 5, "sugerida": 43}
    assert c.manuais == {"pdv": 6}
    assert c.contribuicoes == []                          # o seed não conta como contribuição de ninguém


def test_manual_novo_aumenta_a_cobertura_e_conta_para_o_autor(cliente, con):
    antes = por_menu(con, "com_manual")["Caixa"]
    corpo = {"titulo": "Abertura", "modulo": "pdv", "menu": "pdv.caixa.abertura-de-caixa",
             "secoes": [{"titulo": "Passos", "blocos": [{"tipo": "passo", "texto": "Abra o caixa."}]}]}
    assert cliente.post("/api/manuais", json=corpo, headers=AUTOR).status_code == 201
    assert por_menu(con, "com_manual")["Caixa"] == antes + 1
    assert {"autor": "Ana", "tipo": "manual", "n": 1} in calcular(con).contribuicoes


def test_segundo_manual_na_mesma_tela_nao_conta_duas_vezes(cliente, con):
    antes = total(con, "com_manual")
    corpo = {"titulo": "Outro", "modulo": "pdv", "menu": "pdv.caixa.fechamento-de-caixa",  # já tem o DEMO.001
             "secoes": [{"titulo": "Passos", "blocos": [{"tipo": "texto", "texto": "x"}]}]}
    cliente.post("/api/manuais", json=corpo)
    assert total(con, "com_manual") == antes


def test_validar_relacao(cliente, con):
    rel = next(r for r in cliente.get("/api/modulos/pdv/catalogo").json()["relacoes"] if r["estado"] == "sugerida")
    cliente.put("/api/modulos/pdv/relacoes/status", json={"id": rel["id"], "status": "documentada"}, headers=AUTOR)
    c = calcular(con)
    assert {r["estado"]: r["n"] for r in c.relacoes} == {"confirmada": 5, "documentada": 1, "sugerida": 42}
    assert {"autor": "Ana", "tipo": "relacao", "n": 1} in c.contribuicoes


def test_confirmar_vinculos_e_contribuicao_sem_nome(cliente, con):
    menu = con.execute("SELECT menu FROM menu_tabelas WHERE origem = 'sugerido' AND menu LIKE 'pdv.cadastros.%' LIMIT 1").fetchone()["menu"]
    tabelas = [t["tabela"] for t in cliente.get(f"/api/menus/{menu}").json()["tabelas"]]
    assert por_menu(con, "tabelas_confirmadas")["Cadastros"] == 0
    cliente.put(f"/api/menus/{menu}/tabelas", json={"tabelas": tabelas})  # sem X-Usuario
    assert por_menu(con, "tabelas_confirmadas")["Cadastros"] == 1
    assert {"autor": SEM_NOME, "tipo": "vinculo", "n": len(tabelas)} in calcular(con).contribuicoes


def test_metricas_de_cobertura_no_prometheus(cliente):
    texto = cliente.get("/metrics").text
    assert 'nexus_wiki_screens{menu="Caixa",module="pdv"} 3.0' in texto
    assert 'nexus_wiki_relations{module="pdv",state="sugerida"} 43.0' in texto
    assert "nexus_wiki_up 1.0" in texto


def test_banco_fora_do_ar_nao_derruba_metrics(cliente, monkeypatch, tmp_path):
    monkeypatch.setattr(db, "ARQUIVO", tmp_path / "nao_existe" / "\0.db")
    r = cliente.get("/metrics")
    assert r.status_code == 200 and "nexus_wiki_up 0.0" in r.text
    assert "nexus_http_requests_total" in r.text  # as métricas técnicas continuam
    assert REGISTRY.get_sample_value("nexus_wiki_up") == 0


def test_seed_nao_muda_a_data_de_manual_que_nao_mudou(con):
    con.execute("UPDATE manuais SET atualizado_em = '2020-01-01 10:00:00' WHERE codigo IN ('DEMO.001', 'DEMO.002')")
    con.execute("UPDATE manuais SET titulo = 'mudou' WHERE codigo = 'DEMO.002'")  # o seed vai regravar o título do arquivo
    con.commit()
    seed.main()
    datas = {r["codigo"]: r["atualizado_em"] for r in con.execute("SELECT codigo, atualizado_em FROM manuais")}
    assert datas["DEMO.001"] == "2020-01-01 10:00:00"
    assert datas["DEMO.002"] != "2020-01-01 10:00:00"
