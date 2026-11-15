# 数据范围服务

Phase 1.3 建立统一的数据范围基础设施，暂不创建客户、联系人或跟进表和业务接口。客户模块启用后，必须在 Repository/Service 的每一种资源查询中复用 `app.common.data_scope.data_scope_service`。

## 范围与角色继承

数据库继续保存项目基线中的四个值：

| 设计名称 | 持久化值 | 规则 |
| --- | --- | --- |
| `ALL` | `all` | 允许访问全部未删除资源 |
| `DEPARTMENT` | `department` | 资源部门等于当前用户部门 |
| `DEPARTMENT_AND_CHILDREN` | `subtree` | 资源部门属于当前部门树 |
| `SELF` | `self` | 资源负责人或创建者等于当前用户 |

用户拥有多个角色时取最宽范围：`ALL` > `DEPARTMENT_AND_CHILDREN` > `DEPARTMENT` > `SELF`。部门树每次解析都从数据库重新计算，因此用户或部门移动后下一次请求立即使用新范围。没有部门的用户在部门范围下没有部门资源可见性，`SELF` 仍可访问其本人资源。

当前预置角色的范围和组织权限如下：

| 角色 | 数据范围 | 组织/账号 API |
| --- | --- | --- |
| `system_admin` | `ALL` | 全部组织、用户和角色管理 |
| `department_manager` | `DEPARTMENT_AND_CHILDREN` | 读取本部门及下属部门组织和用户 |
| `employee` | `SELF` | 工作台；无组织管理 API |

## Repository 使用约定

先在 Service 中解析当前用户的上下文，再把同一个上下文传入列表、详情、更新、删除、统计和导出查询：

```python
context = data_scope_service.resolve(db, actor)
statement = select(Customer).where(Customer.deleted_at.is_(None))
statement = data_scope_service.apply(
    statement,
    context,
    Customer,
    owner_field="owner_id",
    department_field="department_id",
)
```

详情和写操作必须让查询先带范围条件，再按 ID 查询；查询不到时统一返回 `RESOURCE_NOT_FOUND`，不能通过 ID 遍历泄露资源存在性。统计和导出必须复用同一 `apply` 条件，不能单独使用未经授权的全表 `count` 或导出查询。需要同时允许本人创建记录时，使用 `creator_field`，该字段会与负责人字段按 `OR` 组合。

`DataScopeService.assert_access` 用于已经加载的资源，越权同样返回资源不存在；创建或变更负责人/部门前使用 `assert_department_access` 校验目标部门。显式共享客户属于客户模块的额外读取条件，不能替代修改、删除等写权限和范围校验。

## 本阶段边界

本阶段没有新增客户业务模型、迁移或 API。现有用户列表、详情和部门树已改为使用统一范围上下文，作为后续 CRM Repository 的参考实现；客户列表、详情、编辑、删除、分配、统计和导出将在客户模块阶段实现并使用同一服务。
