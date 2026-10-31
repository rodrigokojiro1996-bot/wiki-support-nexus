"""Dois tipos de manual por tela: o manual da tela (processo, um só) e os chamados frequentes (vários)."""
import json
from urllib.parse import quote

# tela do exemplo que só tem chamado frequente (DEMO.001): ainda sem manual da tela
TELA = "pdv.caixa.fechamento-de-caixa"


def manual(tipo=None, titulo="Fechar o caixa", menu=TELA):
    m = {"titulo": titulo, "subtitulo": "", "modulo": "pdv", "menu": menu,
         "secoes": [{"titulo": "Procedimento", "blocos": [{"tipo": "passo", "texto": "Acesse **Caixa > Fechamento**."}]}]}
    if tipo:
        m["tipo"] = tipo
    return m


def criar(cliente, corpo):
    return cliente.post("/api/manuais", json=corpo, headers={"X-Usuario": quote("Ana")})


def test_sem_tipo_e_manual_da_tela(cliente):
    codigo = criar(cliente, manual()).json()["codigo"]
    assert cliente.get(f"/api/manuais/{codigo}").json()["tipo"] == "processo"


def test_um_manual_da_tela_e_varios_chamados(cliente):
    assert criar(cliente, manual("processo")).status_code == 201
    r = criar(cliente, manual("processo", "Outro manual da tela"))
    assert r.status_code == 409 and "já tem o manual da tela" in r.json()["detail"]
    for titulo in ("Caixa não fecha", "Diferença no fechamento"):
        assert criar(cliente, manual("chamado", titulo)).status_code == 201


def test_ficha_separa_manual_da_tela_e_chamados(cliente):
    criar(cliente, manual("processo"))
    criar(cliente, manual("chamado", "Caixa não fecha"))
    manuais = cliente.get(f"/api/menus/{TELA}").json()["manuais"]
    assert manuais[0]["tipo"] == "processo"                       # o manual da tela vem primeiro
    assert {m["tipo"] for m in manuais[1:]} == {"chamado"}
    assert {m["codigo"] for m in manuais if m["tipo"] == "chamado"} >= {"DEMO.001"}


def test_manual_da_tela_mostra_os_chamados_da_tela(cliente):
    codigo = criar(cliente, manual("processo")).json()["codigo"]
    chamado = criar(cliente, manual("chamado", "Caixa não fecha")).json()["codigo"]
    rel = cliente.get(f"/api/manuais/{codigo}").json()["relacionados"]
    assert {(r["codigo"], r["tipo"]) for r in rel} == {(chamado, "chamado"), ("DEMO.001", "chamado")}
    # e o chamado aponta para o manual da tela
    assert (codigo, "processo") in {(r["codigo"], r["tipo"]) for r in cliente.get(f"/api/manuais/{chamado}").json()["relacionados"]}


def test_editar_sem_tipo_mantem_o_tipo(cliente):
    codigo = criar(cliente, manual("chamado", "Caixa não fecha")).json()["codigo"]
    corpo = manual(titulo="Caixa não fecha (revisado)")          # o editor comum pode não mandar o tipo
    assert cliente.put(f"/api/manuais/{codigo}", json=corpo, headers={"X-Usuario": "Ana"}).status_code == 200
    assert cliente.get(f"/api/manuais/{codigo}").json()["tipo"] == "chamado"


def test_virar_manual_da_tela_respeita_a_regra(cliente):
    criar(cliente, manual("processo"))
    chamado = criar(cliente, manual("chamado", "Caixa não fecha")).json()["codigo"]
    r = cliente.put(f"/api/manuais/{chamado}", json=manual("processo", "Caixa não fecha"), headers={"X-Usuario": "Ana"})
    assert r.status_code == 409


def test_tipo_vai_no_json_e_volta_no_seed(cliente, banco):
    from app import seed
    codigo = criar(cliente, manual("chamado", "Caixa não fecha")).json()["codigo"]
    assert json.loads((banco / "manuais" / f"{codigo}.json").read_text(encoding="utf-8"))["tipo"] == "chamado"
    seed.main()
    assert cliente.get(f"/api/manuais/{codigo}").json()["tipo"] == "chamado"
    assert cliente.get("/api/manuais/DEMO.004").json()["tipo"] == "processo"
