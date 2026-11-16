<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { deleteCustomer, getCustomer } from '@/api/customers'
import { useAuthStore } from '@/stores/auth'
import type { CustomerDetail } from '@/types/api'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const customer = ref<CustomerDetail | null>(null)
const loading = ref(false)
const deleting = ref(false)
const loadError = ref('')
const customerId = computed(() => String(route.params.customerId ?? ''))
const canUpdate = computed(() => authStore.hasPermission('customers:update'))
const canDelete = computed(() => authStore.hasPermission('customers:delete'))
const canAssign = computed(() => authStore.hasPermission('customers:assign'))
const canTransfer = computed(() => authStore.hasPermission('customers:transfer'))

async function loadCustomer() {
  loading.value = true
  loadError.value = ''
  try {
    customer.value = await getCustomer(customerId.value)
  } catch {
    customer.value = null
    loadError.value = '客户不存在、已删除或当前账号无权查看。'
  } finally {
    loading.value = false
  }
}

function formatDate(value: string) {
  return new Date(value).toLocaleString()
}

function levelLabel(level: CustomerDetail['level']) {
  return { A: 'A 重点', B: 'B 优先', C: 'C 常规', D: 'D 观察' }[level]
}

async function removeCustomer() {
  if (!customer.value) return
  try {
    await ElMessageBox.confirm(
      `软删除客户“${customer.value.name}”（${customer.value.customer_no}）？`,
      '确认删除',
      { type: 'warning' },
    )
    deleting.value = true
    await deleteCustomer(customer.value.id)
    ElMessage.success('客户已删除')
    await router.push({ name: 'customers' })
  } catch (error: unknown) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('客户删除失败，请重试。')
  } finally {
    deleting.value = false
  }
}

onMounted(loadCustomer)
</script>

<template>
  <section class="page-view customer-detail-page">
    <div class="page-heading">
      <div>
        <p class="eyebrow">CRM / ACCOUNTS</p>
        <h1>客户详情</h1>
      </div>
      <div class="customer-detail-actions">
        <el-button @click="router.push({ name: 'customers' })">返回列表</el-button>
        <el-button
          v-if="customer && canAssign"
          @click="
            router.push({
              name: 'customers',
              query: { action: 'assign', customer_id: customer.id },
            })
          "
        >
          分配负责人
        </el-button>
        <el-button
          v-if="customer && canTransfer"
          type="warning"
          plain
          @click="
            router.push({
              name: 'customers',
              query: { action: 'transfer', customer_id: customer.id },
            })
          "
        >
          转移负责人
        </el-button>
        <el-button
          v-if="customer && canUpdate"
          type="primary"
          @click="router.push({ name: 'customer-edit', params: { customerId: customer.id } })"
        >
          编辑
        </el-button>
        <el-button
          v-if="customer && canDelete"
          type="danger"
          plain
          :loading="deleting"
          @click="removeCustomer"
        >
          删除
        </el-button>
      </div>
    </div>

    <el-skeleton v-if="loading" :rows="8" animated />
    <el-result v-else-if="loadError" icon="error" title="无法加载客户" :sub-title="loadError">
      <template #extra>
        <el-button type="primary" @click="loadCustomer">重试</el-button>
        <el-button @click="router.push({ name: 'customers' })">返回客户列表</el-button>
      </template>
    </el-result>
    <template v-else-if="customer">
      <section class="customer-detail-section">
        <div class="customer-detail-heading">
          <div>
            <h2>{{ customer.name }}</h2>
            <p>{{ customer.customer_no }}</p>
          </div>
          <div class="customer-detail-tags">
            <el-tag :type="customer.status === 'active' ? 'success' : 'info'" effect="light">
              {{ customer.status === 'active' ? '正常' : '停用' }}
            </el-tag>
            <el-tag type="warning" effect="plain">{{ levelLabel(customer.level) }}</el-tag>
          </div>
        </div>
        <el-descriptions :column="2" class="customer-descriptions">
          <el-descriptions-item label="负责人">{{ customer.owner_name }}</el-descriptions-item>
          <el-descriptions-item label="所属部门">{{
            customer.department_name
          }}</el-descriptions-item>
          <el-descriptions-item label="创建人">{{ customer.created_by_name }}</el-descriptions-item>
          <el-descriptions-item label="客户来源">{{ customer.source || '—' }}</el-descriptions-item>
          <el-descriptions-item label="所属行业">{{
            customer.industry || '—'
          }}</el-descriptions-item>
          <el-descriptions-item label="联系电话">{{ customer.phone || '—' }}</el-descriptions-item>
          <el-descriptions-item label="联系邮箱">{{ customer.email || '—' }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{
            formatDate(customer.updated_at)
          }}</el-descriptions-item>
          <el-descriptions-item label="地址" :span="2">{{
            customer.address || '—'
          }}</el-descriptions-item>
          <el-descriptions-item label="客户描述" :span="2">
            <span class="customer-description">{{ customer.description || '—' }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </section>

      <section class="customer-detail-section">
        <div class="section-heading-row">
          <div>
            <h2>负责人变更记录</h2>
            <p>客户分配与转移历史</p>
          </div>
          <span>{{ customer.ownership_history.length }} 条记录</span>
        </div>
        <el-table
          v-if="customer.ownership_history.length"
          :data="customer.ownership_history"
          row-key="id"
          class="data-table"
        >
          <el-table-column label="操作" width="110">
            <template #default="scope">
              {{ scope.row.action === 'assigned' ? '分配' : '转移' }}
            </template>
          </el-table-column>
          <el-table-column label="原负责人" min-width="140">
            <template #default="scope">{{ scope.row.previous_owner_name || '—' }}</template>
          </el-table-column>
          <el-table-column label="新负责人" min-width="140" prop="new_owner_name" />
          <el-table-column label="新所属部门" min-width="140" prop="new_department_name" />
          <el-table-column label="操作人" min-width="140" prop="transferred_by_name" />
          <el-table-column label="原因" min-width="180">
            <template #default="scope">{{ scope.row.reason || '—' }}</template>
          </el-table-column>
          <el-table-column label="操作时间" min-width="180">
            <template #default="scope">{{ formatDate(scope.row.created_at) }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无负责人变更记录" />
      </section>
    </template>
  </section>
</template>
