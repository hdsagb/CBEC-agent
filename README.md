# CBEC Agent（跨境电商智能 Agent）

面向跨境贸易团队的内部效率工具，围绕「报价 → 申报 → 发货」三个环节提供 AI 辅助。

## 功能概览

- **F1 智能比价**：上传 Excel / Word / PDF / 图片四种格式的报价单，自动解析为结构化明细（含置信度），人工确认后生成多供应商加权比价看板；并可按 HS 编码关联历史成交价，对报价做合理性校验。
- **F2 申报要素库**：按「客户 + HS 编码 + 产品」沉淀报关申报要素，支持多维检索、Excel 批量导入（按 HS+商品名+客户去重）与按筛选条件导出、报关格式文本一键复制；详情页展示该商品的历史价格参考。
- **F3 箱唛生成**：模板化管理，画布式可视化编辑（文本 / Logo / 二维码 / 条形码 / 图片），连续箱号自动补齐，导出 300dpi PDF（一箱一页）与 PNG（多箱竖向拼接）。
- **F4 Agent 对话**：自然语言入口，通过 Function Calling 调度「检索申报要素、加权比价、创建箱唛、导出箱唛、批量导入要素、查询比价批次」等工具，支持多轮工具循环与结果自然语言摘要。

其它已实现能力：登录注册与三角色权限（admin / customs / merchandiser）、数据分析报表（供应商价格走势 / 报关品类分布 / 比价节省金额）、供应商主数据与历史报价库、Agent 会话管理（多会话 / 重命名 / 删除）。

> 进度：F1–F4 主干功能均已实现，Agent 已用真实 DeepSeek 完成端到端实测（检索要素 → 比价 → 建箱唛 → 导出 PDF）。剩余为部署收口：镜像实测与公网 HTTPS 需在具备 Docker 与域名的环境执行。

## 技术栈

| 层 | 选型 |
| --- | --- |
| 前端 | Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router（图表为手写 SVG） |
| 后端 | FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 + PyJWT + bcrypt |
| 数据库 | 本地开发默认 SQLite；生产 PostgreSQL |
| LLM | DeepSeek（可切换的适配层 `backend/app/services/llm/`），支持 Function Calling / JSON Mode / 多模态 |
| 文档解析 | openpyxl / python-docx / pypdf + RapidOCR（图片走多模态模型，未配置时回退本地 OCR） |
| 箱唛渲染 | reportlab + Pillow + qrcode + python-barcode |
| 部署 | Docker Compose（postgres + api + nginx） |

## 目录结构

```
cbec-agent/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── main.py          # 应用入口（CORS、路由挂载、/api/health、/uploads 静态托管）
│   │   ├── db.py            # SQLAlchemy engine / Session / Base
│   │   ├── core/            # config(环境变量) / security(JWT+bcrypt)
│   │   ├── api/             # deps(认证+角色依赖) + routers
│   │   │   └── routers/     # auth / elements / quotes / marks / agent / reports / suppliers
│   │   ├── models/          # user / declaration_element / quote / mark / chat / supplier
│   │   ├── schemas/         # Pydantic 模型（含 price_reference / report / supplier）
│   │   ├── parsers/         # 报价单格式路由（Excel / Word / PDF / OCR）
│   │   └── services/        # llm 适配层、agent 编排、comparison、mark_render、
│   │                        # element_excel / element_import、reports、suppliers、price_reference
│   ├── alembic/             # 数据库迁移
│   ├── tests/               # pytest（全量 149 项）
│   ├── Dockerfile
│   ├── .dockerignore
│   └── requirements.txt
├── frontend/                # Vue3 前端
│   └── src/
│       ├── views/           # Login / Dashboard / Elements / Quotes / Marks / Agent
│       │                    # / Suppliers / Reports / Admin
│       ├── components/      # ToolIcon / MarkCanvasEditor
│       ├── layouts/         # MainLayout（侧边导航）
│       ├── router/ stores/ api/
│       └── ...
├── deploy/
│   ├── docker-compose.yml   # postgres + api + nginx
│   └── nginx.conf           # 静态托管 + /api 与 /uploads 反代
├── .env.example
└── THIRD_PARTY_NOTICES.md   # 第三方参考项目登记
```

## 本地开发

### 后端（Python 3.12+）

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

- 启动时自动建表（`Base.metadata.create_all`，SQLite 文件 `backend/cbec.db`）。
- 接口文档：<http://127.0.0.1:8000/docs>
- 需要 LLM 能力（比价解析 / Agent 对话）时，先在 `backend/.env` 配置 `DEEPSEEK_API_KEY`。

### 创建账号

角色分三级：`admin` 管理员 / `customs` 关务员 / `merchandiser` 业务员。
自助注册接口**只能创建 `merchandiser`**（不接受客户端指定角色，防止任何人自助提权），
`admin` 与 `customs` 账号由具备服务器权限的人用运维脚本预置：

```powershell
# 本地开发（在 backend 目录下执行）
.venv\Scripts\python.exe -m app.scripts.create_user admin "改成强密码" --role admin
.venv\Scripts\python.exe -m app.scripts.create_user guanwu "改成强密码" --role customs

# Docker 部署（在仓库根目录执行）
docker compose -f deploy/docker-compose.yml exec api python -m app.scripts.create_user admin "改成强密码" --role admin
```

脚本在用户名重复时直接报错退出，不会覆盖既有密码，可反复执行。
普通业务员如需注册，走登录页的注册入口或 `POST /api/auth/register` 即可。

### 前端（Node 18+）

```powershell
cd frontend
npm install
npm run dev
```

访问 <http://localhost:5173>（Vite 已配置 `/api` 与 `/uploads` 代理到 8000 端口）。

