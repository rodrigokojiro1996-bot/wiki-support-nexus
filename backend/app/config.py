"""Configuração do Support Nexus: caminhos, portas e limites num só lugar."""
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

VERSAO = "0.3.0"

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

# datas que a equipe vê (ex.: "Manual alterado em") são sempre de Brasília, qualquer que seja o fuso do servidor
FUSO = ZoneInfo("America/Sao_Paulo")


def agora_brasilia() -> str:
    """Agora em Brasília, no formato das datas do banco: "AAAA-MM-DD HH:MM:SS"."""
    return datetime.now(FUSO).strftime("%Y-%m-%d %H:%M:%S")

# "homologacao" mostra a faixa "Ambiente de homologação" na interface (GET /api/saude informa o valor)
AMBIENTE = os.environ.get("NEXUS_AMBIENTE", "").strip().lower()

# diagrama
APOIO_MINIMO = 40     # tabelas referenciadas por tantas outras (empresas, usuarios…) ficam ocultas por padrão
LIMITE_DIAGRAMA = 40  # máximo de tabelas no diagrama, para continuar legível
NIVEL_MAXIMO = 3      # níveis de vizinhança aceitos em ?nivel=

# módulos do sistema e o schema de banco de cada um: modulos.json (real, fora do git) ou modulos.exemplo.json
MODULOS_REAL = RAIZ / "modulos.json"
MODULOS_EXEMPLO = RAIZ / "modulos.exemplo.json"


def modulos() -> list[tuple[str, str, str | None]]:
    """[(id, nome, banco), ...] na ordem em que aparecem na interface."""
    arq = MODULOS_REAL if MODULOS_REAL.exists() else MODULOS_EXEMPLO
    return [(m["id"], m["nome"], m.get("banco")) for m in json.loads(arq.read_text(encoding="utf-8"))]
