<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import {
  assignCustomer,
  deleteCustomer,
  getCustomer,
  listCustomerAssignees,
  listCustomers,
  transferCustomer,
  type CustomerFilters,
} from '@/api/customers'
import { listTags } from '@/api/tags'
import { useAuthStore } from '@/stores/auth'
import type { CustomerAssignee, CustomerRecord, TagRecord } from '@/types/api'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const customers = ref<CustomerRecord[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const loadError = ref('')
const searchInput = ref('')
const filters = reactive<CustomerFilters>({})
const ownerDialogVisible = ref(false)
const ownerSaving = ref(false)
const ownerLoading = ref(false)
const ownerAction = ref<'assign' | 'transfer'>('assign')
const selectedCustomer = ref<CustomerRecord | null>(null)
const assignees = ref<CustomerAssignee[]>([])
const ownerForm = reactive({ owner_id: '', reason: '' })
const tags = ref<TagRecord[]>([])
const canTagRead = authStore.hasPermission('tags:read')

const canCreate = authStore.hasPermission('customers:create')
const canUpdate = authStore.hasPermission('customers:update')
const canDelete = authStore.hasPermission('customers:delete')
const canAssign = authStore.hasPermission('customers:assign')
const canTransfer = authStore.hasPermission('customers:transfer')

async function loadCustomers() {
  loading.value = true
  loadError.value = ''
  try {
    const response = await listCustomers({
      ...filters,
      search: searchInput.value.trim() || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    customers.value = response.data.items
    total.value = response.data.total
  } catch {
    loadError.value = '客户列表加载失败，请重试。'
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  page.value = 1
  void loadCustomers()
}

function resetFilters() {
  searchInput.value = ''
  filters.source = undefined
  filters.industry = undefined
  filters.level = undefined
  filters.status = undefined
  filters.tag_id = undefined
  applyFilters()
}

async function loadTags() {
  if (!canTagRead) return
  try {
    tags.value = await listTags()
  } catch {
    tags.value = []
  }
}

function changePage(nextPage: number) {
  page.value = nextPage
  void loadCustomers()
}

function changePageSize(size: number) {
  pageSize.value = size
  page.value = 1
  void loadCustomers()
}

function openCustomer(customerId: string) {
  void router.push({ name: 'customer-detail', params: { customerId } })
}

function editCustomer(customerId: string) {
  void router.push({ name: 'customer-edit', params: { customerId } })
}

function levelType(level: CustomerRecord['level']) {
  return { A: 'danger', B: 'warning', C: 'primary', D: 'info' }[level]
}

function levelLabel(level: CustomerRecord['level']) {
  return { A: 'A 重点', B: 'B 优先', C: 'C 常规', D: 'D 观察' }[level]
}

async function openOwnerDialog(customer: CustomerRecord, action: 'assign' | 'transfer') {
  selectedCustomer.value = customer
  ownerAction.value = action
  ownerForm.owner_id = ''
  ownerForm.reason = ''
  ownerDialogVisible.value = true
  ownerLoading.value = true
  try {
    assignees.value = await listCustomerAssignees()
  } catch {
    assignees.value = []
    ElMessage.error('负责人列表加载失败')
  } finally {
    ownerLoading.value = false
  }
}

async function openOwnerActionFromQuery() {
  const customerId = route.query.customer_id
  const action = route.query.action
  if (typeof customerId !== 'string' || (action !== 'assign' && action !== 'transfer')) return
  try {
    const customer = await getCustomer(customerId)
    await openOwnerDialog(customer, action)
    await router.replace({ name: 'customers' })
  } catch {
    ElMessage.error('无法打开该客户的负责人变更窗口')
  }
}

async function submitOwnerChange() {
  if (!selectedCustomer.value || !ownerForm.owner_id) return
  if (ownerAction.value === 'transfer' && ownerForm.reason.trim().length < 3) {
    ElMessage.warning('请填写至少 3 个字符的转移原因')
    return
  }
  ownerSaving.value = true
  try {
    const payload = {
      owner_id: ownerForm.owner_id,
      reason: ownerForm.reason.trim() || null,
    }
    if (ownerAction.value === 'assign') {
      await assignCustomer(selectedCustomer.value.id, payload)
      ElMessage.success('客户负责人已分配，变更已记录')
    } else {
      await transferCustomer(selectedCustomer.value.id, {
        owner_id: payload.owner_id,
        reason: payload.reason ?? '',
      })
      ElMessage.success('客户已转移，变更已记录')
    }
    ownerDialogVisible.value = false
    await loadCustomers()
  } catch {
    ElMessage.error('负责人变更失败，请检查客户和目标负责人范围')
  } finally {
    ownerSaving.value = false
  }
}

async function removeCustomer(customer: CustomerRecord) {
  try {
    await ElMessageBox.confirm(
      `软删除客户“${customer.name}”（${customer.customer_no}）？`,
      '确认删除',
      { type: 'warning' },
    )
    await deleteCustomer(customer.id)
    ElMessage.success('客户已删除')
    if (customers.value.length === 1 && page.value > 1) page.value -= 1
    await loadCustomers()
  } catch (error: unknown) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('客户删除失败')
  }
}

onMounted(async () => {
  await Promise.all([loadCustomers(), loadTags()])
  await openOwnerActionFromQuery()
})
</script>

<template>
  <section class="page-view customers-page">
    <div class="page-heading">
      <div>
        <p class="eyebrow">CRM / ACCOUNTS</p>
        <h1>客户管理</h1>
      </div>
      <el-button v-if="canCreate" type="primary" @click="router.push({ name: 'customer-create' })">
        新建客户
      </el-button>
    </div>

    <div class="customer-filters">
      <el-input
        v-model="searchInput"
        clearable
        placeholder="搜索编号、名称、电话或邮箱"
        class="customer-search"
        @keyup.enter="applyFilters"
        @clear="applyFilters"
      />
      <el-input v-model="filters.source" clearable placeholder="来源" @keyup.enter="applyFilters" />
      <el-input
        v-model="filters.industry"
        clearable
        placeholder="行业"
        @keyup.enter="applyFilters"
      />
      <el-select v-model="filters.level" clearable placeholder="客户等级">
        <el-option label="A 重点" value="A" />
        <el-option label="B 优先" value="B" />
        <el-option label="C 常规" value="C" />
        <el-option label="D 观察" value="D" />
      </el-select>
      <el-select v-model="filters.status" clearable placeholder="客户状态">
        <el-option label="正常" value="active" />
        <el-option label="停用" value="inactive" />
      </el-select>
      <el-select
        v-if="canTagRead"
        v-model="filters.tag_id"
        clearable
        filterable
        placeholder="客户标签"
      >
        <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id" />
      </el-select>
      <el-button type="primary" @click="applyFilters">查询</el-button>
      <el-button @click="resetFilters"> 重置 </el-button>
    </div>

    <el-alert v-if="loadError" :title="loadError" type="error" show-icon :closable="false">
      <template #default>
        <el-button link type="primary" @click="loadCustomers">重试</el-button>
      </template>
    </el-alert>

    <el-table v-loading="loading" :data="customers" row-key="id" class="data-table customer-table">
      <el-table-column label="客户" min-width="240">
        <template #default="scope">
          <button class="customer-name-link" type="button" @click="openCustomer(scope.row.id)">
            <strong>{{ scope.row.name }}</strong>
            <span>{{ scope.row.customer_no }}</span>
          </button>
        </template>
      </el-table-column>
      <el-table-column label="负责人" min-width="130" prop="owner_name" />
      <el-table-column label="所属部门" min-width="130" prop="department_name" />
      <el-table-column label="来源" min-width="120" prop="source" />
      <el-table-column label="行业" min-width="130" prop="industry" />
      <el-table-column label="等级" width="110">
        <template #default="scope">
          <el-tag :type="levelType(scope.row.level)" effect="plain">
            {{ levelLabel(scope.row.level) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="scope">
          <el-tag :type="scope.row.status === 'active' ? 'success' : 'info'" effect="light">
            {{ scope.row.status === 'active' ? '正常' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" min-width="170">
        <template #default="scope">{{ new Date(scope.row.updated_at).toLocaleString() }}</template>
      </el-table-column>
      <el-table-column
        v-if="canUpdate || canDelete || canAssign || canTransfer"
        label="操作"
        min-width="210"
        fixed="right"
      >
        <template #default="scope">
          <el-button v-if="canUpdate" link type="primary" @click="editCustomer(scope.row.id)">
            编辑
          </el-button>
          <el-button
            v-if="canAssign"
            link
            type="primary"
            @click="openOwnerDialog(scope.row, 'assign')"
          >
            分配
          </el-button>
          <el-button
            v-if="canTransfer"
            link
            type="warning"
            @click="openOwnerDialog(scope.row, 'transfer')"
          >
            转移
          </el-button>
          <el-button v-if="canDelete" link type="danger" @click="removeCustomer(scope.row)">
            删除
          </el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty :description="loading ? '正在加载客户' : '没有符合条件的客户'" />
      </template>
    </el-table>

    <div class="pagination-row">
      <span>共 {{ total }} 位客户</span>
      <el-pagination
        :current-page="page"
        :page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        layout="sizes, prev, pager, next"
        @current-change="changePage"
        @size-change="changePageSize"
      />
    </div>

    <el-dialog
      v-model="ownerDialogVisible"
      :title="ownerAction === 'assign' ? '分配客户' : '转移客户负责人'"
      width="520px"
    >
      <p v-if="selectedCustomer" class="dialog-description">
        {{ selectedCustomer.name }} · {{ selectedCustomer.customer_no }} · 当前负责人
        {{ selectedCustomer.owner_name }}
      </p>
      <el-form label-position="top">
        <el-form-item label="新负责人" required>
          <el-select
            v-model="ownerForm.owner_id"
            v-loading="ownerLoading"
            filterable
            placeholder="选择可见范围内的启用用户"
            class="full-width"
          >
            <el-option
              v-for="assignee in assignees"
              :key="assignee.id"
              :label="`${assignee.display_name} · ${assignee.department_name}`"
              :value="assignee.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item
          :label="ownerAction === 'transfer' ? '转移原因' : '分配说明'"
          :required="ownerAction === 'transfer'"
        >
          <el-input
            v-model="ownerForm.reason"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            placeholder="负责人变更会保留操作历史"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ownerDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="ownerSaving"
          :disabled="
            !ownerForm.owner_id ||
            (ownerAction === 'transfer' && ownerForm.reason.trim().length < 3)
          "
          @click="submitOwnerChange"
        >
          保存
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>
