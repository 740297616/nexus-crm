from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionDefinition:
    code: str
    name: str
    resource: str
    action: str
    permission_type: str
    description: str


PERMISSION_CATALOG = (
    PermissionDefinition(
        "dashboard:menu", "工作台菜单", "dashboard", "menu", "menu", "显示工作台菜单"
    ),
    PermissionDefinition(
        "dashboard:page", "工作台页面", "dashboard", "page", "page", "访问工作台页面"
    ),
    PermissionDefinition("users:menu", "用户管理菜单", "users", "menu", "menu", "显示用户管理菜单"),
    PermissionDefinition("users:page", "用户管理页面", "users", "page", "page", "访问用户管理页面"),
    PermissionDefinition("users:read", "查看用户", "users", "read", "api", "查询用户列表和详情"),
    PermissionDefinition("users:create", "创建用户", "users", "create", "api", "创建员工账号"),
    PermissionDefinition("users:update", "编辑用户", "users", "update", "api", "修改员工信息"),
    PermissionDefinition(
        "users:disable", "启用或禁用用户", "users", "disable", "api", "修改用户启用状态"
    ),
    PermissionDefinition(
        "users:assign_roles", "分配用户角色", "users", "assign_roles", "api", "分配用户角色"
    ),
    PermissionDefinition(
        "departments:menu", "部门管理菜单", "departments", "menu", "menu", "显示部门管理菜单"
    ),
    PermissionDefinition(
        "departments:page", "部门管理页面", "departments", "page", "page", "访问部门管理页面"
    ),
    PermissionDefinition(
        "departments:read", "查看部门", "departments", "read", "api", "查询部门组织树"
    ),
    PermissionDefinition(
        "departments:create", "创建部门", "departments", "create", "api", "创建组织部门"
    ),
    PermissionDefinition(
        "departments:update", "编辑部门", "departments", "update", "api", "修改部门信息"
    ),
    PermissionDefinition(
        "departments:delete", "删除部门", "departments", "delete", "api", "删除空部门"
    ),
    PermissionDefinition("roles:menu", "角色管理菜单", "roles", "menu", "menu", "显示角色管理菜单"),
    PermissionDefinition("roles:page", "角色管理页面", "roles", "page", "page", "访问角色管理页面"),
    PermissionDefinition("roles:read", "查看角色", "roles", "read", "api", "查询角色和权限目录"),
    PermissionDefinition("roles:create", "创建角色", "roles", "create", "api", "创建自定义角色"),
    PermissionDefinition("roles:update", "编辑角色", "roles", "update", "api", "修改自定义角色"),
    PermissionDefinition(
        "roles:delete", "删除角色", "roles", "delete", "api", "删除未分配的自定义角色"
    ),
    PermissionDefinition(
        "roles:assign_permissions",
        "配置角色权限",
        "roles",
        "assign_permissions",
        "api",
        "配置自定义角色权限",
    ),
    PermissionDefinition(
        "roles:assign_system",
        "分配系统管理员",
        "roles",
        "assign_system",
        "api",
        "授予系统管理员角色",
    ),
    PermissionDefinition(
        "permissions:read", "查看权限目录", "permissions", "read", "api", "查询权限目录"
    ),
    PermissionDefinition(
        "customers:menu", "客户管理菜单", "customers", "menu", "menu", "显示客户管理菜单"
    ),
    PermissionDefinition(
        "customers:page", "客户管理页面", "customers", "page", "page", "访问客户管理页面"
    ),
    PermissionDefinition(
        "customers:read", "查看客户", "customers", "read", "api", "查询客户和同名提醒"
    ),
    PermissionDefinition(
        "customers:create", "创建客户", "customers", "create", "api", "创建客户档案"
    ),
    PermissionDefinition(
        "customers:update", "编辑客户", "customers", "update", "api", "编辑客户档案"
    ),
    PermissionDefinition(
        "customers:delete", "删除客户", "customers", "delete", "api", "软删除客户"
    ),
    PermissionDefinition(
        "customers:assign", "分配客户", "customers", "assign", "api", "分配客户负责人"
    ),
    PermissionDefinition(
        "customers:transfer", "转移客户", "customers", "transfer", "api", "转移客户负责人并记录原因"
    ),
    PermissionDefinition(
        "contacts:read", "查看联系人", "contacts", "read", "api", "查询客户联系人"
    ),
    PermissionDefinition(
        "contacts:create", "创建联系人", "contacts", "create", "api", "创建客户联系人"
    ),
    PermissionDefinition(
        "contacts:update", "编辑联系人", "contacts", "update", "api", "编辑客户联系人"
    ),
    PermissionDefinition(
        "contacts:delete", "删除联系人", "contacts", "delete", "api", "软删除客户联系人"
    ),
    PermissionDefinition(
        "contacts:set_primary",
        "设置主要联系人",
        "contacts",
        "set_primary",
        "api",
        "设置客户主要联系人",
    ),
    PermissionDefinition("tags:read", "查看标签", "tags", "read", "api", "查询客户标签"),
    PermissionDefinition("tags:create", "创建标签", "tags", "create", "api", "创建客户标签"),
    PermissionDefinition("tags:update", "编辑标签", "tags", "update", "api", "编辑客户标签"),
    PermissionDefinition("tags:delete", "删除标签", "tags", "delete", "api", "软删除客户标签"),
    PermissionDefinition("tags:bind", "绑定标签", "tags", "bind", "api", "为客户绑定标签"),
    PermissionDefinition("tags:unbind", "解绑标签", "tags", "unbind", "api", "移除客户标签"),
)

ROLE_CATALOG = {
    "system_admin": {
        "name": "系统管理员",
        "description": "管理所有组织、账号和权限配置。",
        "data_scope": "all",
        "permission_codes": tuple(item.code for item in PERMISSION_CATALOG),
    },
    "department_manager": {
        "name": "部门主管",
        "description": "查看本部门及下属部门的用户、组织和角色配置。",
        "data_scope": "subtree",
        "permission_codes": (
            "dashboard:menu",
            "dashboard:page",
            "users:menu",
            "users:page",
            "users:read",
            "departments:menu",
            "departments:page",
            "departments:read",
            "roles:menu",
            "roles:page",
            "roles:read",
            "permissions:read",
        ),
    },
    "employee": {
        "name": "普通员工",
        "description": "访问工作台，不具备组织和账号管理权限。",
        "data_scope": "self",
        "permission_codes": ("dashboard:menu", "dashboard:page"),
    },
    "sales_manager": {
        "name": "销售主管",
        "description": "管理本人部门及下属部门范围内的客户和负责人分配。",
        "data_scope": "subtree",
        "permission_codes": (
            "dashboard:menu",
            "dashboard:page",
            "customers:menu",
            "customers:page",
            "customers:read",
            "customers:create",
            "customers:update",
            "customers:delete",
            "customers:assign",
            "customers:transfer",
            "contacts:read",
            "contacts:create",
            "contacts:update",
            "contacts:delete",
            "contacts:set_primary",
            "tags:read",
            "tags:create",
            "tags:update",
            "tags:delete",
            "tags:bind",
            "tags:unbind",
        ),
    },
    "sales": {
        "name": "销售",
        "description": "管理本人负责的客户。",
        "data_scope": "self",
        "permission_codes": (
            "dashboard:menu",
            "dashboard:page",
            "customers:menu",
            "customers:page",
            "customers:read",
            "customers:create",
            "customers:update",
            "contacts:read",
            "contacts:create",
            "contacts:update",
            "contacts:delete",
            "contacts:set_primary",
            "tags:read",
            "tags:bind",
            "tags:unbind",
        ),
    },
}
