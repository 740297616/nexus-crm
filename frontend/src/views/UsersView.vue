<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  createUser,
  listDepartments,
  listRoles,
  listUsers,
  updateUser,
  updateUserRoles,
  updateUserStatus,
} from '@/api/admin'
import { useAuthStore } from '@/stores/auth'
import type { DepartmentRecord, RoleRecord, UserRecord } from '@/types/api'

const authStore = useAuthStore()
const users = ref<UserRecord[]>([])
const roles = ref<RoleRecord[]>([])
const departments = ref<DepartmentRecord[]>([])
const search = ref('')
const departmentFilter = ref('')
const page = ref(1)
const pageSize = 20
const total = ref(0)
const loading = ref(false)
const createDialogVisible = ref(false)
const rolesDialogVisible = ref(false)
const editingUser = ref<UserRecord | null>(null)
const selectedRoleIds = ref<string[]>([])
const form = reactive({
  username: '',
  email: '',
  display_name: '',
  password: '',
  department_id: '',
  role_ids: [] as string[],
})

const departmentOptions = computed(() => flattenDepartments(departments.value))

function flattenDepartments(
  items: DepartmentRecord[],
  depth = 0,
): Array<{ id: string; label: string }> {
  return items.flatMap((item) => [
    { id: item.id, label: `${'　'.repeat(depth)}${item.name}` },
    ...flattenDepartments(item.children, depth + 1),
  ])
}

function roleName(code: string) {
  return roles.value.find((role) => role.code === code)?.name ?? code
}

