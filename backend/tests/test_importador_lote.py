"""Importador em lote (ferramentas/importar_processos.py): módulo e tabelas citadas de cada manual."""
import json

from ferramentas import importar_processos as lote

TEXTO = "Conferir o caixa\nConsulte a tabela caixa_mov e a tabela formas_pgto.\nOBS: confira a sangria.\n"


def importar(banco, tmp_path, itens):
    origem = tmp_path / "docs"
    origem.mkdir(exist_ok=True)
    for item in itens:
        for f in item["fontes"]:
            (origem / f["arquivo"]).write_text(TEXTO, encoding="utf-8")
    cur = tmp_path / "curadoria.json"
    cur.write_text(json.dumps({"origem": str(origem), "manuais": itens}), encoding="utf-8")
    problemas = lote.main(cur)
    manuais = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (banco / "manuais").glob("*.json")}
    return manuais, problemas


def item(codigo, menu, **extra):
    return {"codigo": codigo, "titulo": f"Manual {codigo}", "menu": menu, "fontes": [{"arquivo": f"{codigo}.txt"}], **extra}


def test_modulo_vem_de_cada_item_da_curadoria(banco, tmp_path):
    manuais, _ = importar(banco, tmp_path, [
        item("T.PDV", "pdv.caixa.fechamento-de-caixa"),                 # sem "modulo": prefixo do menu
        item("T.FIN", "fin.contas.baixa"),                             # antes caía no PDV
        item("T.ADM", "pdv.caixa.fechamento-de-caixa", modulo="adm"),  # "modulo" explícito vence o prefixo
    ])
    assert manuais["T.PDV"]["modulo"] == "pdv"
    assert manuais["T.FIN"]["modulo"] == "fin"
    assert manuais["T.ADM"]["modulo"] == "adm"


def test_tabelas_citadas_vem_do_banco_do_modulo(banco, tmp_path):
    manuais, _ = importar(banco, tmp_path, [item("T.PDV", "pdv.caixa.fechamento-de-caixa"), item("T.FIN", "fin.contas.baixa")])
    # demo_pdv tem caixa_mov e formas_pgto; o Financeiro de exemplo ainda não tem banco mapeado
    assert manuais["T.PDV"]["tabelas"] == ["caixa_mov", "formas_pgto"]
    assert manuais["T.FIN"]["tabelas"] == []


def test_modulo_inexistente_nao_importa_e_avisa(banco, tmp_path):
    manuais, problemas = importar(banco, tmp_path, [item("T.X", "xyz.tela")])
    assert "T.X" not in manuais
    assert any("módulo xyz não existe" in p for p in problemas)
