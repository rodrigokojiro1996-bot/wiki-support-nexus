from app.servicos import limpeza as imp


def test_mascara_parametro_password():
    assert imp.mascarar("mysql -u root --password=S3cr3t! -h x") == "mysql -u root --password=****** -h x"


def test_mascara_atribuicao_password():
    assert imp.mascarar("Password = abc123") == "Password = ******"


def test_texto_sem_senha_fica_igual():
    assert imp.mascarar("Abrir o caixa e conferir o troco.") == "Abrir o caixa e conferir o troco."


def test_senhas_do_arquivo_de_segredos(tmp_path, monkeypatch):
    arq = tmp_path / "segredos.txt"
    arq.write_text("# comentário não vira senha\nsenhaFicticia42\n\n  outra.senha  \n", encoding="utf-8")
    extras = imp.carregar_segredos(arq)
    assert len(extras) == 2
    monkeypatch.setattr(imp, "SEGREDOS", imp.SEGREDOS + extras)
    assert imp.mascarar("entre com senhaFicticia42 ou outra.senha") == "entre com ****** ou ******"
    assert imp.mascarar("comentário não vira senha") == "comentário não vira senha"


def test_arquivo_de_segredos_ausente(tmp_path):
    assert imp.carregar_segredos(tmp_path / "nao_existe.txt") == []
