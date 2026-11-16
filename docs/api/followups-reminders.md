# 跟进与提醒 API

所有路径都相对于 `/api/v1`，需要 `Authorization: Bearer <access_token>`。成功和错误响应遵循 `PROJECT_SPEC.md` 的统一封装。

## 跟进记录

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/customers/{customer_id}/follow-ups` | `follow_ups:read` | 按客户查询时间线，支持 `search`、`method`、`from_at`、`to_at`、`page`、`page_size`、`sort_order` |
| POST | `/customers/{customer_id}/follow-ups` | `follow_ups:create` | 记录当前认证用户为真实跟进人；可选关联当前客户的有效联系人 |
| GET | `/customers/{customer_id}/follow-ups/{record_id}` | `follow_ups:read` | 查询单条记录；客户或记录不可见时返回 404 |
| PATCH | `/customers/{customer_id}/follow-ups/{record_id}` | `follow_ups:update` | 修改跟进内容；`self` 数据范围用户只能修改自己创建的记录 |

`method` 取值为 `phone`、`visit`、`wechat`、`email`、`other`。跟进记录不提供物理删除接口；写入和修改与审计日志在同一事务中完成。`next_follow_up_at` 不能早于 `followed_at`。

## 提醒

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/reminders` | `reminders:read` | 按当前用户数据范围查询提醒 |
| GET | `/reminders/mine` | `reminders:read` | 查询当前用户个人待办 |
| GET | `/reminders/due` | `reminders:read` | 查询 `pending` 且 `remind_at <= now()` 的提醒 |
| GET | `/reminders/overdue` | `reminders:read` | 查询 `pending` 且 `remind_at < now()` 的提醒 |
| POST | `/reminders` | `reminders:create` | 创建归属当前用户的提醒，可选关联可见客户或跟进记录 |
| GET | `/reminders/{reminder_id}` | `reminders:read` | 查询单条提醒；不可见时返回 404 |
| PATCH | `/reminders/{reminder_id}` | `reminders:update` | 仅 `pending` 提醒可编辑 |
| POST | `/reminders/{reminder_id}/complete` | `reminders:complete` | 将 `pending` 变为 `completed` 并写入完成时间 |
| POST | `/reminders/{reminder_id}/cancel` | `reminders:cancel` | 将 `pending` 变为 `cancelled` 并写入取消时间 |

提醒状态只允许 `pending`、`completed`、`cancelled`。首版主动提示由提醒页面每 60 秒轮询受权限保护的到期接口，并显示站内通知；页面关闭后不运行后台进程。未定义邮件、短信或外部推送渠道，因此不引入 Redis、Celery 或其他通知基础设施。
