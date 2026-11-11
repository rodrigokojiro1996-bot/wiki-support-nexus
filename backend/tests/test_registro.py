"""Registro de alterações: cada validação, alteração ou exclusão fica com o nome de quem fez e uma frase clara do que
mudou (com o antes e o depois)."""
from tests.test_ligar_colunas import par_sem_relacao
from tests.test_manual_trechos import um_manual

ANA = {"X-Usuario": "Ana%20Lima"}
BETO = {"X-Usuario": "Beto%20Souza"}


def ultimo(cliente, **filtro):
    itens = cliente.get("/api/registro", params=filtro).json()["itens"]
    assert itens, f"nada registrado com {filtro}"
    return itens[0]


def test_comeca_vazio_e_filtros(cliente):
    assert cliente.get("/api/registro").json() == {"itens": [], "mais": False}
    f = cliente.get("/api/registro/filtros").json()
    assert f["pessoas"] == [] and "manual" in f["areas"] and "validou" in f["acoes"]


def test_ligacao_validada_informativo_e_desfazer(cliente, con):
    corpo = par_sem_relacao(con)
    rel = cliente.post("/api/modulos/pdv/relacoes", json=corpo | {"observacao": "conferido no caixa"}, headers=ANA).json()
    ligacao = f"{corpo['origem']}.{corpo['coluna_origem']} → {corpo['destino']}.{corpo['coluna_destino']}"
    r = ultimo(cliente)
    assert (r["por"], r["acao"], r["area"], r["modulo"]) == ("Ana Lima", "validou", "ligacao", "pdv")
    assert r["resumo"] == f"Validou a ligação {ligacao} (N → 1) · observação: “conferido no caixa”"

    url = "/api/modulos/pdv/relacoes/nota"
    cliente.put(url, json={"id": rel["id"], "texto": "Venda perde o cliente"}, headers=ANA)
    assert ultimo(cliente)["resumo"] == f"Incluiu o informativo de incidentes da ligação {ligacao}: “Venda perde o cliente”"
    cliente.put(url, json={"id": rel["id"], "texto": "Venda some do extrato"}, headers=BETO)
    r = ultimo(cliente)
    assert (r["por"], r["acao"]) == ("Beto Souza", "alterou")
    assert r["detalhe"] == {"antes": "Venda perde o cliente", "depois": "Venda some do extrato"}
    cliente.put(url, json={"id": rel["id"], "posicao": 0.8}, headers=ANA)
    assert ultimo(cliente)["resumo"].endswith("(50% → 80% da linha)")
    n = len(cliente.get("/api/registro").json()["itens"])
    cliente.put(url, json={"id": rel["id"], "posicao": 0.8}, headers=ANA)  # nada mudou: nada registrado
    assert len(cliente.get("/api/registro").json()["itens"]) == n

    cliente.put("/api/modulos/pdv/relacoes/status", json={"id": rel["id"], "status": "sugerida"}, headers=BETO)
    r = ultimo(cliente)
    assert (r["por"], r["acao"]) == ("Beto Souza", "excluiu")
    assert r["resumo"] == f"Desfez a ligação {ligacao}, que tinha sido ligada pela equipe; o informativo “Venda some do extrato” foi excluído junto"


def test_sugestao_descartada_e_informativo_excluido(cliente, con):
    sug = con.execute("SELECT id FROM relacoes WHERE tipo = 'sug' LIMIT 1").fetchone()["id"]
    cliente.put("/api/modulos/pdv/relacoes/status", json={"id": sug, "status": "descartada", "observacao": "não bate"}, headers=ANA)
    r = ultimo(cliente)
    assert r["acao"] == "descartou" and r["resumo"].startswith("Descartou a ligação sugerida ") and r["resumo"].endswith("· observação: “não bate”")
    assert r["detalhe"]["antes"] == "sugerida" and r["detalhe"]["depois"] == "descartada"
    cliente.put("/api/modulos/pdv/relacoes/nota", json={"id": sug, "texto": "x"}, headers=ANA)
    cliente.delete("/api/modulos/pdv/relacoes/nota", params={"id": sug}, headers=BETO)
    r = ultimo(cliente)
    assert (r["por"], r["acao"], r["area"]) == ("Beto Souza", "excluiu", "informativo") and r["detalhe"]["antes"] == "x"


def test_diagrama_organizar_adicionar_remover_reorganizar(cliente):
    url = "/api/modulos/pdv/diagrama"
    cliente.put(f"{url}/posicoes", json={"chave": "vendas", "posicoes": [{"tabela": "vendas", "x": 10, "y": 20}]}, headers=ANA)
    r = ultimo(cliente)
    assert r["acao"] == "moveu" and "mudou de lugar vendas" in r["resumo"] and r["detalhe"]["vendas"] == {"antes": None, "depois": {"x": 10, "y": 20}}
    cliente.post(f"{url}/tabelas", json={"chave": "vendas", "tabela": "lojas", "x": 0, "y": 0}, headers=ANA)
    assert ultimo(cliente)["resumo"].startswith("Adicionou a tabela lojas ao ")
    cliente.delete(f"{url}/tabelas", params={"chave": "vendas", "tabela": "lojas"}, headers=BETO)
    r = ultimo(cliente)
    assert (r["por"], r["acao"]) == ("Beto Souza", "excluiu") and r["resumo"].startswith("Removeu a tabela lojas do ")
    cliente.delete(f"{url}/posicoes", params={"chave": "vendas"}, headers=ANA)
    assert "voltou ao layout automático" in ultimo(cliente)["resumo"]


