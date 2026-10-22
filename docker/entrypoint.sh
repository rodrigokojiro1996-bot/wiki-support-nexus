#!/bin/sh
# Inicialização do contêiner do Support Nexus.
#  1. seed: aplica as migrações que faltam e carrega catálogo, menus e manuais (pode rodar sempre: não duplica
#     nada e preserva o trabalho da equipe)
#  2. API: uvicorn sem --reload, escutando em todas as interfaces DO CONTÊINER (quem decide o que fica exposto
#     fora dele é o mapeamento de portas do compose)
set -eu

cd /app/backend
python -m app.seed

# exec: o uvicorn substitui este script e vira o processo principal; o "docker stop" chega direto nele
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --no-server-header
