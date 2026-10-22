# syntax=docker/dockerfile:1
#
# Support Nexus em um contêiner: API FastAPI + interface já compilada + Chromium para o PDF.
#
#   docker compose up -d --build        (recomendado: usa o docker-compose.yml)
#   docker build -t support-nexus .     (só a imagem)
#
# Imagens base travadas por versão E por digest (sha256): o mesmo Dockerfile gera a mesma base hoje e daqui a
# um ano. Para atualizar, troque versão e digest juntos e rode os testes.

# ---------------------------------------------------------------------------------------------------------------
# Etapa 1 · frontend: compila o React. Nada desta etapa vai para a imagem final além de frontend/dist.
# ---------------------------------------------------------------------------------------------------------------
FROM node:22.23.0-bookworm-slim@sha256:d9f850096136edbc402debdd8729579a288aac64574ada0ff4db26b6ae58b0b2 AS frontend

WORKDIR /src

# primeiro só os arquivos de dependências: enquanto eles não mudarem, o "npm ci" sai do cache do Docker
COPY frontend/package.json frontend/package-lock.json ./
# npm ci instala exatamente o package-lock.json (e falha se ele estiver desatualizado), diferente do npm install
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build


# ---------------------------------------------------------------------------------------------------------------
# Etapa 2 · aplicação: Python + dependências da API + Chromium do Playwright + o build da etapa 1.
# ---------------------------------------------------------------------------------------------------------------
FROM python:3.14.9-slim-bookworm@sha256:7e0522950230cad1ec100ada6e3898c22c6bc82851289b4bdf0bf77c1c829cd5 AS app

# PYTHONDONTWRITEBYTECODE / PYTHONUNBUFFERED: sem .pyc soltos e com log aparecendo na hora no "docker logs"
# PLAYWRIGHT_BROWSERS_PATH: o Chromium fica numa pasta fixa, legível pelo usuário sem privilégios
# NEXUS_PDF_CANAL=chromium: no Linux não há Edge; o PDF usa o Chromium que o Playwright instala
# NEXUS_FRONTEND: o gerador de PDF abre a página de impressão na própria API (modo de produção, sem Vite)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    NEXUS_PDF_CANAL=chromium \
    NEXUS_FRONTEND=http://127.0.0.1:8010

WORKDIR /app/backend

# dependências antes do código (mesmo motivo do cache da etapa 1). Só a API (que inclui a importação de
# documentos); os testes (requirements-dev.txt) não fazem parte da imagem.
COPY backend/requirements.txt ./
# --with-deps instala também as bibliotecas do sistema que o Chromium precisa (fontes, libnss, ...);
# --no-shell: só o Chromium completo, que é o que NEXUS_PDF_CANAL=chromium usa (o "headless shell" seria +273 MB);
# a limpeza do apt no mesmo RUN evita que a lista de pacotes fique gravada numa camada da imagem
# tini: processo init (PID 1) que recolhe os processos do Chromium que terminam, sem depender do "init: true"
# do compose; assim a imagem funciona igual num "docker run" simples (homologação na VPS, por exemplo)
RUN pip install -r requirements.txt \
 && python -m playwright install --with-deps --no-shell chromium \
 && apt-get install -y --no-install-recommends tini \
 && rm -rf /var/lib/apt/lists/*

# usuário sem privilégios: se alguém explorar uma falha da aplicação, não é root dentro do contêiner
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin nexus

# só o que a aplicação usa em execução (o resto fica de fora pelo .dockerignore)
COPY backend/app ./app
COPY backend/seed ./seed
COPY backend/modulos.exemplo.json ./
COPY coletor/exemplo /app/coletor/exemplo
COPY --from=frontend /src/dist /app/frontend/dist
COPY docker/entrypoint.sh /usr/local/bin/nexus-entrypoint

# dados/ é onde ficam o SQLite, os manuais e os prints: no compose vira um volume (sobrevive ao contêiner).
# A pasta já existe na imagem com o dono certo, então o volume novo herda a permissão do usuário nexus.
RUN chmod 755 /usr/local/bin/nexus-entrypoint \
 && mkdir -p /app/backend/dados \
 && chown nexus:nexus /app/backend/dados

USER nexus

# documentação: a porta em que a API escuta dentro do contêiner (quem publica no host é o compose / docker run -p)
EXPOSE 8010

# o Docker chama /api/saude a cada 30 s; 3 falhas seguidas marcam o contêiner como "unhealthy".
# Python em vez de curl: a imagem slim não tem curl, e não vale instalar só para isso.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8010/api/saude', timeout=4).status == 200 else 1)"]

ENTRYPOINT ["tini", "--", "nexus-entrypoint"]