def test_tabelas_da_tela(cliente, con):
    menu = con.execute("SELECT menu FROM menu_tabelas GROUP BY menu HAVING count(*) >= 2 LIMIT 1").fetchone()["menu"]
    atuais = [r["tabela"] for r in con.execute("SELECT tabela FROM menu_tabelas WHERE menu = ? ORDER BY tabela", (menu,))]
    cliente.put(f"/api/menus/{menu}/tabelas", json={"tabelas": atuais[1:] + ["lojas"]}, headers=ANA)
    r = ultimo(cliente)
    assert r["area"] == "tela" and r["resumo"].startswith("Alterou as tabelas da tela ")
    assert r["resumo"].endswith(f"incluiu lojas; tirou {atuais[0]}") or "lojas" in atuais


def test_trecho_validado_e_desligado(cliente, con):
    codigo, modulo, tabela = um_manual(con)
    t = cliente.post(f"/api/manuais/{codigo}/trechos", json={"tabela": tabela, "secao": 1, "bloco": 0, "texto": "Abra a tela"}, headers=ANA).json()
    r = ultimo(cliente)
    assert (r["acao"], r["area"], r["modulo"]) == ("validou", "trecho", modulo)
    assert f"corresponde à tabela {tabela}: “Abra a tela”" in r["resumo"]
    cliente.delete(f"/api/manuais/{codigo}/trechos/{t['id']}", headers=BETO)
    r = ultimo(cliente)
    assert (r["por"], r["acao"]) == ("Beto Souza", "excluiu") and "(tinha sido validado por Ana Lima)" in r["resumo"]


def test_manual_criado_e_alterado_com_o_que_mudou(cliente):
    m = cliente.get("/api/manuais/DEMO.001").json()
    corpo = {k: m[k] for k in ("titulo", "subtitulo", "modulo", "menu", "tipo")} | {"secoes": m["secoes"]}
    secao = corpo["secoes"][0]
    i = next(i for i, b in enumerate(secao["blocos"]) if b["tipo"] != "imagem")
    antigo = secao["blocos"][i]["texto"]
    secao["blocos"][i]["texto"] = "Texto novo do bloco"
    corpo["secoes"].append({"titulo": "Observações finais", "blocos": [{"tipo": "texto", "texto": "Confira o caixa."}]})
    assert cliente.put("/api/manuais/DEMO.001", json=corpo, headers=ANA).status_code == 200
    r = ultimo(cliente, area="manual")
    assert (r["por"], r["acao"], r["alvo"]) == ("Ana Lima", "alterou", "DEMO.001")
    assert f"(versão {m['versao']} → " in r["resumo"] and "2 mudanças" in r["resumo"]
    mud = r["detalhe"]["mudancas"]
    assert any(x.startswith(f"seção 1 “{secao['titulo']}”: alterou o ") and "“Texto novo do bloco”" in x for x in mud), mud
    assert any(x.startswith("incluiu a seção") and "Observações finais" in x for x in mud), mud
    assert antigo[:20] in " ".join(mud)
    # filtros: por pessoa, por área e busca no texto
    assert all(x["por"] == "Ana Lima" for x in cliente.get("/api/registro", params={"por": "Ana Lima"}).json()["itens"])
    assert cliente.get("/api/registro", params={"busca": "Observações finais"}).json()["itens"][0]["id"] == r["id"]
    assert "Ana Lima" in cliente.get("/api/registro/filtros").json()["pessoas"]


def test_paginacao(cliente):
    for i in range(5):
        cliente.put("/api/modulos/pdv/diagrama/posicoes", json={"chave": "vendas", "posicoes": [{"tabela": "vendas", "x": i, "y": 0}]})
    p1 = cliente.get("/api/registro", params={"limite": 3}).json()
    assert len(p1["itens"]) == 3 and p1["mais"]
    p2 = cliente.get("/api/registro", params={"limite": 3, "antes": p1["itens"][-1]["id"]}).json()
    assert len(p2["itens"]) == 2 and not p2["mais"]
    # o histórico não se edita nem se apaga pela API
    assert cliente.delete("/api/registro").status_code == 405


def test_importacao_do_dicionario_diz_o_que_entrou_e_o_que_mudou(cliente, con):
    from tests.test_descricoes import planilha
    t = con.execute("SELECT nome FROM tabelas ORDER BY nome LIMIT 1").fetchone()[0]
    cliente.post("/api/descricoes/importar", content=planilha(tabelas=[("PDV", t, "Primeira versão", "S")]), headers=ANA)
    r = ultimo(cliente)
    assert (r["por"], r["acao"], r["area"]) == ("Ana Lima", "importou", "dicionario")
    assert r["resumo"].endswith("1 descrição(ões) nova(s) e 0 alterada(s) (0 sem mudança)")
    cliente.post("/api/descricoes/importar", content=planilha(tabelas=[("PDV", t, "Versão corrigida", "S")]), headers=BETO)
    assert ultimo(cliente)["detalhe"]["alteradas"] == [f"PDV {t}: “Primeira versão” → “Versão corrigida”"]
    n = len(cliente.get("/api/registro").json()["itens"])
    cliente.post("/api/descricoes/importar", content=planilha(tabelas=[("PDV", t, "Versão corrigida", "S")]), headers=BETO)
    assert len(cliente.get("/api/registro").json()["itens"]) == n  # a mesma planilha de novo: nada mudou, nada registrado
