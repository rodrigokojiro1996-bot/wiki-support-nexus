"""Adicionar tabela ao diagrama (botão direito no fundo): entra para todos naquela tela, no ponto clicado, com as
ligações dela; sai sem apagar as ligações feitas com ela."""
from app import seed

EU = {"X-Usuario": "Ana%20Lima"}
URL = "/api/modulos/pdv/diagrama"


def diagrama(cliente, tabelas="vendas", nivel=0):
    return cliente.get(URL, params={"tabelas": tabelas, "nivel": nivel}).json()


def fora_do_diagrama(cliente, tabelas="vendas", nivel=0):
    dentro = {t["nome"] for t in diagrama(cliente, tabelas, nivel)["tabelas"]}
    return next(t["nome"] for t in cliente.get("/api/modulos/pdv/tabelas").json() if t["nome"] not in dentro)


def test_lista_das_tabelas_do_modulo_para_a_busca(cliente):
    lista = cliente.get("/api/modulos/pdv/tabelas").json()
    assert len(lista) > 5 and set(lista[0]) == {"nome", "descricao"}
    assert [t["nome"] for t in lista] == sorted(t["nome"] for t in lista)


def test_adicionar_tabela_entra_na_tela_no_ponto_clicado_e_sobrevive_ao_seed(cliente):
    extra = fora_do_diagrama(cliente)
    r = cliente.post(f"{URL}/tabelas", json={"chave": "vendas", "tabela": extra, "x": 410.6, "y": -80}, headers=EU)
    assert r.status_code == 201, r.text
    d = diagrama(cliente)
    t = next(t for t in d["tabelas"] if t["nome"] == extra)
    assert t["adicionada"] is True and t["foco"] is False and t["colunas"]
    assert d["posicoes"][extra] == {"x": 411, "y": -80}
    # vale só para esta tela; adicionar de novo não duplica; sobrevive a reimportar o catálogo
    assert not any(t["adicionada"] for t in diagrama(cliente, "vendas,clientes")["tabelas"])
    assert cliente.post(f"{URL}/tabelas", json={"chave": "vendas", "tabela": extra}).status_code == 201
    seed.main()
    assert [t["nome"] for t in diagrama(cliente)["tabelas"]].count(extra) == 1


def test_tabela_adicionada_traz_as_ligacoes_com_as_que_ja_estao(cliente, con):
    # uma tabela ligada a vendas que não aparece no nível 0
    vizinha = next(r["origem"] if r["destino"] == "vendas" else r["destino"]
                   for r in cliente.get("/api/modulos/pdv/catalogo").json()["relacoes"]
                   if "vendas" in (r["origem"], r["destino"]) and r["origem"] != r["destino"] and r["estado"] != "descartada")
    assert not any(vizinha in (r["origem"], r["destino"]) for r in diagrama(cliente)["relacoes"])
    cliente.post(f"{URL}/tabelas", json={"chave": "vendas", "tabela": vizinha})
    assert any(vizinha in (r["origem"], r["destino"]) for r in diagrama(cliente)["relacoes"])


def test_remover_tira_a_tabela_e_a_posicao(cliente):
    extra = fora_do_diagrama(cliente)
    cliente.post(f"{URL}/tabelas", json={"chave": "vendas", "tabela": extra, "x": 10, "y": 10})
    assert cliente.delete(f"{URL}/tabelas", params={"chave": "vendas", "tabela": extra}).status_code == 200
    d = diagrama(cliente)
    assert extra not in {t["nome"] for t in d["tabelas"]} and extra not in d["posicoes"]
    assert cliente.delete(f"{URL}/tabelas", params={"chave": "vendas", "tabela": extra}).status_code == 404


def test_recusa_tabela_inexistente(cliente):
    assert cliente.post(f"{URL}/tabelas", json={"chave": "vendas", "tabela": "nao_existe"}).status_code == 404
    assert cliente.post(f"{URL}/tabelas", json={"chave": "vendas", "tabela": ""}).status_code == 422
