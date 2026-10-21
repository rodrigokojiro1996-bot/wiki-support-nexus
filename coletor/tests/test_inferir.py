"""Cada regra de inferência com um catálogo mínimo montado no próprio teste (CSVs no formato do coletor)."""
import csv
import json
import sys

import pytest

import inferir


@pytest.fixture
def inferir_catalogo(tmp_path, monkeypatch):
    """inferir_catalogo({tabela: [(coluna, tipo, pk)]}, fks=[...], indices=[...], dicionario=[...]) -> {id: relação}."""
    def rodar(tabelas, fks=(), indices=(), dicionario=()):
        pasta = tmp_path / "saida" / "teste"
        pasta.mkdir(parents=True, exist_ok=True)

        def gravar(nome, campos, linhas):
            with open(pasta / f"{nome}.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, campos)
                w.writeheader()
                w.writerows(linhas)

        gravar("tabelas", ["TABLE_NAME", "ENGINE", "linhas_estimadas", "TABLE_COMMENT"],
               [{"TABLE_NAME": t, "ENGINE": "InnoDB", "linhas_estimadas": "1", "TABLE_COMMENT": ""} for t in tabelas])
        gravar("colunas", ["TABLE_NAME", "ORDINAL_POSITION", "COLUMN_NAME", "COLUMN_TYPE", "COLUMN_KEY"],
               [{"TABLE_NAME": t, "ORDINAL_POSITION": i + 1, "COLUMN_NAME": c, "COLUMN_TYPE": tipo, "COLUMN_KEY": "PRI" if pk else ""}
                for t, cols in tabelas.items() for i, (c, tipo, pk) in enumerate(cols)])
        gravar("fks", ["CONSTRAINT_NAME", "TABLE_NAME", "COLUMN_NAME", "REFERENCED_TABLE_NAME", "REFERENCED_COLUMN_NAME"],
               [dict(zip(["CONSTRAINT_NAME", "TABLE_NAME", "COLUMN_NAME", "REFERENCED_TABLE_NAME", "REFERENCED_COLUMN_NAME"], f)) for f in fks])
        gravar("indices", ["TABLE_NAME", "INDEX_NAME", "NON_UNIQUE", "SEQ_IN_INDEX", "COLUMN_NAME"],
               [dict(zip(["TABLE_NAME", "INDEX_NAME", "NON_UNIQUE", "SEQ_IN_INDEX", "COLUMN_NAME"], x)) for x in indices])
        (tmp_path / "dicionario.json").write_text(json.dumps({"regras": list(dicionario)}), encoding="utf-8")

        monkeypatch.setattr(inferir, "AQUI", tmp_path)
        monkeypatch.setattr(sys, "argv", ["inferir.py", "teste"])
        inferir.main()
        cat = json.loads((pasta / "catalogo.json").read_text(encoding="utf-8"))
        return {e["id"]: e for e in cat["edges"]}
    return rodar


INT = "int(11)"


def test_fk_declarada_vira_confirmada(inferir_catalogo):
    rels = inferir_catalogo({"clientes": [("id", INT, True)], "pedidos": [("id", INT, True), ("cli", INT, False)]},
                            fks=[("fk_cli", "pedidos", "cli", "clientes", "id")])
    r = rels["pedidos.cli>clientes"]
    assert (r["kind"], r["regra"], r["cols"]) == ("fk", "fk", [["cli", "id"]])


def test_dicionario(inferir_catalogo):
    rels = inferir_catalogo({"lojas": [("id_loja", INT, True)], "transf": [("id", INT, True), ("loja_origem", INT, False)]},
                            dicionario=[{"colunas": ["loja_origem"], "tabela": "lojas"}])
    r = rels["transf.loja_origem>lojas"]
    assert (r["kind"], r["regra"], r["cols"]) == ("sug", "dicionario", [["loja_origem", "id_loja"]])


def test_dicionario_aceita_tipos_diferentes_com_aviso(inferir_catalogo):
    rels = inferir_catalogo({"lojas": [("id_loja", INT, True)], "transf": [("id", INT, True), ("loja_origem", "varchar(10)", False)]},
                            dicionario=[{"colunas": ["loja_origem"], "tabela": "lojas"}])
    assert "tipos diferentes" in rels["transf.loja_origem>lojas"]["reason"]


def test_nome_tabela(inferir_catalogo):
    rels = inferir_catalogo({"cidades": [("id", INT, True)], "clientes": [("id", INT, True), ("cidade", INT, False)]})
    assert rels["clientes.cidade>cidades"]["regra"] == "nome_tabela"


def test_nome_tabela_exige_tipo_compativel(inferir_catalogo):
    rels = inferir_catalogo({"cidades": [("id", INT, True)], "clientes": [("id", INT, True), ("cidade", "varchar(60)", False)]})
    assert rels == {}


def test_decimal_com_casas_nao_vira_chave(inferir_catalogo):
    rels = inferir_catalogo({"produtos": [("id", INT, True)], "itens": [("id", INT, True), ("produto", "decimal(10,2)", False)]})
    assert rels == {}


def test_pk_igual(inferir_catalogo):
    rels = inferir_catalogo({"produtos": [("id_produto", INT, True)], "itens": [("id", INT, True), ("id_produto", INT, False)]})
    assert rels["itens.id_produto>produtos"]["regra"] == "pk_igual"


def test_pk_generica_nao_gera_relacao(inferir_catalogo):
    rels = inferir_catalogo({"produtos": [("codigo", INT, True)], "itens": [("id", INT, True), ("codigo", INT, False)]})
    assert rels == {}


def test_pk_igual_ambigua_nao_gera_relacao(inferir_catalogo):
    # duas tabelas com a mesma PK: não dá para saber qual é o destino
    rels = inferir_catalogo({"a": [("id_x", INT, True)], "b": [("id_x", INT, True)], "c": [("id", INT, True), ("id_x", INT, False)]})
    assert not any(k.startswith("c.") for k in rels)


def test_uma_relacao_por_coluna_vence_a_maior_prioridade(inferir_catalogo):
    # loja_origem casaria com o dicionário (lojas) e com pk_igual (origem_loja tem PK loja_origem)
    rels = inferir_catalogo({"lojas": [("id_loja", INT, True)], "origem_loja": [("loja_origem", INT, True)],
                             "transf": [("id", INT, True), ("loja_origem", INT, False)]},
                            dicionario=[{"colunas": ["loja_origem"], "tabela": "lojas"}])
    do_transf = [r for k, r in rels.items() if k.startswith("transf.")]
    assert [r["regra"] for r in do_transf] == ["dicionario"]


def test_composta(inferir_catalogo):
    pk = [("id_loja", INT, True), ("numero", INT, True), ("serie", INT, True)]
    rels = inferir_catalogo(
        {"nfce": pk, "nfce_itens": pk + [("item", INT, True)]},
        indices=[("nfce", "PRIMARY", "0", i + 1, c) for i, (c, _, _) in enumerate(pk)]
        + [("nfce_itens", "PRIMARY", "0", i + 1, c) for i, c in enumerate(["id_loja", "numero", "serie", "item"])])
    r = rels["nfce_itens.id_loja+numero+serie>nfce"]
    assert r["regra"] == "composta"
    assert r["cols"] == [["id_loja", "id_loja"], ["numero", "numero"], ["serie", "serie"]]


def test_exemplo_versionado_continua_igual():
    """O catalogo.json do exemplo bate com o que o inferir.py gera hoje (5 FKs + 43 inferidas)."""
    cat = json.loads((inferir.AQUI / "exemplo" / "demo_pdv" / "catalogo.json").read_text(encoding="utf-8"))
    tipos = [e["kind"] for e in cat["edges"]]
    assert (tipos.count("fk"), tipos.count("sug")) == (5, 43)
