"""Conversão de documentos em rascunho de manual (app/servicos/importacao.py), com os exemplos fictícios de tests/dados/importacao/."""
import json
from pathlib import Path

from app.servicos.importacao import converter
from ferramentas import importar_processos as lote

EXEMPLOS = Path(__file__).parent / "dados" / "importacao"
TABELAS = {"caixa_mov", "formas_pgto", "transferencias"}


def blocos(r: dict, tipo: str) -> list[dict]:
    return [b for s in r["secoes"] for b in s["blocos"] if b["tipo"] == tipo]


def test_txt_vira_secoes_passos_e_sql(banco):
    r = converter((EXEMPLOS / "exemplo.txt").read_bytes(), "exemplo.txt", TABELAS)
    assert [s["titulo"] for s in r["secoes"]][1:] == ["Transferência presa como em uso", "Transferência não aparece no destino"]
    assert [b["rotulo"] for b in blocos(r, "passo")] == ["1.1", "1.2"]
    assert blocos(r, "sql")[0]["texto"].startswith("SELECT id_transf")
    assert r["tabelas"] == ["transferencias"]
    assert r["fontes"] == ["exemplo.txt"]


def test_senha_sai_mascarada(banco):
    r = converter((EXEMPLOS / "exemplo.txt").read_bytes(), "exemplo.txt", TABELAS)
    texto = json.dumps(r, ensure_ascii=False)
    assert "segredo123" not in texto
    assert "password=******" in texto


def test_pdf_tira_cabecalho_e_logo_repetidos_e_guarda_o_print_no_rascunho(banco):
    r = converter((EXEMPLOS / "exemplo.pdf").read_bytes(), "exemplo.pdf", TABELAS)
    assert [s["titulo"] for s in r["secoes"]] == ["Abrir o caixa", "Conferir o fechamento"]
    assert "Manual de exemplo" not in json.dumps(r, ensure_ascii=False)
    imagens = blocos(r, "imagem")
    assert len(imagens) == 1  # o logo aparece nas 3 páginas e é descartado
    assert imagens[0]["arquivo"].startswith("_rascunho/")
    assert (banco / "imagens" / imagens[0]["arquivo"]).exists()
    assert r["tabelas"] == ["caixa_mov"]


def test_lote_grava_o_mesmo_conteudo_da_conversao(banco, tmp_path):
    origem = tmp_path / "docs"
    origem.mkdir()
    for n in ("exemplo.pdf", "exemplo.txt"):
        (origem / n).write_bytes((EXEMPLOS / n).read_bytes())
    cur = tmp_path / "curadoria.json"
    cur.write_text(json.dumps({"origem": str(origem), "manuais": [
        {"codigo": "T.PDF", "titulo": "Caixa", "menu": "pdv.caixa.fechamento-de-caixa", "fontes": [{"arquivo": "exemplo.pdf"}]},
        {"codigo": "T.TXT", "titulo": "Transferências", "menu": "pdv.caixa.fechamento-de-caixa", "fontes": [{"arquivo": "exemplo.txt"}]},
    ]}), encoding="utf-8")
    lote.main(cur)
    for codigo, n in (("T.PDF", "exemplo.pdf"), ("T.TXT", "exemplo.txt")):
        gravado = json.loads((banco / "manuais" / f"{codigo}.json").read_text(encoding="utf-8"))
        r = converter((EXEMPLOS / n).read_bytes(), n, TABELAS)
        # no lote o print vai direto para imagens/<código>/; na interface, para o rascunho
        for b_lote, b_conv in zip(blocos(gravado, "imagem"), blocos(r, "imagem"), strict=True):
            assert b_lote["arquivo"] == f"{codigo}/01.png"
            assert (banco / "imagens" / b_lote["arquivo"]).read_bytes() == (banco / "imagens" / b_conv["arquivo"]).read_bytes()
            b_lote["arquivo"] = b_conv["arquivo"]
        assert gravado["secoes"] == r["secoes"]
        assert gravado["tabelas"] == r["tabelas"]