async function loadUsers() {
  loading.value = true
  try {
    const result = await listUsers({
      search: search.value || undefined,
      department_id: departmentFilter.value || undefined,
      page: page.value,
      page_size: pageSize,
    })
    users.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

async function loadPageData() {
  try {
    const [roleItems, departmentItems] = await Promise.all([listRoles(), listDepartments()])
    roles.value = roleItems
    departments.value = departmentItems
    await loadUsers()
  } catch {
    ElMessage.error('用户数据加载失败')
  }
}

function openCreateDialog() {
  editingUser.value = null
  Object.assign(form, {
    username: '',
    email: '',
    display_name: '',
    password: '',
    department_id: '',
    role_ids: [],
  })
  createDialogVisible.value = true
}

function openEditDialog(user: UserRecord) {
  editingUser.value = user
  Object.assign(form, {
    username: user.username,
    email: user.email ?? '',
    display_name: user.display_name,
    password: '',
    department_id: user.department_id ?? '',
    role_ids: [],
  })
  createDialogVisible.value = true
}

async function submitCreate() {
  try {
    if (editingUser.value) {
      await updateUser(editingUser.value.id, {
        email: form.email || null,
        display_name: form.display_name,
        department_id: form.department_id || null,
      })
      ElMessage.success('用户信息已更新')
      createDialogVisible.value = false
      await loadUsers()
      return
    }
    await createUser({
      username: form.username,
      email: form.email || null,
      display_name: form.display_name,
      password: form.password,
      department_id: form.department_id || null,
      role_ids: form.role_ids,
    })
    ElMessage.success('用户已创建')
    createDialogVisible.value = false
    await loadUsers()
  } catch {
    ElMessage.error('用户创建失败，请检查用户名、部门和角色')
  }
}

async function toggleStatus(user: UserRecord) {
  const nextStatus = user.status === 'active' ? 'disabled' : 'active'
  try {
    await ElMessageBox.confirm(
      `${nextStatus === 'disabled' ? '禁用' : '启用'}用户“${user.display_name}”？`,
      '确认操作',
      { type: 'warning' },
    )
    await updateUserStatus(user.id, nextStatus)
    ElMessage.success(nextStatus === 'disabled' ? '用户已禁用' : '用户已启用')
    await loadUsers()
  } catch (error: unknown) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('用户状态更新失败')
  }
}

function openRolesDialog(user: UserRecord) {
  editingUser.value = user
  selectedRoleIds.value = roles.value
    .filter((role) => user.role_codes.includes(role.code))
    .map((role) => role.id)
  rolesDialogVisible.value = true
}

async function submitRoles() {
  if (!editingUser.value) return
  try {
    await updateUserRoles(editingUser.value.id, selectedRoleIds.value)
    ElMessage.success('角色分配已更新')
    rolesDialogVisible.value = false
    await loadUsers()
  } catch {
    ElMessage.error('角色分配更新失败')
  }
}

function handlePageChange(nextPage: number) {
  page.value = nextPage
  void loadUsers()
}

onMounted(loadPageData)
</script>

<template>
  <section class="page-view">
    <div class="page-heading">
      <div>
        <p class="eyebrow">ORGANIZATION</p>
        <h1>用户管理</h1>
        <p class="page-description">维护员工账号、所属部门与角色。</p>
      </div>
      <el-button
        v-if="
          authStore.hasPermission('users:create') && authStore.hasPermission('users:assign_roles')
        "
        type="primary"
        @click="openCreateDialog"
      >
        新建用户
      </el-button>
    </div>

    <div class="toolbar-row">
      <el-input
        v-model="search"
        clearable
        placeholder="搜索姓名、用户名或邮箱"
        class="toolbar-search"
        @keyup.enter="loadUsers"
        @clear="loadUsers"
      />
      <el-select
        v-model="departmentFilter"
        clearable
        placeholder="全部可见部门"
        class="toolbar-select"
        @change="loadUsers"
      >
        <el-option
          v-for="department in departmentOptions"
          :key="department.id"
          :label="department.label"
          :value="department.id"
        />
      </el-select>
      <el-button @click="loadUsers">查询</el-button>
    </div>

    <el-table v-loading="loading" :data="users" row-key="id" class="data-table">
      <el-table-column label="姓名" min-width="140">
        <template #default="scope">
          <div class="identity-cell">
            <strong>{{ scope.row.display_name }}</strong>
            <span>{{ scope.row.username }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="邮箱" min-width="190" prop="email" />
      <el-table-column label="部门" min-width="140" prop="department_name" />
      <el-table-column label="角色" min-width="190">
        <template #default="scope">
          <el-tag v-for="code in scope.row.role_codes" :key="code" class="role-tag" effect="plain">
            {{ roleName(code) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="scope">
          <el-tag :type="scope.row.status === 'active' ? 'success' : 'info'" effect="light">
            {{ scope.row.status === 'active' ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        v-if="
          authStore.hasPermission('users:update') ||
          authStore.hasPermission('users:disable') ||
          authStore.hasPermission('users:assign_roles')
        "
        label="操作"
        width="230"
        fixed="right"
      >
        <template #default="scope">
          <el-button
            v-if="authStore.hasPermission('users:update')"
            link
            type="primary"
            @click="openEditDialog(scope.row)"
          >
            编辑
          </el-button>
          <el-button
            v-if="authStore.hasPermission('users:assign_roles')"
            link
            type="primary"
            @click="openRolesDialog(scope.row)"
          >
            分配角色
          </el-button>
          <el-button
            v-if="authStore.hasPermission('users:disable')"
            link
            :type="scope.row.status === 'active' ? 'danger' : 'success'"
            @click="toggleStatus(scope.row)"
          >
            {{ scope.row.status === 'active' ? '禁用' : '启用' }}
          </el-button>
        </template>
      </el-table-column>
      <el-table-column v-if="!users.length && !loading" label="" />
    </el-table>

    <div class="pagination-row">
      <span>共 {{ total }} 个用户</span>
      <el-pagination
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>

    <el-dialog
      v-model="createDialogVisible"
      :title="editingUser ? '编辑用户' : '新建用户'"
      width="560px"
    >
      <el-form :model="form" label-position="top">
        <div class="form-grid">
          <el-form-item label="用户名" required>
            <el-input v-model="form.username" autocomplete="off" :disabled="Boolean(editingUser)" />
          </el-form-item>
          <el-form-item label="姓名" required>
            <el-input v-model="form.display_name" />
          </el-form-item>
          <el-form-item label="邮箱">
            <el-input v-model="form.email" type="email" />
          </el-form-item>
          <el-form-item v-if="!editingUser" label="初始密码" required>
            <el-input
              v-model="form.password"
              show-password
              type="password"
              autocomplete="new-password"
            />
          </el-form-item>
          <el-form-item label="部门">
            <el-select v-model="form.department_id" clearable placeholder="未分配">
              <el-option
                v-for="department in departmentOptions"
                :key="department.id"
                :label="department.label"
                :value="department.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item v-if="!editingUser" label="角色" required>
            <el-select v-model="form.role_ids" multiple placeholder="选择角色">
              <el-option
                v-for="role in roles"
                :key="role.id"
                :label="role.name"
                :value="role.id"
                :disabled="
                  role.code === 'system_admin' && !authStore.hasPermission('roles:assign_system')
                "
              />
            </el-select>
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :disabled="
            !form.username ||
            !form.display_name ||
            (!editingUser && (form.password.length < 8 || !form.role_ids.length))
          "
          @click="submitCreate"
        >
          {{ editingUser ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="rolesDialogVisible" title="分配角色" width="480px">
      <p v-if="editingUser" class="dialog-description">
        {{ editingUser.display_name }} · {{ editingUser.username }}
      </p>
      <el-checkbox-group v-model="selectedRoleIds" class="role-options">
        <el-checkbox
          v-for="role in roles"
          :key="role.id"
          :value="role.id"
          :disabled="
            role.code === 'system_admin' && !authStore.hasPermission('roles:assign_system')
          "
        >
          {{ role.name }}
        </el-checkbox>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="rolesDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!selectedRoleIds.length" @click="submitRoles">
          保存
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>
