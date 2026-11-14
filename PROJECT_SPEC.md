# Nexus CRM 项目规范

> 版本：v0.1（首版设计基线）  
> 状态：设计阶段  
> 适用范围：企业内部 CRM 首版，10–50 名用户，模块化单体，前后端分离

## 1. 项目目标与边界

### 1.1 产品目标

为企业内部员工提供统一的客户、联系人和跟进记录管理能力，确保客户信息可检索、跟进过程可追溯、访问范围可控制，并为后续报表和流程扩展保留清晰边界。

### 1.2 首版范围

- 账号登录、退出、刷新令牌和当前用户信息。
- 用户、部门、角色、权限的基础管理。
- 客户档案：名称、来源、行业、联系方式、地址、负责人、状态、备注。
- 联系人档案：姓名、职位、电话、邮箱、所属客户、主要联系人标识。
- 跟进记录：跟进方式、时间、内容、结果、下次跟进时间、关联客户/联系人。
- 基础列表搜索、筛选、排序、分页，以及客户详情下的关联数据查看。
- 数据范围权限、敏感操作审计日志。
- 面向内部管理的基础统计接口和页面；首版不建设复杂 BI。

### 1.3 明确不做的内容

首版不引入 Redis、Celery、微服务、Kubernetes、消息队列、全文搜索引擎、工作流引擎、复杂多租户、外部营销自动化、计费、移动端原生应用和实时协同。需要异步任务时，先使用可观测的同步实现或数据库内可恢复的简单机制，并在需求评审后再扩展。

### 1.4 非功能目标

- 10–50 名并发用户下，常用列表接口 p95 目标小于 500 ms，详情和写入接口 p95 目标小于 800 ms（以测试环境基线为准）。
- 所有业务表使用 UTC 时间存储，API 使用 ISO 8601；前端按用户时区展示。
- 关键写操作具备权限校验、事务边界和审计记录。
- 后端类型检查、Lint、单元测试和集成测试纳入 CI；前端单元测试、端到端冒烟测试纳入 CI。
- 迁移可在空数据库和上一版本数据库上重复验证，禁止手工改生产表结构。

## 2. 固定技术栈与工程决策

### 2.1 技术栈

前端固定使用 Vue 3、TypeScript strict、Vite、Element Plus、Pinia、Vue Router、Axios、ECharts、pnpm。后端固定使用 Python 3.12+、FastAPI、SQLAlchemy 2.0 同步模式、Pydantic 2、Alembic、PostgreSQL、PyJWT、Argon2id、uv。工程化固定使用 Docker、Docker Compose、Caddy、Pytest、Vitest、Playwright、Ruff、ESLint、Prettier。

### 2.2 总体架构

```text
Browser
  └─ Caddy（静态文件、/api 反向代理、HTTPS）
       ├─ Frontend Vue SPA
       └─ Backend FastAPI /api/v1
              └─ PostgreSQL
```

- 前后端完全分离，只通过 RESTful JSON API 通信。
- 后端是模块化单体：模块在同一进程和数据库中部署，模块之间通过服务接口或领域事件约定协作，禁止跨模块直接修改对方内部对象。
- 所有 API 使用 `/api/v1` 前缀；健康检查使用 `/healthz` 和 `/readyz`，不属于业务 API。
- SQLAlchemy 使用同步 `Session`；每个请求使用明确的事务边界，读操作默认只读，写操作由 Service 提交事务。
- Alembic 是唯一数据库结构变更入口；Model 只描述映射，不作为迁移文件的替代品。

## 3. 推荐目录结构

以下是目标结构；当前阶段只建立规范文档，不创建业务代码目录。

