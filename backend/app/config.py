"""Configuração do Support Nexus: caminhos, portas e limites num só lugar."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent  # backend/
PROJETO = RAIZ.parent
SEED = RAIZ / "seed"     # só o sistema de exemplo (versionado)
DADOS = RAIZ / "dados"   # banco gerado e conteúdo real (fora do git)


def pasta_conteudo(nome: str) -> Path:
    """Conteúdo real (dados/<nome>) quando existir; senão o exemplo versionado (seed/<nome>)."""
    real = DADOS / nome
    return real if real.is_dir() else SEED / nome
