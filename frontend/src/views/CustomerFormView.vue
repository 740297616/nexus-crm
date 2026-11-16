<script setup lang="ts">
import axios from 'axios'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  checkCustomerName,
  createCustomer,
  getCustomer,
  listCustomerAssignees,
  updateCustomer,
  type CustomerPayload,
} from '@/api/customers'
import { useAuthStore } from '@/stores/auth'
import type { ApiErrorBody, CustomerAssignee, CustomerNameMatch } from '@/types/api'

interface CustomerForm {
  customer_no: string
  name: string
  owner_id: string
  source: string
  industry: string
  level: 'A' | 'B' | 'C' | 'D'
  status: 'active' | 'inactive'
  phone: string
  email: string
  address: string
  description: string
}

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const formRef = ref<FormInstance>()
const form = reactive<CustomerForm>(emptyForm())
const assignees = ref<CustomerAssignee[]>([])
const duplicateMatches = ref<CustomerNameMatch[]>([])
const loading = ref(false)
const saving = ref(false)
const assigneesLoading = ref(false)
const nameChecking = ref(false)
const pageError = ref('')
const assigneeError = ref('')
const nameCheckError = ref('')

const customerId = computed(() =>
  typeof route.params.customerId === 'string' ? route.params.customerId : null,
)
const isEditing = computed(() => customerId.value !== null)
const canRead = computed(() => authStore.hasPermission('customers:read'))
const canAssign = computed(() => authStore.hasPermission('customers:assign'))

const rules: FormRules<CustomerForm> = {
  customer_no: [
    { required: true, message: '请输入客户编号', trigger: 'blur' },
    {
      pattern: /^[A-Za-z0-9][A-Za-z0-9_-]{2,39}$/,
      message: '编号需为 3–40 位字母、数字、下划线或连字符',
      trigger: 'blur',
    },
  ],
  name: [
    { required: true, message: '请输入客户名称', trigger: 'blur' },
    { min: 1, max: 200, message: '名称长度不能超过 200 个字符', trigger: 'blur' },
  ],
  source: [{ max: 80, message: '来源不能超过 80 个字符', trigger: 'blur' }],
  industry: [{ max: 100, message: '行业不能超过 100 个字符', trigger: 'blur' }],
  email: [
    {
      validator: (_rule, value: string, callback) => {
        if (!value || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) callback()
        else callback(new Error('请输入有效的邮箱地址'))
      },
      trigger: 'blur',
    },
  ],
  phone: [{ max: 40, message: '电话不能超过 40 个字符', trigger: 'blur' }],
  address: [{ max: 500, message: '地址不能超过 500 个字符', trigger: 'blur' }],
  description: [{ max: 4000, message: '描述不能超过 4000 个字符', trigger: 'blur' }],
}

function emptyForm(): CustomerForm {
  return {
    customer_no: '',
    name: '',
    owner_id: '',
    source: '',
    industry: '',
    level: 'C',
    status: 'active',
    phone: '',
    email: '',
    address: '',
    description: '',
  }
}

function nullable(value: string) {
  return value.trim() || null
}

function apiMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    return error.response?.data?.error?.message ?? fallback
  }
  return fallback
}

function goBack() {
  if (customerId.value) {
    void router.push({ name: 'customer-detail', params: { customerId: customerId.value } })
  } else {
    void router.push({ name: 'customers' })
  }
}

function clearNameCheck() {
  duplicateMatches.value = []
  nameCheckError.value = ''
}