```text
nexus-crm/
├─ frontend/
│  ├─ src/
│  │  ├─ app/                 # 应用启动、全局配置、错误处理
│  │  ├─ api/                 # Axios 实例、拦截器、按资源封装的 API client
│  │  ├─ assets/
│  │  ├─ components/          # 跨页面复用的展示/交互组件
│  │  ├─ composables/         # 可复用的 Vue 逻辑
│  │  ├─ layouts/
│  │  ├─ router/
│  │  ├─ stores/              # Pinia：认证、用户、权限等客户端状态
│  │  ├─ types/               # API DTO 与前端领域类型
│  │  ├─ utils/
│  │  └─ views/               # 按业务模块组织页面
│  ├─ tests/unit/
│  ├─ tests/e2e/
│  ├─ package.json
│  ├─ pnpm-lock.yaml
│  ├─ vite.config.ts
│  └─ tsconfig*.json
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ core/                # 配置、日志、安全、异常、依赖注入
│  │  ├─ db/                  # engine、Session、Base、事务工具
│  │  ├─ api/
│  │  │  └─ v1/              # 路由聚合与版本入口
│  │  └─ modules/
│  │     ├─ auth/
│  │     ├─ users/
│  │     ├─ organizations/   # 部门与组织树
│  │     ├─ roles/
│  │     ├─ customers/
│  │     ├─ contacts/
│  │     ├─ followups/
│  │     ├─ dashboard/
│  │     └─ audit_logs/
│  ├─ migrations/             # Alembic env.py 与 versions/
│  ├─ tests/
│  │  ├─ unit/
│  │  └─ integration/
│  ├─ pyproject.toml
│  └─ uv.lock
├─ deploy/
│  ├─ Caddyfile
│  ├─ docker-compose.yml
│  ├─ docker-compose.test.yml
│  ├─ frontend.Dockerfile
│  └─ backend.Dockerfile
├─ docs/
│  ├─ adr/                    # 有影响的架构决策记录
│  └─ api/                    # 必要时维护 API 使用说明
├─ AGENTS.md
├─ PROJECT_SPEC.md
└─ README.md
```

### 3.1 后端模块内部约定

每个业务模块按以下职责拆分：

```text
modules/customers/
├─ router.py       # HTTP 参数、依赖、响应；不放业务规则
├─ service.py      # 用例编排、事务、业务规则
├─ repository.py   # 查询和持久化；不决定权限策略
├─ model.py        # SQLAlchemy ORM 映射
├─ schema.py       # Pydantic 请求、响应、筛选模型
└─ permissions.py  # 该模块的权限名和资源级校验辅助
```

Router 只能调用 Service。Service 可以调用本模块 Repository 及明确声明的其他模块 Service；禁止在 Router 中直接写 SQL、提交事务或拼装复杂权限逻辑。

## 4. 核心数据模型（ER 设计）

### 4.1 关系概览

```text
departments 1──N users
departments 1──N departments (parent_id)
users N──N roles ──N──N permissions
users 1──N customers (owner_id)
departments 1──N customers (department_id)
customers 1──N contacts
customers 1──N follow_ups
contacts 0..1──N follow_ups
customers N──N users (customer_collaborators)
users 1──N audit_logs
users 1──N refresh_tokens
```

### 4.2 表与关键字段

所有表至少包含 `id`（UUID）、`created_at`、`updated_at`；软删除只在需要保留历史关联的业务表上使用 `deleted_at`，列表默认过滤已删除数据。

| 表 | 关键字段与约束 |
|---|---|
| `departments` | `id`, `name`, `parent_id`（自引用，可空）, `is_active`；同一父节点下名称唯一；禁止形成环。 |
| `users` | `id`, `username` 唯一, `email` 唯一可空, `password_hash`, `display_name`, `department_id`, `status`（active/disabled）, `last_login_at`；禁用用户不能登录。 |
| `roles` | `id`, `name` 唯一, `code` 唯一, `description`, `data_scope`（self/department/subtree/all）, `is_system`；系统角色不可被普通管理员删除。 |
| `permissions` | `id`, `code` 唯一, `name`, `resource`, `action`, `permission_type`（menu/page/api）；代码由后端常量维护，数据库保存展示信息。 |
| `user_roles` | `user_id`, `role_id`；联合主键，避免重复分配。 |
| `role_permissions` | `role_id`, `permission_id`；联合主键。 |
| `customers` | `id`, `name`, `code` 唯一, `source`, `industry`, `phone`, `email`, `address`, `status`, `owner_id`, `department_id`, `remark`, `deleted_at`；`owner_id` 和 `department_id` 必填。 |
| `contacts` | `id`, `customer_id`, `name`, `title`, `phone`, `email`, `is_primary`, `remark`, `deleted_at`；同一客户最多一个有效主要联系人。 |
| `follow_ups` | `id`, `customer_id`, `contact_id` 可空, `user_id`, `followed_at`, `method`, `content`, `result`, `next_follow_up_at` 可空；客户必须存在，联系人必须属于该客户。 |
| `customer_collaborators` | `customer_id`, `user_id`, `granted_by`, `created_at`；用于在角色数据范围之外显式共享客户，联合主键。 |
| `refresh_tokens` | `id`, `user_id`, `token_hash`, `expires_at`, `revoked_at`, `replaced_by_id`, `created_at`, `last_used_at`；只存哈希，支持轮换和撤销。 |
| `audit_logs` | `id`, `actor_user_id` 可空, `action`, `resource_type`, `resource_id` 可空, `before_data` JSONB 可空, `after_data` JSONB 可空, `request_id`, `ip_address`, `user_agent`, `created_at`；只追加，不提供业务 API 修改/删除。 |

