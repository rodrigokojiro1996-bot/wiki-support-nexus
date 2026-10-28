import json
from urllib.parse import quote

import pytest

from app import seed

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 64
MENU = "pdv.caixa.fechamento-de-caixa"


def novo(**extra):
    m = {"titulo": "Reabrir caixa", "subtitulo": "Quando o operador fechou antes da hora", "modulo": "pdv", "menu": MENU,
         "secoes": [{"titulo": "Procedimento", "blocos": [
             {"tipo": "passo", "texto": "Acesse **Caixa > Reabrir**."},
             {"tipo": "sql", "texto": "SELECT * FROM caixa_mov WHERE id_caixa = 1;"},
             {"tipo": "obs", "texto": "Use mysql --password=Segredo123 só no servidor."}]}]}
    m.update(extra)
    return m


def criar(cliente, corpo=None, autor="Ana"):
    return cliente.post("/api/manuais", json=corpo or novo(), headers={"X-Usuario": quote(autor)})


def test_cria_com_codigo_do_modulo_e_aparece_na_tela(cliente, banco):
    r = criar(cliente)
    assert r.status_code == 201 and r.json() == {"codigo": "PDV.001", "versao": "1.0"}
    assert criar(cliente).json()["codigo"] == "PDV.002"
    m = cliente.get("/api/manuais/PDV.001").json()
    assert m["titulo"] == "Reabrir caixa" and m["menu"] == MENU and m["por"] == "Ana"
    assert "PDV.001" in {x["codigo"] for x in cliente.get(f"/api/menus/{MENU}").json()["manuais"]}


def test_grava_json_no_formato_dos_manuais(cliente, banco):
    criar(cliente)
    arq = json.loads((banco / "manuais" / "PDV.001.json").read_text(encoding="utf-8"))
    assert arq["editado"] is True  # o importador não sobrescreve
    assert [b["tipo"] for b in arq["secoes"][0]["blocos"]] == ["passo", "sql", "obs"]
    assert set(arq["secoes"][0]["blocos"][0]) == {"tipo", "texto"}


def test_mascara_senha_e_detecta_tabelas(cliente):
    criar(cliente)
    m = cliente.get("/api/manuais/PDV.001").json()
    assert "Segredo123" not in json.dumps(m) and "--password=******" in m["secoes"][0]["blocos"][2]["texto"]
    assert m["tabelas"] == ["caixa_mov"]
    # e o manual passa a aparecer na ficha da tabela
    assert "PDV.001" in {x["codigo"] for x in cliente.get("/api/modulos/pdv/tabelas/caixa_mov").json()["manuais"]}


def test_editar_sobe_a_versao_e_mantem_o_codigo(cliente):
    criar(cliente)
    corpo = novo(titulo="Reabrir caixa (revisado)")
    r = cliente.put("/api/manuais/PDV.001", json=corpo, headers={"X-Usuario": "Bia"})
    assert r.json() == {"codigo": "PDV.001", "versao": "1.1"}
    m = cliente.get("/api/manuais/PDV.001").json()
    assert (m["titulo"], m["por"]) == ("Reabrir caixa (revisado)", "Bia")


def test_editar_manual_de_exemplo_grava_em_dados_e_sobrevive_ao_seed(cliente, banco):
    m = cliente.get("/api/manuais/DEMO.002").json()
    corpo = {"titulo": "Título novo", "subtitulo": m["subtitulo"], "modulo": "pdv", "menu": m["menu"], "secoes": m["secoes"]}
    assert cliente.put("/api/manuais/DEMO.002", json=corpo).status_code == 200
    assert (banco / "manuais" / "DEMO.002.json").exists()
    seed.main()
    assert cliente.get("/api/manuais/DEMO.002").json()["titulo"] == "Título novo"


def test_seed_preserva_manual_criado_pela_interface(cliente):
    criar(cliente)
    seed.main()
    assert cliente.get("/api/manuais/PDV.001").status_code == 200


def test_editar_inexistente_404(cliente):
    assert cliente.put("/api/manuais/PDV.999", json=novo()).status_code == 404


