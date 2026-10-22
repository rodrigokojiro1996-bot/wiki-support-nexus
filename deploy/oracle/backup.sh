#!/usr/bin/env bash
# Backup do Support Nexus no servidor: banco SQLite, manuais e prints (o volume nexus-dados), compactados.
# Uso: bash deploy/oracle/backup.sh            (guarda em ~/backups-nexus, mantém os 14 mais recentes)
# Agendar todo dia às 03:00 (crontab -e):
#   0 3 * * * cd ~/wiki-support-nexus && bash deploy/oracle/backup.sh >> ~/backups-nexus/backup.log 2>&1
set -euo pipefail

cd "$(dirname "$0")/../.."
DESTINO="${NEXUS_BACKUP_DIR:-$HOME/backups-nexus}"
MANTER="${NEXUS_BACKUP_MANTER:-14}"
mkdir -p "$DESTINO"

arquivo="nexus-dados-$(date +%Y%m%d-%H%M).tar.gz"
parcial="$DESTINO/.$arquivo.parcial"
trap 'rm -f "$parcial"' EXIT   # se algo falhar, não sobra um backup pela metade com cara de bom

# o próprio contêiner da aplicação compacta a pasta de dados (volume) e entrega pela saída padrão
docker compose exec -T nexus tar czf - -C /app/backend dados > "$parcial"
gzip -t "$parcial"             # confere se o arquivo está íntegro antes de dar nome de backup
mv "$parcial" "$DESTINO/$arquivo"
echo "$(date '+%F %T') backup: $DESTINO/$arquivo ($(du -h "$DESTINO/$arquivo" | cut -f1))"

# rotação: apaga os mais antigos além dos $MANTER
ls -1t "$DESTINO"/nexus-dados-*.tar.gz | tail -n +"$((MANTER + 1))" | xargs -r rm -f
