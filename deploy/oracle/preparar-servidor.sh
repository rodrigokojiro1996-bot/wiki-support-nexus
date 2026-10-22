#!/usr/bin/env bash
# Prepara um servidor Ubuntu 24.04 novo (Oracle Cloud) para o Support Nexus. Rodar UMA vez:
#   sudo bash deploy/oracle/preparar-servidor.sh
# Faz: atualizações, Docker oficial, fuso de São Paulo, atualizações automáticas de segurança,
#      portas 80/443 no firewall interno da imagem da Oracle e swap se a máquina tiver pouca memória.
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "Rode com sudo." >&2; exit 1; }
USUARIO=${SUDO_USER:-ubuntu}

echo "== 1/6 atualizando o sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get upgrade -y -q
apt-get install -y -q ca-certificates curl git unattended-upgrades netfilter-persistent iptables-persistent

echo "== 2/6 Docker (repositório oficial)"
if ! command -v docker >/dev/null; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -q
  apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
usermod -aG docker "$USUARIO"   # o usuário roda "docker" sem sudo (vale a partir do próximo login)

echo "== 3/6 fuso horário"
timedatectl set-timezone America/Sao_Paulo

echo "== 4/6 atualizações automáticas de segurança"
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "== 5/6 firewall interno: liberar 80 e 443"
# A imagem Ubuntu da Oracle vem com regras de iptables que recusam tudo além do SSH (porta 22).
# As regras novas entram ANTES da linha REJECT, senão não valem.
pos=$(iptables -L INPUT --line-numbers | awk '/REJECT/ { print $1; exit }')
for regra in "-p tcp --dport 80" "-p tcp --dport 443" "-p udp --dport 443"; do
  # shellcheck disable=SC2086
  if ! iptables -C INPUT -m state --state NEW $regra -j ACCEPT 2>/dev/null; then
    # shellcheck disable=SC2086
    iptables -I INPUT "${pos:-1}" -m state --state NEW $regra -j ACCEPT
  fi
done
netfilter-persistent save

echo "== 6/6 swap (só em máquina com menos de 4 GB)"
mem_mb=$(awk '/MemTotal/ { print int($2 / 1024) }' /proc/meminfo)
if [ "$mem_mb" -lt 4000 ] && [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo "/swapfile none swap sw 0 0" >> /etc/fstab
  echo "   swap de 2 GB criado (máquina com ${mem_mb} MB)"
fi

echo
echo "Servidor pronto. Saia e entre de novo no SSH (para o grupo docker valer) e siga o docs/oracle-cloud.md."
