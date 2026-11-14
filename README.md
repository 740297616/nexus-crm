# Nexus CRM

企业内部 CRM 系统，采用前后端分离和模块化单体架构。

## Phase 0 基础设施

当前阶段完成前端管理后台骨架、FastAPI 基础服务、PostgreSQL 连接配置、Alembic 基线迁移、统一响应/异常处理、健康检查和 Docker Compose 配置。登录、用户、角色、客户等业务功能将在后续 Phase 实现。

## 本地开发

复制环境变量文件：

```powershell
Copy-Item .env.example .env
```

启动后端：

```powershell
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动前端：

```powershell
cd frontend
pnpm install
pnpm dev
```

前端默认地址为 `http://localhost:5173`，后端文档为 `http://localhost:8000/docs`，健康检查为 `http://localhost:8000/healthz` 和 `http://localhost:8000/readyz`。

## Docker Compose

开发环境支持前后端热更新，并为 PostgreSQL 提供持久化 Volume：

```powershell
docker compose -f docker-compose.dev.yml up --build
```

停止并移除容器：

```powershell
docker compose -f docker-compose.dev.yml down
```

## 质量检查

```powershell
# frontend/
pnpm typecheck
pnpm lint
pnpm format:check
pnpm test:unit
pnpm build

# backend/
uv run ruff format --check app tests migrations
uv run ruff check app tests migrations
uv run pytest
uv run alembic upgrade head
```

详细架构、数据模型、API、权限和阶段验收要求见 [PROJECT_SPEC.md](PROJECT_SPEC.md)，AI 开发约束见 [AGENTS.md](AGENTS.md)。