### 测试

```powershell
cd backend
$env:PYTHONDONTWRITEBYTECODE="1"; .venv\Scripts\pytest -p no:cacheprovider
```

## 环境变量

本地开发复制 `.env.example` 为 `backend/.env`；Docker 部署复制为仓库根目录 `.env`（compose 通过 `env_file` 注入）。

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `APP_NAME` | 应用名 | `CBEC Agent` |
| `DATABASE_URL` | 留空用本地 SQLite；生产填 PostgreSQL 连接串 | `sqlite:///./cbec.db` |
| `POSTGRES_PASSWORD` | compose 中 Postgres 密码（生产必改） | `cbec123` |
| `JWT_SECRET` | JWT 签名密钥，**必填**；留空、示例值或短于 16 位时服务拒绝启动 | 无默认值 |
| `LLM_PROVIDER` | LLM 适配层标识 | `deepseek` |
| `DEEPSEEK_API_KEY` | DeepSeek 平台 API Key | 空 |
| `DEEPSEEK_BASE_URL` | DeepSeek API 地址 | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 对话 / 抽取模型 | `deepseek-chat` |
| `LLM_VISION_MODEL` | 图片报价单识别的多模态模型；留空则回退本地 OCR | 空 |
| `LLM_VISION_BASE_URL` | 多模态服务地址；留空复用 DeepSeek 配置 | 空 |
| `LLM_VISION_API_KEY` | 多模态服务 Key；留空复用 `DEEPSEEK_API_KEY` | 空 |
| `OCR_ENABLED` | 是否启用本地 RapidOCR 兜底 | `true` |
| `UPLOAD_DIR` | 上传文件与箱唛导出产物目录 | `./uploads` |
| `MARK_FONT_FILE` | 箱唛导出使用的中文 TrueType 字体路径；留空自动探测系统字体 | 空 |

## 部署（Docker Compose）

### 启动

```powershell
cd frontend; npm run build; cd ..      # nginx 直接挂载 frontend/dist，需先构建
Copy-Item .env.example .env            # 修改 JWT_SECRET、DEEPSEEK_API_KEY、POSTGRES_PASSWORD
docker compose -f deploy/docker-compose.yml up -d --build
```

- Web：<http://localhost:8080>（nginx 托管 `frontend/dist` 并反代 `/api`、`/uploads`）
- api 服务内置健康检查（`/api/health`），`restart: unless-stopped` 保证异常自恢复。
- Postgres 端口仅绑定 `127.0.0.1`，不对公网暴露；如需从外部连库请自行调整并加访问控制。

### 中文字体（箱唛导出必需）

箱唛导出由 reportlab / Pillow 渲染，运行时必须能取到一款**中文 TrueType 字体**。
`fonts-noto-cjk` 提供的是 CFF 轮廓（sfnt tag `OTTO`），reportlab 无法嵌入、导出 PDF 会失败，
请改用 TrueType 轮廓的中文字体（文泉驿、Droid Sans Fallback 等）。取不到可用字体时，
导出接口会返回 500 并提示。查找顺序：

1. 环境变量 `MARK_FONT_FILE` 指定的字体文件；
2. 仓库内 `backend/app/assets/fonts/` 下自放的 `.ttf` / `.ttc`；
3. 系统字体：Windows 微软雅黑 / 黑体 / 宋体，Linux 文泉驿 / Droid，macOS PingFang。

`backend/Dockerfile` 已内置安装 `fonts-wqy-microhei` 与 `fonts-droid-fallback`，无需额外处理。
非 Docker 部署请自行安装，例如：

```bash
# Debian / Ubuntu
apt-get install -y fonts-wqy-microhei fonts-droid-fallback
# RHEL / openSUSE
dnf install -y wqy-microhei-fonts
```

装完可用 `fc-list :lang=zh` 确认中文字体是否就绪；也可把任意 TrueType 字体文件挂载进容器，
再用 `MARK_FONT_FILE` 指向它。

### 公网 + HTTPS

`deploy/nginx.conf` 默认只监听 80，适用于内网或联调。对外发布需自行补上 TLS：

1. 域名解析到服务器，安全组放行 80 / 443；
2. 申请证书：Let's Encrypt（certbot）或云厂商免费证书，落盘到宿主机目录（如 `deploy/certs/`）；
3. 在 `deploy/nginx.conf` 增加 443 server 块，并把 80 的 server 改为跳转：

```nginx
server {
    listen 80;
    server_name your.domain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name your.domain.com;
    ssl_certificate     /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;
    # 其余 location（/api/、/uploads/、/）与 80 配置保持一致
}
```

4. 在 compose 中把 `web` 的端口映射改为 `"443:443"`（并按需保留 `"80:80"`），
   同时挂载证书目录：`- ./certs:/etc/nginx/certs:ro`。

### 上线前安全清单

- `JWT_SECRET` 改为足够长的随机字符串（服务已内置启动自检，示例值或短于 16 位会直接拒绝启动）；
- `admin` / `customs` 账号通过运维脚本创建，不要依赖注册接口自选角色（该入口已封死）；
- `POSTGRES_PASSWORD` 改为强密码，且数据库不对公网开放（compose 默认已绑定 `127.0.0.1`）；
- 确认 `.env` 未提交到仓库（`.gitignore` 已忽略）；
- 仅通过 HTTPS 对外提供服务；
- 数据卷 `pgdata`、`uploads` 纳入备份（两者的持久化目录分别为 Postgres 数据目录与 `/app/uploads`）。

## 第三方参考

开发过程中参考的开源项目及其许可情况见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。License 待项目定稿后补充。