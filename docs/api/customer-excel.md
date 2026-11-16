# 客户 Excel 导入导出

所有接口都需要 `Authorization: Bearer <access_token>`，并使用 `/api/v1` 前缀。

## 模板下载

```http
GET /api/v1/customers/import/template
```

需要 `customers:import` 权限。响应为 `customer-import-template.xlsx`，包含 `customers` 和 `字段说明` 两个工作表。

## 导入

```http
POST /api/v1/customers/import
Content-Type: multipart/form-data

file=<customers.xlsx>
```

需要 `customers:import` 权限。当前默认限制为 10 MB、20,000 行，服务端按 500 行一批写入。支持的列如下：

| 列名 | 必填 | 说明 |
| --- | --- | --- |
| 客户编号 | 是 | 全局唯一，格式与客户创建接口一致 |
| 客户名称 | 是 | 与已有客户重名只返回 warning，不自动合并 |
| 负责人账号 | 否 | 负责人用户名或邮箱；不接受 `owner_id`，由服务端按当前用户权限解析 |
| 来源、行业、等级、状态 | 否 | 等级为 A/B/C/D，状态为 active/inactive |
| 联系电话、联系邮箱、地址、客户描述 | 否 | 按客户 Schema 校验 |

服务端拒绝 `.xlsx` 之外的扩展名、无效 ZIP 内容、公式或以 `=`, `+`, `-`, `@` 开头的单元格内容，以及负责人 ID、部门 ID、角色和权限字段。成功响应包含总行数、成功数、跳过数、错误数和提醒数，并带有行号、字段、错误码和安全截断后的值。

错误行不会写入客户；名称重复仍可导入并在 `warnings` 中返回。导入结果写入审计日志，负责人变更历史与客户写入保持同一事务。

## 导出

```http
GET /api/v1/customers/export?search=Acme&tag_id=<tag-id>
```

需要 `customers:export` 权限。支持客户列表的搜索、标签、来源、行业、等级、状态、负责人、部门、创建时间和排序参数。导出查询复用客户列表的数据范围条件，越权的负责人或部门筛选不会扩大范围。默认最多导出 50,000 条，超出时返回 `413 FILE_TOO_LARGE`。导出事件写入审计日志，响应为 `customers.xlsx`。
