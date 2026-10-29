#!/usr/bin/env bash
# 一键发布：拉取代码 → 构建前端 → 重建容器 → 健康检查
#
# 用法（在服务器仓库根目录执行）：
#   ./deploy/release.sh                 # 完整发布
#   ./deploy/release.sh --no-pull       # 跳过 git pull（脚本尚未入库时使用）
#   ./deploy/release.sh --skip-frontend # 仅后端变更，跳过前端构建
#
# 可用环境变量覆盖默认值：
#   WEB_PORT=8080        对外端口（健康检查用）
#   NPM_REGISTRY=...     npm 源（默认 https://registry.npmmirror.com）
#   HEALTH_RETRIES=60    健康检查最大尝试次数，每次间隔 2 秒
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/deploy/docker-compose.yml"
WEB_PORT="${WEB_PORT:-8080}"
HEALTH_RETRIES="${HEALTH_RETRIES:-60}"
NPM_REGISTRY="${NPM_REGISTRY:-https://registry.npmmirror.com}"
LOCK_FILE="${TMPDIR:-/tmp}/cbec-release.lock"

DO_PULL=1
DO_FRONTEND=1

usage() {
    sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

for arg in "$@"; do
    case "$arg" in
        --no-pull) DO_PULL=0 ;;
        --skip-frontend) DO_FRONTEND=0 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "未知参数：$arg（支持 --no-pull / --skip-frontend）" >&2; exit 2 ;;
    esac
done

log() { echo "[$(date '+%F %T')] $*"; }

# 防止并发发布互相覆盖
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "已有发布流程在运行（$LOCK_FILE），本次退出" >&2
    exit 1
fi

cd "$ROOT_DIR"

[ -f "$ROOT_DIR/.env" ] || { echo "缺少 $ROOT_DIR/.env（api 运行必需）" >&2; exit 1; }
[ -f "$ROOT_DIR/deploy/.env" ] || { echo "缺少 $ROOT_DIR/deploy/.env（compose 插值数据库密码）" >&2; exit 1; }

if [ "$DO_PULL" -eq 1 ]; then
    log "拉取代码（当前分支 $(git rev-parse --abbrev-ref HEAD)）"
    git pull --ff-only
fi

if [ "$DO_FRONTEND" -eq 1 ]; then
    command -v npm >/dev/null 2>&1 || {
        echo "未找到 npm，无法构建前端；请安装 Node.js，或仅后端变更时加 --skip-frontend" >&2
        exit 1
    }
    log "构建前端"
    npm_args=(ci --no-audit --no-fund --registry="$NPM_REGISTRY")
    ( cd "$ROOT_DIR/frontend" && npm "${npm_args[@]}" && npm run build )
    [ -f "$ROOT_DIR/frontend/dist/index.html" ] || {
        echo "前端构建产物缺失：frontend/dist/index.html" >&2
        exit 1
    }
fi

log "重建并启动容器"
docker compose -f "$COMPOSE_FILE" up -d --build

# 绑定挂载的 nginx.conf 变化不会触发容器重建，主动 reload 使其生效
docker compose -f "$COMPOSE_FILE" exec -T web nginx -s reload

log "健康检查 http://127.0.0.1:$WEB_PORT/api/health"
healthy=0
for _ in $(seq 1 "$HEALTH_RETRIES"); do
    if curl -fsS --max-time 5 "http://127.0.0.1:$WEB_PORT/api/health" 2>/dev/null \
        | grep -q '"database": *"ok"'; then
        healthy=1
        break
    fi
    sleep 2
done

if [ "$healthy" -ne 1 ]; then
    echo "健康检查失败，输出最近状态与日志：" >&2
    docker compose -f "$COMPOSE_FILE" ps >&2
    docker compose -f "$COMPOSE_FILE" logs --tail=50 api >&2
    exit 1
fi

log "发布完成：$(git rev-parse --short HEAD)，前端入口 $(ls -t "$ROOT_DIR/frontend/dist/assets" 2>/dev/null | head -n1)"
docker compose -f "$COMPOSE_FILE" ps
