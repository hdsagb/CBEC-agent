#!/usr/bin/env bash
# 磁盘每周清理：Docker 缓存/悬空镜像、journald 日志、旧轮转日志、/tmp 旧文件
#
# 用法（在服务器 ~/CBEC-agent 目录下）：
#   ./deploy/cleanup-disk.sh              # 手动跑一次
#   crontab -e 里加（每周日凌晨 4:00）：
#     0 4 * * 0 /root/CBEC-agent/deploy/cleanup-disk.sh >> /var/log/cbec-cleanup.log 2>&1
#
# 只做安全清理：不触碰运行中的容器和在用镜像；
# 可用 DOCKER_CACHE_DAYS / LOG_KEEP_DAYS / TMP_KEEP_DAYS 环境变量覆盖默认值。
set -euo pipefail

DOCKER_CACHE_DAYS="${DOCKER_CACHE_DAYS:-7}"   # 构建缓存保留天数
LOG_KEEP_DAYS="${LOG_KEEP_DAYS:-14}"          # 轮转日志保留天数
TMP_KEEP_DAYS="${TMP_KEEP_DAYS:-7}"           # /tmp 文件保留天数

usage_before=$(df --output=used -BG / | tail -1 | tr -dc '0-9')
echo "[$(date '+%F %T')] 清理开始，根分区已用 ${usage_before}G"

# 1. Docker：清理 7 天前的构建缓存 + 悬空镜像（不影响在用镜像和容器）
# 注意：docker 的 until 过滤器只支持小时格式（如 168h），不认 7d
CACHE_HOURS=$((DOCKER_CACHE_DAYS * 24))
docker builder prune -af --filter "until=${CACHE_HOURS}h" | tail -1 || true
docker image prune -f | tail -1 || true

# 2. journald：压缩 systemd 日志，只保留最近 7 天且总量不超过 100M
journalctl --vacuum-time=7d --vacuum-size=100M 2>&1 | tail -2 || true

# 3. /var/log：删除超过保留期的已轮转日志（.gz / .1 .2 ... 旧文件）
find /var/log -type f \( -name '*.gz' -o -regex '.*\.[0-9]+' \) -mtime +"${LOG_KEEP_DAYS}" -delete 2>/dev/null || true

# 4. /tmp：删除超过保留期的普通文件（跳过正在使用的锁文件等目录项）
find /tmp -xdev -type f -atime +"${TMP_KEEP_DAYS}" -delete 2>/dev/null || true

usage_after=$(df --output=used -BG / | tail -1 | tr -dc '0-9')
echo "[$(date '+%F %T')] 清理完成，根分区已用 ${usage_after}G（释放 $((usage_before - usage_after))G）"