async function initialize() {
  loading.value = true
  pageError.value = ''
  assigneeError.value = ''
  nameCheckError.value = ''
  duplicateMatches.value = []
  assignees.value = []
  Object.assign(form, emptyForm())
  try {
    if (isEditing.value) {
      if (!authStore.hasPermission('customers:update')) {
        pageError.value = '当前账号没有编辑客户的权限。'
        return
      }
      const customer = await getCustomer(customerId.value!)
      Object.assign(form, {
        customer_no: customer.customer_no,
        name: customer.name,
        source: customer.source ?? '',
        industry: customer.industry ?? '',
        level: customer.level,
        status: customer.status,
        phone: customer.phone ?? '',
        email: customer.email ?? '',
        address: customer.address ?? '',
        description: customer.description ?? '',
      })
    } else {
      if (!authStore.hasPermission('customers:create')) {
        pageError.value = '当前账号没有创建客户的权限。'
        return
      }
      if (canAssign.value) {
        assigneesLoading.value = true
        try {
          assignees.value = await listCustomerAssignees()
        } catch (error: unknown) {
          assigneeError.value = apiMessage(error, '负责人列表加载失败，仍可由当前用户负责。')
        } finally {
          assigneesLoading.value = false
        }
      }
    }
  } catch (error: unknown) {
    pageError.value = apiMessage(error, '客户信息加载失败，请重试。')
  } finally {
    loading.value = false
  }
}

async function inspectName(): Promise<'clear' | 'duplicate' | 'unavailable'> {
  const name = form.name.trim()
  duplicateMatches.value = []
  nameCheckError.value = ''
  if (!name) return 'clear'
  if (!canRead.value) {
    nameCheckError.value = '当前账号无法查询同名客户。'
    return 'unavailable'
  }
  nameChecking.value = true
  try {
    const result = await checkCustomerName(name, customerId.value ?? undefined)
    duplicateMatches.value = result.matches
    return result.has_duplicates ? 'duplicate' : 'clear'
  } catch {
    nameCheckError.value = '暂时无法检查同名客户；保存前请确认没有重复客户。'
    return 'unavailable'
  } finally {
    nameChecking.value = false
  }
}

async function confirmNameStatus(status: 'duplicate' | 'unavailable') {
  const message =
    status === 'duplicate'
      ? `找到 ${duplicateMatches.value.length} 条同名客户。仍要继续保存吗？系统不会合并客户。`
      : '当前无法完成名称查重。确认已检查现有客户并仍要继续保存吗？'
  try {
    await ElMessageBox.confirm(message, '确认客户名称', {
      confirmButtonText: '继续保存',
      cancelButtonText: '返回修改',
      type: 'warning',
    })
    return true
  } catch {
    return false
  }
}

async function submit() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  const nameStatus = await inspectName()
  if (nameStatus !== 'clear' && !(await confirmNameStatus(nameStatus))) return

  const payload: CustomerPayload = {
    customer_no: form.customer_no.trim().toUpperCase(),
    name: form.name.trim(),
    source: nullable(form.source),
    industry: nullable(form.industry),
    level: form.level,
    status: form.status,
    phone: nullable(form.phone),
    email: nullable(form.email),
    address: nullable(form.address),
    description: nullable(form.description),
  }
  if (form.owner_id) payload.owner_id = form.owner_id

  saving.value = true
  try {
    if (customerId.value) {
      await updateCustomer(customerId.value, {
        name: payload.name,
        source: payload.source,
        industry: payload.industry,
        level: payload.level,
        status: payload.status,
        phone: payload.phone,
        email: payload.email,
        address: payload.address,
        description: payload.description,
      })
      ElMessage.success('客户信息已更新')
      await router.push({ name: 'customer-detail', params: { customerId: customerId.value } })
    } else {
      const customer = await createCustomer(payload)
      ElMessage.success('客户已创建')
      await router.push({ name: 'customer-detail', params: { customerId: customer.id } })
    }
  } catch (error: unknown) {
    ElMessage.error(apiMessage(error, '客户保存失败，请检查编号和字段内容。'))
  } finally {
    saving.value = false
  }
}

watch(
  () => route.params.customerId,
  () => void initialize(),
  { immediate: true },
)
</script>