### 4.3 索引、完整性和并发

- `users(username)`, `users(email)`, `customers(code)`, `customers(owner_id, status)`, `customers(department_id, status)`, `contacts(customer_id)`, `follow_ups(customer_id, followed_at DESC)`, `audit_logs(resource_type, resource_id, created_at DESC)` 建立索引。
- 客户名称使用普通索引或前缀查询；首版不承诺模糊搜索的全文检索能力。
- 外键默认使用 `RESTRICT` 或明确的软删除策略，避免删除父记录导致业务历史丢失。
- 客户、联系人、跟进记录写入必须在同一事务内完成关联校验；出现并发更新时返回 `409 CONFLICT`。
- 需要唯一性的业务规则优先由数据库约束兜底，再在 Service 中提供友好错误。

## 5. API 规范

### 5.1 命名与通用约定

- 基础地址：`/api/v1`；资源使用复数名词，例如 `/customers`、`/contacts`、`/follow-ups`。
- 使用标准 HTTP 方法：GET 查询，POST 创建，PATCH 局部更新，DELETE 仅用于明确允许的软删除/撤销。
- ID 使用 UUID 字符串；时间使用带时区的 ISO 8601，服务端统一存 UTC。
- 列表参数统一支持 `page`（从 1 开始）、`page_size`（默认 20，最大 100）、`sort_by`、`sort_order`；资源特有筛选使用明确字段名。
- 请求头 `Authorization: Bearer <access_token>`；服务端响应 `X-Request-ID`，并在响应体返回同一值。

### 5.2 响应封装

成功响应：

```json
{
  "success": true,
  "data": { "id": "...", "name": "示例客户" },
  "meta": null,
  "request_id": "01J..."
}
```

列表响应：

```json
{
  "success": true,
  "data": { "items": [], "total": 0 },
  "meta": { "page": 1, "page_size": 20, "total_pages": 0 },
  "request_id": "01J..."
}
```

错误响应：

```json
{
  "success": false,
  "error": {
    "code": "CUSTOMER_NOT_FOUND",
    "message": "客户不存在或无权访问",
    "details": null
  },
  "request_id": "01J..."
}
```

`message` 面向用户且不泄露内部细节；`details` 只放可安全展示的字段错误或分页信息，不返回堆栈和 SQL。

### 5.3 错误码基线

| HTTP | 错误码 | 使用场景 |
|---:|---|---|
| 400 | `VALIDATION_ERROR` | 请求体、查询参数或字段格式不合法 |
| 401 | `AUTH_REQUIRED` / `TOKEN_INVALID` / `TOKEN_EXPIRED` / `AUTH_INVALID_CREDENTIALS` / `ACCOUNT_DISABLED` | 缺少、无效或过期令牌，或认证信息/账号状态不合法 |
| 403 | `PERMISSION_DENIED` / `DATA_SCOPE_DENIED` | 无操作权限或超出数据范围 |
| 404 | `RESOURCE_NOT_FOUND` / `CUSTOMER_NOT_FOUND` | 资源不存在或对当前用户不可见 |
| 409 | `DUPLICATE_RESOURCE` / `CONFLICT` | 唯一键冲突或并发版本冲突 |
| 422 | `BUSINESS_RULE_VIOLATION` | 请求格式正确但违反业务规则 |
| 429 | `RATE_LIMITED` | 登录等敏感接口触发限流（由网关/应用实现） |
| 500 | `INTERNAL_ERROR` | 未预期错误；必须记录 request_id |
| 503 | `SERVICE_UNAVAILABLE` | 数据库或依赖不可用 |

### 5.4 首版核心端点

```text
POST   /auth/login
POST   /auth/refresh
POST   /auth/logout
GET    /auth/me
POST   /auth/change-password

GET/POST/PATCH /users
PUT              /users/{user_id}/roles
PATCH            /users/{user_id}/status
GET/POST/PATCH/DELETE /departments
GET/POST/PATCH/DELETE /roles
PUT              /roles/{role_id}/permissions
GET              /permissions

GET/POST/PATCH/DELETE /customers
GET/POST/PATCH/DELETE /customers/{customer_id}/contacts
GET/POST/PATCH/DELETE /customers/{customer_id}/follow-ups
POST                   /customers/{customer_id}/collaborators
DELETE                 /customers/{customer_id}/collaborators/{user_id}

GET    /dashboard/summary
GET    /audit-logs
GET    /healthz
GET    /readyz
```

