"""Banco SQLite temporário carregado com o sistema de exemplo (demo_pdv), isolado de qualquer dado real."""
import pytest
from fastapi.testclient import TestClient

from app import config, db, seed
from app.main import app


@pytest.fixture
def banco(tmp_path, monkeypatch):
    # dados/ vazio: manuais, imagens e módulos caem no exemplo versionado, mesmo que exista conteúdo real na máquina
    monkeypatch.setattr(config, "DADOS", tmp_path)
    monkeypatch.setattr(config, "MODULOS_REAL", tmp_path / "modulos.json")
    monkeypatch.setattr(db, "ARQUIVO", tmp_path / "nexus.db")
    monkeypatch.setattr(seed, "arquivo_catalogo", lambda b: config.PROJETO / "coletor" / "exemplo" / b / "catalogo.json")
    seed.main()
    return tmp_path


@pytest.fixture
def cliente(banco):
    return TestClient(app)


@pytest.fixture
def con(banco):
    c = db.conectar()
    yield c
    c.close()