<template>
  <section class="page-view customer-form-page">
    <div class="page-heading">
      <div>
        <p class="eyebrow">CRM / ACCOUNTS</p>
        <h1>{{ isEditing ? '编辑客户' : '新建客户' }}</h1>
      </div>
      <el-button @click="goBack">返回</el-button>
    </div>

    <el-skeleton v-if="loading" :rows="8" animated />
    <el-result v-else-if="pageError" icon="error" title="无法打开客户表单" :sub-title="pageError">
      <template #extra>
        <el-button type="primary" @click="initialize">重试</el-button>
        <el-button @click="router.push({ name: 'customers' })">返回客户列表</el-button>
      </template>
    </el-result>
    <el-form
      v-else
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
      class="customer-form"
      @submit.prevent="submit"
    >
      <div class="customer-form-grid">
        <el-form-item label="客户编号" prop="customer_no" required>
          <el-input v-model="form.customer_no" :disabled="isEditing" maxlength="40" />
        </el-form-item>
        <el-form-item label="客户名称" prop="name" required>
          <el-input
            v-model="form.name"
            maxlength="200"
            show-word-limit
            @input="clearNameCheck"
            @blur="inspectName"
          />
        </el-form-item>
        <el-form-item v-if="!isEditing && canAssign" label="初始负责人">
          <el-select
            v-model="form.owner_id"
            clearable
            filterable
            :loading="assigneesLoading"
            placeholder="默认由当前用户负责"
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
        <el-form-item label="客户来源" prop="source">
          <el-input v-model="form.source" maxlength="80" />
        </el-form-item>
        <el-form-item label="所属行业" prop="industry">
          <el-input v-model="form.industry" maxlength="100" />
        </el-form-item>
        <el-form-item label="客户等级" prop="level" required>
          <el-select v-model="form.level" class="full-width">
            <el-option label="A 重点" value="A" />
            <el-option label="B 优先" value="B" />
            <el-option label="C 常规" value="C" />
            <el-option label="D 观察" value="D" />
          </el-select>
        </el-form-item>
        <el-form-item label="客户状态" prop="status" required>
          <el-select v-model="form.status" class="full-width">
            <el-option label="正常" value="active" />
            <el-option label="停用" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item label="联系电话" prop="phone">
          <el-input v-model="form.phone" maxlength="40" />
        </el-form-item>
        <el-form-item label="联系邮箱" prop="email">
          <el-input v-model="form.email" maxlength="255" />
        </el-form-item>
        <el-form-item label="地址" prop="address" class="customer-form-wide">
          <el-input v-model="form.address" maxlength="500" />
        </el-form-item>
        <el-form-item label="客户描述" prop="description" class="customer-form-wide">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="4"
            maxlength="4000"
            show-word-limit
          />
        </el-form-item>
      </div>

      <el-alert
        v-if="assigneeError"
        :title="assigneeError"
        type="warning"
        show-icon
        :closable="false"
        class="customer-form-alert"
      />
      <el-alert
        v-if="nameCheckError"
        :title="nameCheckError"
        type="warning"
        show-icon
        :closable="false"
        class="customer-form-alert"
      />
      <el-alert
        v-if="duplicateMatches.length"
        :title="`发现 ${duplicateMatches.length} 条同名客户，请确认后再保存。`"
        type="warning"
        show-icon
        :closable="false"
        class="customer-form-alert"
      >
        <template #default>
          <ul class="duplicate-list">
            <li v-for="match in duplicateMatches" :key="match.id">
              {{ match.name }} · {{ match.customer_no }} · {{ match.owner_name }}
            </li>
          </ul>
        </template>
      </el-alert>

      <div class="customer-form-actions">
        <el-button @click="goBack">取消</el-button>
        <el-button type="primary" :loading="saving || nameChecking" @click="submit">
          {{ isEditing ? '保存更改' : '创建客户' }}
        </el-button>
      </div>
    </el-form>
  </section>
</template>
