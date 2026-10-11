# CBEC Agent（跨境电商智能 Agent）

面向跨境贸易团队的内部效率工具，围绕「报价 → 申报 → 发货」三个环节提供 AI 辅助：

- **F1 智能比价**：上传 Excel / Google Sheet / Word / PDF / 图片五种格式的报价单，AI 解析为结构化数据，人工确认后自动生成多供应商比价看板。
- **F2 申报要素库**：按「客户 + 产品」沉淀报关申报要素历史，检索复用、一键复制报关格式文本。
- **F3 箱唛生成**：模板化管理箱唛，画布编辑后导出 PDF。
- **F4 Agent 对话**：工作台自然语言入口，通过 Function Calling 调度上述三个能力。

> 当前进度：项目骨架阶段（可登录、页面占位、数据模型与 API 路由已就绪）。

## 技术栈

| 层 | 选型 |
| --- | --- |
| 前端 | Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router |
| 后端 | FastAPI + SQLAlchemy 2 + Alembic + PyJWT + bcrypt |
| 数据库 | 本地开发默认 SQLite；生产 PostgreSQL |
| LLM | DeepSeek（可切换的适配层 `backend/app/services/llm/`） |
| 部署 | Docker Compose（postgres + api + nginx） |

## 目录结构

```
cbec-agent/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── main.py          # 应用入口（CORS、路由挂载、/api/health）
│   │   ├── db.py            # SQLAlchemy engine / Session / Base
│   │   ├── core/            # config(环境变量) / security(JWT+bcrypt)
│   │   ├── api/             # deps(认证依赖) + routers(auth/elements/quotes/marks/agent)
│   │   ├── models/          # user / declaration_element / quote / mark / chat
│   │   ├── schemas/         # Pydantic 模型
│   │   ├── parsers/         # 报价单格式路由（Excel/Word/PDF/OCR）
│   │   └── services/        # llm 适配层（DeepSeek）+ agent 编排
│   ├── alembic/             # 数据库迁移
│   └── requirements.txt
├── frontend/                # Vue3 前端
│   └── src/
│       ├── views/           # Login / Dashboard / Elements / Quotes / Marks / Admin
│       ├── layouts/         # MainLayout（侧边导航）
│       ├── router/ stores/ api/
│       └── ...
├── deploy/
│   ├── docker-compose.yml   # postgres + api + nginx
│   └── nginx.conf           # 静态托管 + /api 反代
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

### 创建首个账号

系统不预置账号，通过注册接口创建，首个用户可自选角色：

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/auth/register `
  -H "Content-Type: application/json" `
  -d '{\"username\":\"admin\",\"password\":\"admin123\",\"display_name\":\"管理员\",\"role\":\"admin\"}'
```

角色：`admin` 管理员 / `customs` 关务员 / `merchandiser` 业务员。

### 前端（Node 18+）

```powershell
cd frontend
npm install
npm run dev
```

访问 <http://localhost:5173>（Vite 已配置 `/api` 代理到 8000 端口）。

## 环境变量

复制 `.env.example` 为 `.env` 后按需修改（backend 启动时自动读取）：

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `DATABASE_URL` | 留空用本地 SQLite；生产填 PostgreSQL 连接串 | `sqlite:///./cbec.db` |
| `JWT_SECRET` | JWT 签名密钥，**上线必须改为随机长字符串** | `dev-secret-change-me` |
| `LLM_PROVIDER` | LLM 适配层标识 | `deepseek` |
| `DEEPSEEK_API_KEY` | DeepSeek 平台 API Key | 空 |
| `DEEPSEEK_MODEL` | 模型名 | `deepseek-chat` |
| `UPLOAD_DIR` | 报价单等上传文件、箱唛导出产物的目录 | `./uploads` |
| `MARK_FONT_FILE` | 箱唛导出使用的中文 TrueType 字体路径；留空则自动探测系统字体 | 空 |

## 部署

```powershell
Copy-Item .env.example .env    # 修改 JWT_SECRET、DEEPSEEK_API_KEY、POSTGRES_PASSWORD
docker compose -f deploy/docker-compose.yml up -d --build
```

- Web：<http://localhost:8080>（nginx 托管 `frontend/dist` 构建产物并反代 `/api`）
- 前端构建产物需先执行 `npm run build` 生成（或让 CI/镜像内构建）。
- 生产对外使用请配置域名 + HTTPS。

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

## 第三方参考

开发过程中参考的开源项目及其许可情况见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。License 待项目定稿后补充。
