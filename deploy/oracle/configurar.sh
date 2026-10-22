#!/usr/bin/env bash
# Cria ou atualiza o .env do servidor: domínio, e-mail, senha da entrada (cifrada) e senha do Grafana.
# Uso (na pasta do projeto, no servidor):  bash deploy/oracle/configurar.sh
# Pode rodar de novo a qualquer momento (ex.: para trocar a senha da entrada); o que não for perguntado é mantido.
set -euo pipefail

cd "$(dirname "$0")/../.."
ENV_ARQ="${NEXUS_ENV:-.env}"
CADDY="caddy:2.11.7-alpine@sha256:eb4d35b7452d1ab6171fbdbe8d9275b2301dad6dad92115d91e19fb9b24d510f"

touch "$ENV_ARQ"
chmod 600 "$ENV_ARQ"   # só o dono lê: tem senhas

atual() { grep -E "^$1=" "$ENV_ARQ" | tail -1 | cut -d= -f2- | sed -e "s/^'//" -e "s/'$//" || true; }

definir() {  # definir CHAVE VALOR  -> substitui a linha da chave ou acrescenta no fim
  awk -v k="$1" -v v="$2" 'BEGIN { FS = "=" }
       $1 == k { print k "=" v; achou = 1; next } { print }
       END { if (!achou) print k "=" v }' "$ENV_ARQ" > "$ENV_ARQ.tmp"
  cat "$ENV_ARQ.tmp" > "$ENV_ARQ" && rm -f "$ENV_ARQ.tmp"
}

gerar() { tr -dc 'A-Za-z0-9' < /dev/urandom | head -c "${1:-20}" || true; }

perguntar() {  # perguntar "Texto" PADRAO -> resposta (Enter = padrão)
  local resp
  read -r -p "$1 [${2}]: " resp
  echo "${resp:-$2}"
}

echo "== Support Nexus · configuração do servidor =="
dominio=$(perguntar "Domínio do link (ex.: nexus-suporte.duckdns.org)" "$(atual NEXUS_DOMINIO)")
email=$(perguntar "E-mail para avisos do certificado HTTPS" "$(atual NEXUS_EMAIL)")
usuario=$(perguntar "Usuário da entrada (o mesmo para toda a equipe)" "$(atual NEXUS_ACESSO_USUARIO || true)")
usuario=${usuario:-equipe}
[ -n "$dominio" ] && [ -n "$email" ] || { echo "Domínio e e-mail são obrigatórios." >&2; exit 1; }

senha=""
if [ -z "$(atual NEXUS_ACESSO_SENHA_HASH)" ] || [ "${1:-}" = "--trocar-senha" ]; then
  read -r -s -p "Senha da entrada (Enter = gerar uma forte): " senha; echo
  if [ -z "$senha" ]; then senha=$(gerar 16); gerada=1; fi
  # o Caddy cifra a senha (bcrypt); a senha em texto não fica gravada em lugar nenhum
  # (pela entrada padrão, não pela linha de comando: assim a senha não aparece na lista de processos)
  hash=$(printf '%s\n' "$senha" | docker run --rm -i "$CADDY" caddy hash-password)
  # aspas simples: o hash tem vários "$", que o docker compose leria como variáveis
  definir NEXUS_ACESSO_SENHA_HASH "'$hash'"
fi

definir NEXUS_DOMINIO "$dominio"
definir NEXUS_EMAIL "$email"
definir NEXUS_ACESSO_USUARIO "$usuario"
definir COMPOSE_FILE "docker-compose.yml:deploy/oracle/docker-compose.oracle.yml"
[ -n "$(atual NEXUS_FUSO)" ] || definir NEXUS_FUSO "America/Sao_Paulo"
[ -n "$(atual GRAFANA_SENHA)" ] || definir GRAFANA_SENHA "$(gerar 24)"

echo
echo "Pronto. .env gravado (permissão 600)."
echo "  Link:    https://$dominio"
echo "  Usuário: $usuario"
if [ -n "$senha" ]; then
  echo "  Senha:   ${gerada:+$senha  (gerada agora: anote, ela não fica salva em texto)}${gerada:-(a que você digitou)}"
fi
echo "Próximo passo: docker compose up -d --build"
