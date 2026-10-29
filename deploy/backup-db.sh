#!/usr/bin/env bash
# PostgreSQL 每日备份：pg_dump 自定义格式 + 完整性校验 + 保留最近 N 份
#
# 用法（在服务器 ~/CBEC-agent 目录下）：
#   ./deploy/backup-db.sh                 # 手动跑一次
#   crontab -e 里加：
#     30 3 * * * cd /root/CBEC-agent && ./deploy/backup-db.sh >> /var/log/cbec-backup.log 2>&1
#
# 备份写到应用目录之外（默认 /var/backups/cbec），避免重新部署时被覆盖；
# 可用 BACKUP_DIR / KEEP / COMPOSE_FILE 环境变量覆盖默认值。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$SCRIPT_DIR/docker-compose.yml}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/cbec}"
KEEP="${KEEP:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"
TARGET="$BACKUP_DIR/cbec-$STAMP.dump"

mkdir -p "$BACKUP_DIR"

# 先写临时文件再改名，避免中途失败留下半个备份被当成有效文件
docker compose -f "$COMPOSE_FILE" exec -T postgres \
    pg_dump -U cbec -d cbec -Fc > "$TARGET.tmp"
mv "$TARGET.tmp" "$TARGET"

# 完整性校验：能列出归档目录说明文件结构完好，可被 pg_restore 使用
# 注意 pg_restore 不接受 "-" 作为 stdin 占位符，省略文件名即从标准输入读取
if ! docker compose -f "$COMPOSE_FILE" exec -T postgres \
        pg_restore -l < "$TARGET" > /dev/null; then
    echo "[$(date '+%F %T')] 校验失败，已删除: $TARGET" >&2
    rm -f "$TARGET"
    exit 1
fi

sha256sum "$TARGET" > "$TARGET.sha256"

# 只保留最近 KEEP 份（列表已按时间倒序，从第 KEEP+1 条开始删）
ls -1t "$BACKUP_DIR"/cbec-*.dump 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f

# 清理已无对应备份文件的校验文件
for f in "$BACKUP_DIR"/cbec-*.dump.sha256; do
    [ -e "${f%.sha256}" ] || rm -f "$f"
done

echo "[$(date '+%F %T')] 备份完成 $TARGET ($(du -h "$TARGET" | cut -f1))，当前保留 $(ls -1 "$BACKUP_DIR"/cbec-*.dump | wc -l) 份"