实际端点以 OpenAPI 为准；每个端点都必须定义请求 Schema、响应 Schema、所需权限和数据范围行为。

## 6. 认证、授权与数据范围

### 6.1 认证

- 登录使用用户名/邮箱加密码；密码使用 Argon2id 哈希，禁止保存明文或可逆密文。
- 登录成功返回短期 access JWT（建议 15 分钟）和长期 refresh token（建议 7 天）。JWT 至少包含 `sub`、`jti`、`iat`、`exp`、`token_type`；不把完整角色列表塞入令牌。
- refresh token 只保存数据库哈希，采用轮换策略：刷新成功后撤销旧 token 并生成新 token；重复使用已撤销 token 时撤销该用户全部 refresh token 并记录审计。
- 登出撤销当前 refresh token；禁用用户、修改密码或管理员强制下线时撤销该用户全部 refresh token。
- 登录失败响应不区分“用户不存在”和“密码错误”；敏感事件写审计日志。生产部署必须通过 Caddy/HTTPS 传输。

### 6.2 RBAC

权限采用稳定代码，例如 `customer:read`、`customer:create`、`customer:update`、`customer:delete`、`follow_up:read`、`user:manage`、`audit_log:read`。角色分配权限，用户分配角色；权限判断集中在依赖和 Service 层。

当前组织与 RBAC 基线角色：

- `system_admin`：全部组织、用户和权限管理权限，全部数据范围；由受控 bootstrap 创建首个账号。
- `department_manager`：读取本部门及下属部门组织和用户，查看角色目录；无用户创建、禁用或权限配置权限。
- `employee`：只访问工作台，无组织和账号管理权限。

CRM 业务启用后再增加销售角色和客户数据范围策略；菜单权限、页面权限和 API 操作权限使用同一 `resource:action` 代码规范，但必须分别记录权限类型。前端菜单和按钮只改善可见性，后端 API 必须单独授权。

角色只是默认权限模板；后续新增角色必须写明权限和数据范围，不在页面中硬编码角色名称。

### 6.3 数据范围

数据范围由用户所有角色的有效范围合并，取更宽范围；`system_admin` 始终为 `all`。

- `self`：资源 `owner_id = current_user.id`，以及用户自己创建的跟进记录。
- `department`：资源 `department_id = current_user.department_id`。
- `subtree`：当前部门及其所有下属部门；部门树查询必须防环并可缓存于请求上下文。
- `all`：全部未删除资源。
- `customer_collaborators`：客户被明确共享给当前用户时可读；修改/删除仍需对应写权限和 Service 规则。

所有 Repository 的资源查询必须通过统一的 scope 条件构造器；详情、更新、删除和关联资源查询必须使用同一范围过滤，不能只保护列表接口。越权资源统一返回 404 或 `RESOURCE_NOT_FOUND`，避免泄露资源存在性。

### 6.4 审计

登录成功/失败、令牌撤销、密码和角色变更、用户启停用、客户/联系人/跟进创建修改删除、数据共享、批量操作都写 `audit_logs`。审计写入与业务变更使用同一事务；审计失败时业务事务失败。敏感字段（密码、令牌）绝不写入 before/after。

## 7. 测试与质量门禁

- 后端：Ruff format/check、Pytest 单元测试（Service、权限、Schema）和集成测试（API + PostgreSQL）。
- 前端：ESLint、Prettier check、TypeScript strict、Vitest（状态、API 映射、关键组件）和 Playwright（登录、客户 CRUD、数据越权冒烟）。
- 关键业务必须覆盖：登录/刷新/登出、数据范围边界、客户联系人关联校验、跟进创建、角色变更审计、禁用用户不可登录。
- CI 至少执行格式检查、Lint、类型检查、单元测试、迁移升级测试和构建；主分支禁止带失败门禁的合并。
- 日志包含 `request_id`、用户 ID（若已认证）、路由、状态码和耗时；生产日志禁止密码、token、完整个人敏感信息。

## 8. 分阶段开发路线与验收标准

### Phase 0：项目基线（当前阶段）

