#!/usr/bin/env bash
# Sao lưu PostgreSQL định kỳ (thêm vào cron: 0 2 * * *).
set -euo pipefail
BACKUP_DIR="${BACKUP_DIR:-/var/backups/medforecast}"
RETAIN_DAYS="${RETAIN_DAYS:-30}"
: "${DATABASE_URL:?DATABASE_URL is required}"
mkdir -p "$BACKUP_DIR"
TS="$(date +%Y%m%d_%H%M%S)"
FILE="$BACKUP_DIR/medforecast_${TS}.sql.gz"
pg_dump "$DATABASE_URL" | gzip > "$FILE"
echo "Backup -> $FILE"
find "$BACKUP_DIR" -name 'medforecast_*.sql.gz' -mtime +"$RETAIN_DAYS" -delete
echo "Đã xoá bản sao lưu cũ hơn ${RETAIN_DAYS} ngày."
