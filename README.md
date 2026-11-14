# Nexus CRM

企业内部 CRM 系统，采用前后端分离和模块化单体架构。

## 项目阶段

当前仓库已完成基础设施、认证系统，以及组织架构与 RBAC 管理基线。客户、联系人和跟进业务尚未实现。

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

认证接口已接入 `/api/v1/auth`：`login`、`refresh`、`logout`、`me` 和 `change-password`。请在本地 `.env` 中设置随机的 `JWT_SECRET_KEY`；Access Token 只在内存中使用，Refresh Token 由服务端保存哈希并轮换。

组织与权限 API：`/api/v1/users`、`/api/v1/departments`、`/api/v1/roles` 和 `/api/v1/permissions`。迁移会建立“系统管理员”“部门主管”“普通员工”三个预置角色及菜单、页面、API 权限目录。迁移不会创建默认口令或演示用户。

创建首个系统管理员前先执行 Alembic 迁移，然后在后端目录设置一次性初始账号环境变量并运行 bootstrap 命令：

```powershell
$env:INITIAL_ADMIN_USERNAME = "admin"
$env:INITIAL_ADMIN_DISPLAY_NAME = "系统管理员"
$securePassword = Read-Host "输入至少 12 位初始密码" -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
  $env:INITIAL_ADMIN_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
  uv run python -m app.scripts.bootstrap_admin
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
  $securePassword.Dispose()
  Remove-Item Env:INITIAL_ADMIN_PASSWORD
  Remove-Item Env:INITIAL_ADMIN_USERNAME
  Remove-Item Env:INITIAL_ADMIN_DISPLAY_NAME
}
```

Bootstrap 只在系统中尚无系统管理员时创建账号；不会输出密码，也不会把凭据写入仓库。管理员登录后可通过用户管理页面创建主管和员工账号。

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

后端集成测试默认使用隔离 SQLite 数据库。要在专用 PostgreSQL 测试库运行同一套接口和权限测试，先创建一个可丢弃的空测试数据库，然后从 `backend/` 设置 `TEST_DATABASE_URL` 并运行 `uv run pytest`；测试启动时会重建该库中的表。

详细架构、数据模型、API、权限和阶段验收要求见 [PROJECT_SPEC.md](PROJECT_SPEC.md)，AI 开发约束见 [AGENTS.md](AGENTS.md)。
