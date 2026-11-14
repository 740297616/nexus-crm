<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { createDepartment, deleteDepartment, listDepartments, updateDepartment } from '@/api/admin'
import { useAuthStore } from '@/stores/auth'
import type { DepartmentRecord } from '@/types/api'

const authStore = useAuthStore()
const departments = ref<DepartmentRecord[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editingDepartment = ref<DepartmentRecord | null>(null)
const form = reactive({ name: '', parent_id: '' })

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

async function loadDepartments() {
  loading.value = true
  try {
    departments.value = await listDepartments()
  } catch {
    ElMessage.error('部门数据加载失败')
  } finally {
    loading.value = false
  }
}

function openCreate(parent?: DepartmentRecord) {
  editingDepartment.value = null
  form.name = ''
  form.parent_id = parent?.id ?? ''
  dialogVisible.value = true
}

function openEdit(department: DepartmentRecord) {
  editingDepartment.value = department
  form.name = department.name
  form.parent_id = department.parent_id ?? ''
  dialogVisible.value = true
}

async function submitDepartment() {
  try {
    if (editingDepartment.value) {
      await updateDepartment(editingDepartment.value.id, {
        name: form.name,
        parent_id: form.parent_id || null,
      })
      ElMessage.success('部门已更新')
    } else {
      await createDepartment({ name: form.name, parent_id: form.parent_id || null })
      ElMessage.success('部门已创建')
    }
    dialogVisible.value = false
    await loadDepartments()
  } catch {
    ElMessage.error('部门保存失败，请检查名称与上级关系')
  }
}

async function removeDepartment(department: DepartmentRecord) {
  try {
    await ElMessageBox.confirm(`删除部门“${department.name}”？`, '确认操作', { type: 'warning' })
    await deleteDepartment(department.id)
    ElMessage.success('部门已删除')
    await loadDepartments()
  } catch (error: unknown) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('部门删除失败，部门必须为空')
  }
}

async function toggleDepartmentStatus(department: DepartmentRecord) {
  const nextStatus = !department.is_active
  try {
    await updateDepartment(department.id, { is_active: nextStatus })
    ElMessage.success(nextStatus ? '部门已启用' : '部门已停用')
    await loadDepartments()
  } catch {
    ElMessage.error('部门状态更新失败')
  }
}

onMounted(loadDepartments)
</script>

<template>
  <section class="page-view">
    <div class="page-heading">
      <div>
        <p class="eyebrow">ORGANIZATION</p>
        <h1>部门管理</h1>
        <p class="page-description">维护上下级部门结构和部门状态。</p>
      </div>
      <el-button
        v-if="authStore.hasPermission('departments:create')"
        type="primary"
        @click="openCreate()"
      >
        新建部门
      </el-button>
    </div>

    <el-table
      v-loading="loading"
      :data="departments"
      row-key="id"
      default-expand-all
      :tree-props="{ children: 'children' }"
      class="data-table"
    >
      <el-table-column label="部门名称" min-width="240" prop="name" />
      <el-table-column label="成员" width="120">
        <template #default="scope">{{ scope.row.user_count }} 人</template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="scope">
          <el-tag :type="scope.row.is_active ? 'success' : 'info'" effect="light">
            {{ scope.row.is_active ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="210" fixed="right">
        <template #default="scope">
          <el-button
            v-if="authStore.hasPermission('departments:create')"
            link
            type="primary"
            @click="openCreate(scope.row)"
          >
            添加下级
          </el-button>
          <el-button
            v-if="authStore.hasPermission('departments:update')"
            link
            type="primary"
            @click="openEdit(scope.row)"
          >
            编辑
          </el-button>
          <el-button
            v-if="authStore.hasPermission('departments:update')"
            link
            :type="scope.row.is_active ? 'warning' : 'success'"
            @click="toggleDepartmentStatus(scope.row)"
          >
            {{ scope.row.is_active ? '停用' : '启用' }}
          </el-button>
          <el-button
            v-if="authStore.hasPermission('departments:delete')"
            link
            type="danger"
            :disabled="scope.row.user_count > 0 || scope.row.children.length > 0"
            @click="removeDepartment(scope.row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="editingDepartment ? '编辑部门' : '新建部门'"
      width="460px"
    >
      <el-form label-position="top">
        <el-form-item label="部门名称" required>
          <el-input v-model="form.name" maxlength="120" />
        </el-form-item>
        <el-form-item label="上级部门">
          <el-select v-model="form.parent_id" clearable placeholder="设为顶级部门">
            <el-option
              v-for="department in departmentOptions.filter(
                (item) => item.id !== editingDepartment?.id,
              )"
              :key="department.id"
              :label="department.label"
              :value="department.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!form.name.trim()" @click="submitDepartment">
          保存
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>
