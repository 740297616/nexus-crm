<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { listFollowUps } from '@/api/followups'
import { listCustomers } from '@/api/customers'
import type { CustomerRecord, FollowUpRecord } from '@/types/api'

const router = useRouter()
const customers = ref<CustomerRecord[]>([])
const selectedCustomerId = ref('')
const followUps = ref<FollowUpRecord[]>([])
const loadingCustomers = ref(false)
const loadingFollowUps = ref(false)
const error = ref('')
const selectedCustomer = computed(() =>
  customers.value.find((item) => item.id === selectedCustomerId.value),
)

async function loadCustomers() {
  loadingCustomers.value = true
  try {
    const response = await listCustomers({
      page: 1,
      page_size: 100,
      sort_by: 'updated_at',
      sort_order: 'desc',
    })
    customers.value = response.data.items
    if (!selectedCustomerId.value && customers.value[0])
      selectedCustomerId.value = customers.value[0].id
  } catch {
    error.value = '客户列表加载失败，请重试。'
  } finally {
    loadingCustomers.value = false
  }
}

async function loadFollowUps() {
  if (!selectedCustomerId.value) {
    followUps.value = []
    return
  }
  loadingFollowUps.value = true
  error.value = ''
  try {
    const response = await listFollowUps(selectedCustomerId.value, { page: 1, page_size: 100 })
    followUps.value = response.data.items
  } catch {
    error.value = '跟进记录加载失败，请重试。'
  } finally {
    loadingFollowUps.value = false
  }
}

function formatDate(value: string) {
  return new Date(value).toLocaleString()
}

function methodLabel(method: FollowUpRecord['method']) {
  return { phone: '电话', visit: '上门拜访', wechat: '微信', email: '邮件', other: '其他' }[method]
}

function openCustomer() {
  if (selectedCustomerId.value)
    void router.push({ name: 'customer-detail', params: { customerId: selectedCustomerId.value } })
}

watch(selectedCustomerId, () => void loadFollowUps())
onMounted(loadCustomers)
</script>

<template>
  <section class="page-view">
    <div class="page-heading">
      <div>
        <p class="eyebrow">CRM / FOLLOW UPS</p>
        <h1>跟进记录</h1>
        <p class="page-description">按客户查看跟进历史，完整编辑请进入客户详情。</p>
      </div>
      <el-button :disabled="!selectedCustomerId" @click="openCustomer">打开客户详情</el-button>
    </div>
    <el-card shadow="never" class="filter-card">
      <el-select
        v-model="selectedCustomerId"
        filterable
        clearable
        placeholder="选择客户"
        :loading="loadingCustomers"
        class="customer-picker"
      >
        <el-option
          v-for="customer in customers"
          :key="customer.id"
          :label="`${customer.name}（${customer.customer_no}）`"
          :value="customer.id"
        />
      </el-select>
      <span v-if="selectedCustomer" class="related-muted"
        >负责人：{{ selectedCustomer.owner_name }}</span
      >
    </el-card>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false">
      <template #default
        ><el-button link type="primary" @click="loadFollowUps">重试</el-button></template
      >
    </el-alert>
    <el-skeleton v-if="loadingFollowUps" :rows="6" animated />
    <el-empty v-else-if="!followUps.length" description="暂无跟进记录" />
    <el-timeline v-else class="follow-up-timeline">
      <el-timeline-item
        v-for="record in followUps"
        :key="record.id"
        :timestamp="formatDate(record.followed_at)"
        placement="top"
      >
        <div class="timeline-heading">
          <div>
            <el-tag size="small" effect="plain">{{ methodLabel(record.method) }}</el-tag><strong>{{
              record.user_name
            }}</strong
            ><span v-if="record.contact_name" class="related-muted"
              >联系 {{ record.contact_name }}</span
            >
          </div>
        </div>
        <p class="timeline-content">{{ record.content }}</p>
        <p v-if="record.result" class="timeline-result">结果：{{ record.result }}</p>
      </el-timeline-item>
    </el-timeline>
  </section>
</template>