交付物：`PROJECT_SPEC.md`、`AGENTS.md`、目录结构约定、ER 模型、API/错误码、认证与数据范围设计、路线图。验收：文档可独立指导开发；技术栈与约束无冲突；首版边界和每阶段验收标准明确；不包含业务代码实现。

### Phase 1：工程骨架与身份基础

交付物：前后端可启动骨架、Docker Compose、Caddy 代理、配置管理、PostgreSQL 连接、Alembic 初始迁移、统一响应/异常、日志和健康检查、认证基础。验收：空库迁移成功；前端能通过 `/api/v1` 登录；access/refresh 轮换可验证；测试和构建门禁通过。

### Phase 1.2：组织架构与 RBAC

交付物：用户、部门、角色、权限和多对多关联；预置系统管理员、部门主管、普通员工角色；菜单/页面/API 权限目录；用户、部门、角色管理页面；首个系统管理员 bootstrap 命令。验收：管理员、主管、员工三种身份的菜单/API 权限矩阵测试通过；主管的用户查询遵守部门子树范围；员工无法访问管理 API；禁用用户会撤销 Refresh Token；系统角色权限不可被普通管理员修改；数据库在临时 PostgreSQL 环境执行 upgrade/downgrade 验证。

### Phase 2：CRM 数据范围与业务授权

交付物：销售角色、客户数据四级范围、统一 scope 查询和 CRM 业务资源授权。验收：列表、详情、更新、删除均无法越权；本人、部门、下属部门和全部范围正确；越权不泄露资源存在性；管理员操作有审计记录。

### Phase 3：客户与联系人

交付物：客户和联系人真实 CRUD、搜索筛选分页、负责人/部门归属、主要联系人约束、客户共享、详情关联展示。验收：唯一约束、软删除、跨客户联系人校验、共享权限和并发冲突可测试；前端表单校验和错误展示完整；核心流程 Playwright 通过。

### Phase 4：跟进与基础仪表盘

交付物：跟进记录、下次跟进、客户时间线、基础统计接口和 ECharts 页面。验收：跟进只能关联可见客户及其联系人；统计结果遵守当前用户数据范围；时间和时区显示正确；关键写入带审计；接口性能达到本规范目标。

### Phase 5：发布加固

交付物：生产 Compose 配置、Caddy HTTPS 配置说明、备份/恢复演练、迁移回滚策略、权限矩阵文档、监控与日志运行手册、安全检查和发布清单。验收：可从空环境部署并回滚；备份可恢复；关键接口、依赖故障和未授权访问有可观测结果；发布清单逐项通过。

每个 Phase 结束前必须更新 OpenAPI、迁移说明、测试覆盖和变更记录；未达到验收标准的内容不得标记完成。

## 9. 技术风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| 数据范围条件散落在各处 | 越权或权限不一致 | 统一 scope 构造器，Repository 接收范围上下文，增加跨端点越权测试。 |
| 同步 SQLAlchemy 在慢查询下阻塞请求 | 延迟升高 | 先建立索引和分页上限，记录慢查询；规模增长前再评估异步或读副本。 |
| JWT 无状态导致强制下线困难 | 账号风险扩大 | access 短时效，refresh 数据库轮换/撤销；密码变更撤销全部 refresh token。 |
| 组织树出现环或层级过深 | 数据范围错误 | 数据库约束加 Service 校验，更新部门前检测祖先关系，并限制合理深度。 |
| 审计日志暴露敏感信息 | 合规和安全风险 | 字段白名单、敏感字段脱敏、只追加权限、审计写入测试。 |
| 首版搜索需求膨胀 | 进度和架构复杂度上升 | 先支持 PostgreSQL 索引、精确/前缀筛选；全文搜索单独评审。 |
| 迁移与 Model 漂移 | 发布失败或数据丢失 | CI 在空库和上一版本库执行 upgrade，禁止手工 DDL。 |
| 前后端 DTO 不一致 | 运行时错误 | OpenAPI 作为契约来源，前端类型集中管理，CI 检查响应 Schema。 |

## 10. 开发决策规则

- 新需求先判断是否属于首版边界、是否需要新表或权限；先更新设计/ADR，再实现。
- 不以减少文件或代码行数为目标；但没有实际业务价值的抽象不进入代码。
- 任何破坏性数据库变更必须提供迁移、回滚/恢复方案和数据影响说明。
- 未经明确评审不得更换固定技术栈、删除已有功能或引入基础设施组件。