@pytest.mark.parametrize("mudanca", [
    {"titulo": "  "},
    {"secoes": []},
    {"secoes": [{"titulo": "", "blocos": []}]},
    {"secoes": [{"titulo": "S", "blocos": [{"tipo": "passo", "texto": " "}]}]},
    {"secoes": [{"titulo": "S", "blocos": [{"tipo": "tabela", "texto": "x"}]}]},
    {"secoes": [{"titulo": "S", "blocos": [{"tipo": "imagem", "arquivo": "../../dados/nexus.db"}]}]},
    {"secoes": [{"titulo": "S", "blocos": [{"tipo": "imagem", "arquivo": "_rascunho/nao_existe.png"}]}]},
    {"menu": "pdv.nao.existe"},
    {"modulo": "fin"},
])
def test_validacao(cliente, mudanca):
    assert criar(cliente, novo(**mudanca)).status_code == 422


def test_print_colado_vai_para_a_pasta_do_manual_ao_salvar(cliente, banco):
    r = cliente.post("/api/imagens", content=PNG, headers={"Content-Type": "image/png"})
    assert r.status_code == 201
    rascunho = r.json()["arquivo"]
    assert rascunho.startswith("_rascunho/") and rascunho.endswith(".png")
    assert cliente.get(f"/api/imagens/{rascunho}").content == PNG  # a prévia do editor já mostra

    corpo = novo()
    corpo["secoes"][0]["blocos"].append({"tipo": "imagem", "arquivo": rascunho, "legenda": "Tela de reabertura"})
    criar(cliente, corpo)
    bloco = cliente.get("/api/manuais/PDV.001").json()["secoes"][0]["blocos"][-1]
    assert bloco == {"tipo": "imagem", "arquivo": "PDV.001/01.png", "legenda": "Tela de reabertura"}
    assert (banco / "imagens" / "PDV.001" / "01.png").read_bytes() == PNG
    assert not (banco / "imagens" / rascunho).exists()

    # na edição, o print novo ganha o próximo número
    r2 = cliente.post("/api/imagens", content=PNG).json()["arquivo"]
    corpo["secoes"][0]["blocos"] = [bloco, {"tipo": "imagem", "arquivo": r2, "legenda": ""}]
    cliente.put("/api/manuais/PDV.001", json=corpo)
    blocos = cliente.get("/api/manuais/PDV.001").json()["secoes"][0]["blocos"]
    assert [b["arquivo"] for b in blocos] == ["PDV.001/01.png", "PDV.001/02.png"]


def test_imagem_invalida(cliente):
    assert cliente.post("/api/imagens", content=b"<script>alert(1)</script>").status_code == 415
    assert cliente.post("/api/imagens", content=PNG + b"\0" * (8 * 1024 * 1024)).status_code == 413


def test_imagens_do_exemplo_continuam_servidas(cliente, banco, monkeypatch):
    from app import config
    pasta = banco / "seed_imgs"
    (pasta / "imagens" / "DEMO.009").mkdir(parents=True)
    (pasta / "imagens" / "DEMO.009" / "01.png").write_bytes(PNG)
    monkeypatch.setattr(config, "SEED", pasta)
    assert cliente.get("/api/imagens/DEMO.009/01.png").content == PNG
    assert cliente.get("/api/imagens/DEMO.009/02.png").status_code == 404
    assert cliente.get("/api/imagens/..%2F..%2Fnexus.db/x").status_code == 404


def test_manual_so_em_tela_final(cliente, con):
    # menu principal e submenu com opções são só navegação: o manual vai numa tela final
    r = criar(cliente, novo(menu="pdv.caixa"))
    assert r.status_code == 422 and "é um menu, não uma tela" in r.json()["detail"]
    a_detalhar = con.execute("SELECT id FROM menus WHERE submenu = 1 AND modulo = 'pdv'").fetchone()["id"]
    assert criar(cliente, novo(menu=a_detalhar)).status_code == 422  # tem opções no sistema, ainda não mapeadas
    assert criar(cliente, novo(menu=MENU)).status_code == 201
