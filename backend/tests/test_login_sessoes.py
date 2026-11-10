"""Sessões de quem entrou com a conta Microsoft e tentativas de login em andamento (guardadas no SQLite)."""
from app.servicos import sessoes
from app.servicos.entra import Tentativa

ANA = {"oid": "o-ana", "email": "ana@farmaciasassociadas.com.br", "nome": "Ana"}
T = Tentativa(state="estado-1", nonce="nonce-1", verificador="verificador-1")


def test_sessao_criada_e_lida(con):
    token = sessoes.criar(con, **ANA)
    s = sessoes.ler(con, token)
    assert (s["oid"], s["email"], s["nome"]) == ("o-ana", "ana@farmaciasassociadas.com.br", "Ana")


def test_banco_nao_guarda_o_token(con):
    # quem copiar o arquivo do banco não leva sessões prontas para usar
    token = sessoes.criar(con, **ANA)
    valores = [str(v) for linha in con.execute("SELECT * FROM sessoes") for v in tuple(linha)]
    assert valores and all(token not in v for v in valores)


def test_token_desconhecido_ou_vazio(con):
    sessoes.criar(con, **ANA)
    assert sessoes.ler(con, "token-inventado") is None
    assert sessoes.ler(con, "") is None
    assert sessoes.ler(con, None) is None


def test_sessao_vence_e_some(con):
    token = sessoes.criar(con, **ANA, agora=1000)
    fim = 1000 + sessoes.DURACAO_S
    assert sessoes.ler(con, token, agora=fim - 1) is not None
    assert sessoes.ler(con, token, agora=fim) is None
    assert con.execute("SELECT COUNT(*) FROM sessoes").fetchone()[0] == 0


def test_duracao_curta(con):
    token = sessoes.criar(con, **ANA, duracao=120, agora=1000)
    assert sessoes.ler(con, token, agora=1119) is not None
    assert sessoes.ler(con, token, agora=1120) is None


def test_sair_encerra_so_a_propria_sessao(con):
    a = sessoes.criar(con, **ANA)
    b = sessoes.criar(con, **ANA)  # a mesma pessoa em outro navegador
    sessoes.encerrar(con, a)
    assert sessoes.ler(con, a) is None and sessoes.ler(con, b) is not None


def test_sessoes_vencidas_sao_limpas_ao_criar(con):
    sessoes.criar(con, **ANA, agora=1000)
    sessoes.criar(con, **ANA, agora=1000 + sessoes.DURACAO_S + 1)
    assert con.execute("SELECT COUNT(*) FROM sessoes").fetchone()[0] == 1


# ---------------- tentativa de login em andamento ----------------
def test_tentativa_guardada_e_consumida(con):
    chave = sessoes.guardar_login(con, T, "/manuais/DEMO.001", agora=1000)
    p = sessoes.consumir_login(con, chave, agora=1001)
    assert (p.tentativa, p.voltar) == (T, "/manuais/DEMO.001")


def test_tentativa_vale_uma_vez(con):
    # sem isto, o mesmo retorno do Entra poderia ser reapresentado
    chave = sessoes.guardar_login(con, T, "/", agora=1000)
    assert sessoes.consumir_login(con, chave, agora=1001) is not None
    assert sessoes.consumir_login(con, chave, agora=1002) is None


def test_tentativa_vence_em_10_minutos(con):
    chave = sessoes.guardar_login(con, T, "/", agora=1000)
    assert sessoes.consumir_login(con, chave, agora=1000 + 600) is None


def test_tentativa_de_outro_navegador_nao_serve(con):
    sessoes.guardar_login(con, T, "/", agora=1000)
    assert sessoes.consumir_login(con, "chave-inventada", agora=1001) is None
    assert sessoes.consumir_login(con, None, agora=1001) is None
