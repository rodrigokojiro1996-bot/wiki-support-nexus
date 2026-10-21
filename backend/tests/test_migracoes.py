import sqlite3
from pathlib import Path

import pytest

from app import db

SCHEMA_0_1_0 = (Path(__file__).parent / "dados" / "schema_0_1_0.sql").read_text(encoding="utf-8")
LINHA_FONTES = "  fontes        TEXT NOT NULL DEFAULT '[]', -- documentos de origem do manual\n"


def abrir(arq: Path) -> sqlite3.Connection:
    con = sqlite3.connect(arq)
    con.row_factory = sqlite3.Row
    return con


def estrutura(con) -> dict:
    """Colunas (nome, tipo, not null, default, pk) de cada tabela: o equivalente comparável ao ".schema".

    A ordem das colunas não entra: no banco da 0.1.0 "fontes" veio no CREATE, no novo vem do ALTER (fica no fim).
    """
    tabelas = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {t: sorted(tuple(c)[1:] for c in con.execute(f"PRAGMA table_info({t})")) for t in tabelas}


@pytest.fixture
def novo(tmp_path):
    con = abrir(tmp_path / "novo.db")
    db.migrar(con)
    yield con
    con.close()


def test_banco_novo_aplica_todas(tmp_path):
    con = abrir(tmp_path / "x.db")
    aplicadas = db.migrar(con)
    assert aplicadas == [a.stem for _, a in db.migracoes()]
    assert db.versao_atual(con) == db.migracoes()[-1][0]


def test_rodar_de_novo_nao_faz_nada(novo):
    assert db.migrar(novo) == []


@pytest.mark.parametrize("com_fontes, versao", [(True, 2), (False, 1)])
def test_banco_da_0_1_0_termina_igual_ao_novo(tmp_path, novo, com_fontes, versao):
    con = abrir(tmp_path / "antigo.db")
    con.executescript(SCHEMA_0_1_0 if com_fontes else SCHEMA_0_1_0.replace(LINHA_FONTES, ""))
    assert db.versao_atual(con) == versao
    aplicadas = db.migrar(con)
    assert all(int(a[:3]) > versao for a in aplicadas)
    assert estrutura(con) == estrutura(novo)
    assert [r[0] for r in con.execute("SELECT versao FROM schema_version ORDER BY versao")] == [n for n, _ in db.migracoes()]


def test_migracao_com_erro_desfaz_tudo(tmp_path, monkeypatch):
    pasta = tmp_path / "migrations"
    pasta.mkdir()
    (pasta / "001_ok.sql").write_text("CREATE TABLE a (x INTEGER);", encoding="utf-8")
    (pasta / "002_quebrada.sql").write_text("CREATE TABLE b (x INTEGER);\nINSERT INTO nao_existe VALUES (1);", encoding="utf-8")
    monkeypatch.setattr(db, "MIGRACOES", pasta)
    con = abrir(tmp_path / "x.db")
    with pytest.raises(sqlite3.OperationalError):
        db.migrar(con)
    assert db.versao_atual(con) == 1
    assert not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'b'").fetchone()
