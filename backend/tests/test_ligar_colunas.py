"""Ligar colunas no diagrama: a equipe escolhe duas colunas de tabelas diferentes e valida a relação."""
import json

from app import seed

URL = "/api/modulos/pdv/relacoes"
EU = {"X-Usuario": "Ana%20Lima"}


def par_sem_relacao(con):
    """Uma coluna comum de uma tabela e a chave primária de outra, sem nenhuma relação entre as duas tabelas."""
    banco = con.execute("SELECT banco FROM modulos WHERE id = 'pdv'").fetchone()[0]
    ligadas = {frozenset((r["origem"], r["destino"])) for r in con.execute("SELECT origem, destino FROM relacoes WHERE banco = ?", (banco,))}
    pks = list(con.execute("SELECT tabela, nome FROM colunas WHERE banco = ? AND pk = 1 ORDER BY tabela", (banco,)))
    comuns = list(con.execute("SELECT tabela, nome FROM colunas WHERE banco = ? AND pk = 0 ORDER BY tabela, ordem", (banco,)))
    for o in comuns:
        for d in pks:
            if o["tabela"] != d["tabela"] and frozenset((o["tabela"], d["tabela"])) not in ligadas:
                return {"origem": o["tabela"], "coluna_origem": o["nome"], "destino": d["tabela"], "coluna_destino": d["nome"]}
    raise AssertionError("o exemplo deveria ter tabelas sem relação entre si")


def uma_do_tipo(con, tipo):
    r = con.execute("SELECT * FROM relacoes WHERE tipo = ? LIMIT 1", (tipo,)).fetchone()
    a, b = json.loads(r["colunas"])[0]
    return r, {"origem": r["origem"], "coluna_origem": a, "destino": r["destino"], "coluna_destino": b}


def do_catalogo(cliente, rel_id):
    return next((r for r in cliente.get("/api/modulos/pdv/catalogo").json()["relacoes"] if r["id"] == rel_id), None)


def test_ligar_cria_relacao_documentada_com_autoria(cliente, con):
    corpo = par_sem_relacao(con)
    r = cliente.post(URL, json=corpo, headers=EU)
    assert r.status_code == 201, r.text
    rel = r.json()
    assert rel["estado"] == "documentada" and rel["equipe"] is True and rel["por"] == "Ana Lima"
    assert rel["origem"] == corpo["origem"] and rel["colunas"] == [[corpo["coluna_origem"], corpo["coluna_destino"]]]
    assert do_catalogo(cliente, rel["id"])["estado"] == "documentada"
    # o diagrama desenha a ligação nova entre as duas tabelas
    d = cliente.get(f"/api/modulos/pdv/diagrama?tabelas={corpo['origem']}&nivel=1").json()
    assert rel["id"] in {x["id"] for x in d["relacoes"]}
    assert corpo["destino"] in {t["nome"] for t in d["tabelas"]}


def test_ligacao_sobrevive_a_nova_importacao_do_catalogo(cliente, con):
    rel = cliente.post(URL, json=par_sem_relacao(con), headers=EU).json()
    seed.main()
    assert do_catalogo(cliente, rel["id"])["estado"] == "documentada"


def test_ligar_colunas_de_uma_sugestao_so_valida_a_sugestao(cliente, con):
    sug, corpo = uma_do_tipo(con, "sug")
    r = cliente.post(URL, json=corpo, headers=EU)
    assert r.status_code == 201
    assert r.json()["id"] == sug["id"] and r.json()["equipe"] is False
    assert con.execute("SELECT COUNT(*) FROM relacoes_equipe").fetchone()[0] == 0
    assert do_catalogo(cliente, sug["id"])["estado"] == "documentada"


def test_ja_ligadas_em_qualquer_sentido_dao_conflito(cliente, con):
    _, fk = uma_do_tipo(con, "fk")
    invertida = {"origem": fk["destino"], "coluna_origem": fk["coluna_destino"], "destino": fk["origem"], "coluna_destino": fk["coluna_origem"]}
    for corpo in (fk, invertida):
        r = cliente.post(URL, json=corpo)
        assert r.status_code == 409 and "pelo banco" in r.json()["detail"]
    nova = par_sem_relacao(con)
    assert cliente.post(URL, json=nova).status_code == 201
    assert cliente.post(URL, json=nova).status_code == 409


def test_coluna_inexistente_ou_repetida_e_recusada(cliente, con):
    corpo = par_sem_relacao(con)
    assert cliente.post(URL, json={**corpo, "coluna_destino": "nao_existe"}).status_code == 422
    mesma = {**corpo, "destino": corpo["origem"], "coluna_destino": corpo["coluna_origem"]}
    assert cliente.post(URL, json=mesma).status_code == 422


def test_desfazer_apaga_a_ligacao_da_equipe(cliente, con):
    rel = cliente.post(URL, json=par_sem_relacao(con), headers=EU).json()
    r = cliente.put("/api/modulos/pdv/relacoes/status", json={"id": rel["id"], "status": "sugerida"})
    assert r.status_code == 200
    assert do_catalogo(cliente, rel["id"]) is None
    assert con.execute("SELECT COUNT(*) FROM relacao_status WHERE id = ?", (rel["id"],)).fetchone()[0] == 0


def test_ligacao_conta_na_cobertura_e_nas_contribuicoes(cliente, con):
    antes = cliente.get("/metrics").text
    cliente.post(URL, json=par_sem_relacao(con), headers=EU)
    depois = cliente.get("/metrics").text

    def valor(texto, linha):
        return sum(float(x.rsplit(" ", 1)[1]) for x in texto.splitlines() if x.startswith(linha))

    assert valor(depois, 'nexus_wiki_relations{module="pdv",state="documentada"}') == \
        valor(antes, 'nexus_wiki_relations{module="pdv",state="documentada"}') + 1
    assert 'author="Ana Lima"' in depois
