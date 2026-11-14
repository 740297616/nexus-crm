<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  createRole,
  deleteRole,
  listPermissions,
  listRoles,
  updateRole,
  updateRolePermissions,
} from '@/api/admin'
import { useAuthStore } from '@/stores/auth'
import type { DataScope, PermissionRecord, RoleRecord } from '@/types/api'

const authStore = useAuthStore()
const roles = ref<RoleRecord[]>([])
const permissions = ref<PermissionRecord[]>([])
const selectedRoleId = ref('')
const selectedPermissionCodes = ref<string[]>([])
const editingRole = ref<RoleRecord | null>(null)
const activePermissionType = ref<'menu' | 'page' | 'api'>('menu')
const createDialogVisible = ref(false)
const saving = ref(false)
const form = reactive({
  name: '',
  code: '',
  description: '',
  data_scope: 'self' as DataScope,
})

const selectedRole = computed(
  () => roles.value.find((role) => role.id === selectedRoleId.value) ?? null,
)
const groupedPermissions = computed(() => {
  const current = permissions.value.filter(
    (permission) => permission.permission_type === activePermissionType.value,
  )
  return current.reduce<Record<string, PermissionRecord[]>>((groups, permission) => {
    groups[permission.resource] ??= []
    groups[permission.resource].push(permission)
    return groups
  }, {})
})

async function loadRoles() {
  try {
    const [roleItems, permissionItems] = await Promise.all([listRoles(), listPermissions()])
    roles.value = roleItems
    permissions.value = permissionItems
    if (!selectedRoleId.value && roleItems.length) selectedRoleId.value = roleItems[0].id
  } catch {
    ElMessage.error('角色和权限目录加载失败')
  }
}

watch(selectedRole, (role) => {
  selectedPermissionCodes.value = role ? [...role.permission_codes] : []
})

function openCreate() {
  editingRole.value = null
  Object.assign(form, { name: '', code: '', description: '', data_scope: 'self' })
  createDialogVisible.value = true
}

function openEdit() {
  if (!selectedRole.value) return
  editingRole.value = selectedRole.value
  Object.assign(form, {
    name: selectedRole.value.name,
    code: selectedRole.value.code,
    description: selectedRole.value.description ?? '',
    data_scope: selectedRole.value.data_scope,
  })
  createDialogVisible.value = true
}

async function submitCreate() {
  try {
    if (editingRole.value) {
      const updated = await updateRole(editingRole.value.id, {
        name: form.name,
        description: form.description || null,
        data_scope: form.data_scope,
      })
      roles.value = roles.value.map((role) => (role.id === updated.id ? updated : role))
      ElMessage.success('角色信息已更新')
      createDialogVisible.value = false
      return
    }
    const role = await createRole({
      name: form.name,
      code: form.code,
      description: form.description || null,
      data_scope: form.data_scope,
    })
    ElMessage.success('角色已创建，请配置权限')
    createDialogVisible.value = false
    await loadRoles()
    selectedRoleId.value = role.id
  } catch {
    ElMessage.error('角色创建失败，请检查角色代码是否重复')
  }
}

async function savePermissions() {
  if (!selectedRole.value) return
  saving.value = true
  try {
    const updated = await updateRolePermissions(
      selectedRole.value.id,
      selectedPermissionCodes.value,
    )
    roles.value = roles.value.map((role) => (role.id === updated.id ? updated : role))
    ElMessage.success('角色权限已保存')
  } catch {
    ElMessage.error('角色权限保存失败')
  } finally {
    saving.value = false
  }
}

async function removeSelectedRole() {
  if (!selectedRole.value) return
  try {
    await ElMessageBox.confirm(
      `删除角色“${selectedRole.value.name}”？该角色必须尚未分配给任何用户。`,
      '确认删除',
      { type: 'warning' },
    )
    await deleteRole(selectedRole.value.id)
    selectedRoleId.value = ''
    ElMessage.success('角色已删除')
    await loadRoles()
  } catch (error: unknown) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('角色删除失败')
  }
}

const permissionTypeLabels = {
  menu: '菜单权限',
  page: '页面访问',
  api: 'API 操作',
}

onMounted(loadRoles)
</script>

