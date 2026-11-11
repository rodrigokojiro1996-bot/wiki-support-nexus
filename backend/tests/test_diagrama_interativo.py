"""Diagrama interativo: tabelas arrastadas ficam salvas por tela, ligações ganham o informativo (post-it) e o balão
da tabela lista as telas que a usam."""
from app import seed

EU = {"X-Usuario": "Ana%20Lima"}


def diagrama(cliente, tabelas="vendas", nivel=1):
    return cliente.get("/api/modulos/pdv/diagrama", params={"tabelas": tabelas, "nivel": nivel}).json()


def test_posicoes_salvas_por_tela_e_reorganizar(cliente):
    assert diagrama(cliente)["posicoes"] == {}
    corpo = {"chave": "vendas", "posicoes": [{"tabela": "vendas", "x": 120.5, "y": -40}]}
    assert cliente.put("/api/modulos/pdv/diagrama/posicoes", json=corpo, headers=EU).status_code == 200
    assert diagrama(cliente)["posicoes"] == {"vendas": {"x": 120.5, "y": -40}}
    # outra tela (outro conjunto de tabelas) não herda a posição
    assert diagrama(cliente, "vendas,clientes")["posicoes"] == {}
    # arrastar de novo atualiza; sobrevive a reimportar o catálogo
    corpo["posicoes"][0]["x"] = 300
    cliente.put("/api/modulos/pdv/diagrama/posicoes", json=corpo)
    seed.main()
    assert diagrama(cliente)["posicoes"]["vendas"]["x"] == 300
    assert cliente.delete("/api/modulos/pdv/diagrama/posicoes", params={"chave": "vendas"}).status_code == 200
    assert diagrama(cliente)["posicoes"] == {}


def test_informativo_da_ligacao_aparece_no_diagrama_e_move(cliente):
    rel = diagrama(cliente)["relacoes"][0]
    assert "nota" not in rel
    r = cliente.put("/api/modulos/pdv/relacoes/nota", headers=EU,
                    json={"id": rel["id"], "texto": "Se o valor for apagado, a venda perde o cliente."})
    assert r.status_code == 200, r.text
    assert r.json()["posicao"] == 0.5 and r.json()["por"] == "Ana Lima"
    nota = next(x for x in diagrama(cliente)["relacoes"] if x["id"] == rel["id"])["nota"]
    assert nota["texto"].startswith("Se o valor") and nota["posicao"] == 0.5
    # mover o post-it não troca o texto nem o autor
    r = cliente.put("/api/modulos/pdv/relacoes/nota", json={"id": rel["id"], "posicao": 0.8}, headers={"X-Usuario": "Outra"})
    assert r.json()["posicao"] == 0.8 and r.json()["por"] == "Ana Lima" and r.json()["texto"].startswith("Se o valor")
    assert cliente.delete("/api/modulos/pdv/relacoes/nota", params={"id": rel["id"]}).status_code == 200
    assert "nota" not in next(x for x in diagrama(cliente)["relacoes"] if x["id"] == rel["id"])


def test_informativo_recusa_relacao_inexistente_texto_vazio_e_posicao_fora(cliente):
    rel = diagrama(cliente)["relacoes"][0]
    assert cliente.put("/api/modulos/pdv/relacoes/nota", json={"id": "nao>existe", "texto": "x"}).status_code == 404
    assert cliente.put("/api/modulos/pdv/relacoes/nota", json={"id": rel["id"], "texto": "   "}).status_code == 422
    assert cliente.put("/api/modulos/pdv/relacoes/nota", json={"id": rel["id"], "posicao": 0.3}).status_code == 422  # sem texto ainda
    assert cliente.put("/api/modulos/pdv/relacoes/nota", json={"id": rel["id"], "texto": "x", "posicao": 1.5}).status_code == 422


def test_desfazer_ligacao_da_equipe_apaga_o_informativo(cliente, con):
    from tests.test_ligar_colunas import par_sem_relacao
    corpo = par_sem_relacao(con)
    rel = cliente.post("/api/modulos/pdv/relacoes", json=corpo).json()
    cliente.put("/api/modulos/pdv/relacoes/nota", json={"id": rel["id"], "texto": "Impacto no caixa"})
    cliente.put("/api/modulos/pdv/relacoes/status", json={"id": rel["id"], "status": "sugerida"})
    assert con.execute("SELECT count(*) FROM relacao_notas WHERE id = ?", (rel["id"],)).fetchone()[0] == 0


def test_balao_da_tabela_lista_as_telas_que_usam(cliente, con):
    menu, tabela = con.execute("""SELECT mt.menu, mt.tabela FROM menu_tabelas mt JOIN menus m ON m.id = mt.menu
                                  WHERE m.modulo = 'pdv' LIMIT 1""").fetchone()
    t = next(x for x in diagrama(cliente, tabela, 0)["tabelas"] if x["nome"] == tabela)
    titulo = con.execute("SELECT titulo FROM menus WHERE id = ?", (menu,)).fetchone()[0]
    assert any(caminho[-1] == titulo for caminho in t["telas"])
