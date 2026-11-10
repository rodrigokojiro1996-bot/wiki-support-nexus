"""Dicionário de dados: a planilha conferida pela equipe vira o balão das tabelas e colunas no diagrama."""
import io

from openpyxl import Workbook

from app import seed

URL = "/api/descricoes/importar"
EU = {"X-Usuario": "Ana%20Lima"}
CAB_TAB = ["Módulo", "Tabela", "Descrição (edite aqui)", "Conferido (S/N)", "Confiança da sugestão"]
CAB_COL = ["Coluna", "Descrição (edite aqui)", "Conferido (S/N)", "Confiança da sugestão"]
CAB_EXC = ["Módulo", "Tabela", "Coluna", "Descrição (edite aqui)", "Conferido (S/N)"]


def planilha(tabelas=(), colunas=(), excecoes=()) -> bytes:
    wb = Workbook()
    wb.active.title = "Leia-me"
    for aba, cab, linhas in (("Tabelas", CAB_TAB, tabelas), ("Colunas", CAB_COL, colunas), ("Exceções", CAB_EXC, excecoes)):
        ws = wb.create_sheet(aba)
        ws.append(cab)
        for linha in linhas:
            ws.append(list(linha))
    saida = io.BytesIO()
    wb.save(saida)
    return saida.getvalue()


def exemplo(con):
    """Uma tabela do exemplo com duas colunas comuns (sem ser a pk) e a pk."""
    banco = con.execute("SELECT banco FROM modulos WHERE id = 'pdv'").fetchone()[0]
    t = con.execute("SELECT tabela FROM colunas WHERE banco = ? GROUP BY tabela HAVING count(*) >= 3 ORDER BY tabela LIMIT 1",
                    (banco,)).fetchone()[0]
    cols = [r["nome"] for r in con.execute("SELECT nome FROM colunas WHERE banco = ? AND tabela = ? ORDER BY ordem", (banco, t))]
    return t, cols


def no_diagrama(cliente, tabela):
    d = cliente.get("/api/modulos/pdv/diagrama", params={"tabelas": tabela, "nivel": 0}).json()
    return next(t for t in d["tabelas"] if t["nome"] == tabela)


def test_importa_so_o_conferido_e_aparece_no_diagrama(cliente, con):
    t, (c1, c2, c3, *_) = exemplo(con)
    corpo = planilha(
        tabelas=[("PDV", t, "Armazena os dados de teste do SPA PDV", "S", "alta")],
        colunas=[(c1, "Primeira coluna", "s", "alta"), (c2, "Ainda não conferida", "", "baixa"), (c3, "", "S", "")],
    )
    r = cliente.post(URL, content=corpo, headers=EU)
    assert r.status_code == 200, r.text
    assert r.json() | {"fora": []} == {"tabelas": 1, "colunas": 1, "excecoes": 0, "nao_conferidas": 2, "fora": []}
    tab = no_diagrama(cliente, t)
    assert tab["descricao"] == "Armazena os dados de teste do SPA PDV"
    desc = {c["nome"]: c.get("descricao", "") for c in tab["colunas"]}
    assert desc[c1] == "Primeira coluna" and desc[c2] == "" and desc[c3] == ""
    autor = con.execute("SELECT por FROM descricoes WHERE coluna = ?", (c1.lower(),)).fetchone()[0]
    assert autor == "Ana Lima"


def test_excecao_da_tabela_ganha_da_descricao_do_nome(cliente, con):
    t, (c1, *_) = exemplo(con)
    corpo = planilha(colunas=[(c1, "Descrição geral", "S")], excecoes=[("PDV", t, c1, "Nesta tabela é outra coisa", "S")])
    assert cliente.post(URL, content=corpo).json()["excecoes"] == 1
    assert {c["nome"]: c.get("descricao", "") for c in no_diagrama(cliente, t)["colunas"]}[c1] == "Nesta tabela é outra coisa"
    # na ficha da tabela também
    ficha = cliente.get(f"/api/modulos/pdv/tabelas/{t}").json()
    assert {c["nome"]: c.get("descricao", "") for c in ficha["colunas"]}[c1] == "Nesta tabela é outra coisa"


def test_nome_vale_para_todas_as_tabelas_e_sobrevive_a_reimportacao(cliente, con):
    banco = con.execute("SELECT banco FROM modulos WHERE id = 'pdv'").fetchone()[0]
    nome, = con.execute("SELECT nome FROM colunas WHERE banco = ? GROUP BY nome HAVING count(DISTINCT tabela) >= 2 LIMIT 1",
                        (banco,)).fetchone()
    tabelas = [r[0] for r in con.execute("SELECT tabela FROM colunas WHERE banco = ? AND nome = ?", (banco, nome))]
    cliente.post(URL, content=planilha(colunas=[(nome.upper(), "Vale para todas", "S")]))
    seed.main()  # reimportar o catálogo regrava tabelas/colunas, não o dicionário
    for t in tabelas[:2]:
        assert {c["nome"]: c.get("descricao", "") for c in no_diagrama(cliente, t)["colunas"]}[nome] == "Vale para todas"


def test_mandar_de_novo_atualiza_o_texto(cliente, con):
    t, _ = exemplo(con)
    cliente.post(URL, content=planilha(tabelas=[("PDV", t, "Primeira versão", "S")]))
    cliente.post(URL, content=planilha(tabelas=[("pdv", t, "Versão corrigida", "S")]))
    assert no_diagrama(cliente, t)["descricao"] == "Versão corrigida"
    assert next(x for x in cliente.get("/api/modulos/pdv/catalogo").json()["tabelas"] if x["nome"] == t)["descricao"] == "Versão corrigida"


def test_modulo_inexistente_fica_de_fora_e_planilha_invalida_da_422(cliente, con):
    r = cliente.post(URL, content=planilha(tabelas=[("XYZ", "qualquer", "Texto", "S")])).json()
    assert r["tabelas"] == 0 and r["fora"]
    # módulo que existe mas ainda não tem banco ligado: a descrição já fica guardada para quando ligar
    sem_banco = con.execute("SELECT id FROM modulos WHERE banco IS NULL OR banco = ''").fetchone()
    if sem_banco:
        assert cliente.post(URL, content=planilha(tabelas=[(sem_banco[0].upper(), "qualquer", "Texto", "S")])).json()["tabelas"] == 1
    assert cliente.post(URL, content=b"isto nao e um xlsx").status_code == 422
    wb = Workbook()
    wb.active.title = "Colunas"
    wb.active.append(["Coluna", "Descrição"])  # falta o Conferido
    ruim = io.BytesIO()
    wb.save(ruim)
    r = cliente.post(URL, content=ruim.getvalue())
    assert r.status_code == 422 and "Conferido" in r.json()["detail"]
