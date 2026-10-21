"""Configuração do Support Nexus: caminhos, portas e limites num só lugar."""
import json
import os
from pathlib import Path

VERSAO = "0.2.0"

RAIZ = Path(__file__).resolve().parent.parent  # backend/
PROJETO = RAIZ.parent
SEED = RAIZ / "seed"     # só o sistema de exemplo (versionado)
DADOS = RAIZ / "dados"   # banco gerado e conteúdo real (fora do git)
DIST = PROJETO / "frontend" / "dist"  # build do frontend, servido pela API no modo de produção

PORTA_API = 8010
ORIGENS_CORS = ["http://localhost:5173", "http://127.0.0.1:5173"]

# PDF: página de impressão aberta num navegador headless (Edge no Windows; "chromium" no Linux/Docker).
# Em produção NEXUS_FRONTEND aponta para a própria API (http://127.0.0.1:8010), que serve o build.
FRONTEND = os.environ.get("NEXUS_FRONTEND", "http://localhost:5173")
PDF_CANAL = os.environ.get("NEXUS_PDF_CANAL", "msedge")

# diagrama
APOIO_MINIMO = 40     # tabelas referenciadas por tantas outras (empresas, usuarios…) ficam ocultas por padrão
LIMITE_DIAGRAMA = 40  # máximo de tabelas no diagrama, para continuar legível
NIVEL_MAXIMO = 3      # níveis de vizinhança aceitos em ?nivel=

# módulos do sistema e o schema de banco de cada um: modulos.json (real, fora do git) ou modulos.exemplo.json
MODULOS_REAL = RAIZ / "modulos.json"
MODULOS_EXEMPLO = RAIZ / "modulos.exemplo.json"


def pasta_conteudo(nome: str) -> Path:
    """Conteúdo real (dados/<nome>) quando existir; senão o exemplo versionado (seed/<nome>)."""
    real = DADOS / nome
    return real if real.is_dir() else SEED / nome


def modulos() -> list[tuple[str, str, str | None]]:
    """[(id, nome, banco), ...] na ordem em que aparecem na interface."""
    arq = MODULOS_REAL if MODULOS_REAL.exists() else MODULOS_EXEMPLO
    return [(m["id"], m["nome"], m.get("banco")) for m in json.loads(arq.read_text(encoding="utf-8"))]