<template>
  <section class="page-view">
    <div class="page-heading">
      <div>
        <p class="eyebrow">ACCESS CONTROL</p>
        <h1>角色与权限</h1>
        <p class="page-description">权限目录按菜单、页面和 API 操作分类；后端以 API 权限为准。</p>
      </div>
      <el-button v-if="authStore.hasPermission('roles:create')" type="primary" @click="openCreate">
        新建角色
      </el-button>
    </div>

    <div class="roles-workspace">
      <aside class="roles-list-pane">
        <div class="pane-heading">
          角色列表 <span>{{ roles.length }}</span>
        </div>
        <button
          v-for="role in roles"
          :key="role.id"
          type="button"
          class="role-list-item"
          :class="{ selected: role.id === selectedRoleId }"
          @click="selectedRoleId = role.id"
        >
          <span class="role-list-copy">
            <strong>{{ role.name }}</strong>
            <small>{{ role.code }}</small>
          </span>
          <el-tag v-if="role.is_system" size="small" effect="plain">系统</el-tag>
        </button>
      </aside>

      <section v-if="selectedRole" class="permissions-pane">
        <div class="role-detail-heading">
          <div>
            <h2>{{ selectedRole.name }}</h2>
            <p>{{ selectedRole.description || selectedRole.code }}</p>
          </div>
          <div class="role-heading-actions">
            <el-tag effect="plain">数据范围：{{ selectedRole.data_scope }}</el-tag>
            <el-button
              v-if="!selectedRole.is_system && authStore.hasPermission('roles:update')"
              @click="openEdit"
            >
              编辑角色
            </el-button>
            <el-button
              v-if="!selectedRole.is_system && authStore.hasPermission('roles:delete')"
              type="danger"
              plain
              @click="removeSelectedRole"
            >
              删除角色
            </el-button>
          </div>
        </div>

        <el-tabs v-model="activePermissionType">
          <el-tab-pane
            v-for="(label, type) in permissionTypeLabels"
            :key="type"
            :label="label"
            :name="type"
          />
        </el-tabs>

        <div class="permission-groups">
          <section
            v-for="(items, resource) in groupedPermissions"
            :key="resource"
            class="permission-group"
          >
            <div class="permission-group-heading">
              <strong>{{ resource }}</strong>
              <span>{{ items.length }} 项</span>
            </div>
            <el-checkbox-group
              v-model="selectedPermissionCodes"
              :disabled="
                selectedRole.is_system || !authStore.hasPermission('roles:assign_permissions')
              "
            >
              <el-checkbox
                v-for="permission in items"
                :key="permission.code"
                :value="permission.code"
              >
                <span class="permission-label">
                  <span>{{ permission.name }}</span>
                  <code>{{ permission.code }}</code>
                </span>
              </el-checkbox>
            </el-checkbox-group>
          </section>
          <el-empty v-if="!Object.keys(groupedPermissions).length" description="暂无此类权限" />
        </div>

        <div
          v-if="!selectedRole.is_system && authStore.hasPermission('roles:assign_permissions')"
          class="permissions-footer"
        >
          <span>{{ selectedPermissionCodes.length }} 项已选</span>
          <el-button type="primary" :loading="saving" @click="savePermissions">保存权限</el-button>
        </div>
        <el-alert
          v-else-if="selectedRole.is_system"
          type="info"
          :closable="false"
          title="系统角色为预置角色，权限不可在此修改。"
        />
      </section>
      <el-empty v-else description="请选择角色" />
    </div>

    <el-dialog
      v-model="createDialogVisible"
      :title="editingRole ? '编辑角色' : '新建角色'"
      width="480px"
    >
      <el-form label-position="top">
        <el-form-item label="角色名称" required
          ><el-input v-model="form.name" maxlength="100"
        /></el-form-item>
        <el-form-item v-if="!editingRole" label="角色代码" required
          ><el-input v-model="form.code" placeholder="e.g. finance_viewer"
        /></el-form-item>
        <el-form-item label="描述"
          ><el-input v-model="form.description" maxlength="500"
        /></el-form-item>
        <el-form-item label="数据范围" required>
          <el-select v-model="form.data_scope">
            <el-option label="本人" value="self" />
            <el-option label="本部门" value="department" />
            <el-option label="本部门及下属部门" value="subtree" />
            <el-option label="全部数据" value="all" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :disabled="!form.name.trim() || (!editingRole && !form.code.trim())"
          @click="submitCreate"
        >
          {{ editingRole ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>
