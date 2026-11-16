<script setup lang="ts">
import {
  ElMessage,
  ElMessageBox,
  ElNotification,
  type FormInstance,
  type FormRules,
} from 'element-plus'
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'

import {
  cancelReminder,
  completeReminder,
  createReminder,
  listDueReminders,
  listMyReminders,
  listOverdueReminders,
  updateReminder,
  type ReminderPayload,
} from '@/api/reminders'
import { useAuthStore } from '@/stores/auth'
import type { ReminderRecord } from '@/types/api'

interface ReminderForm {
  title: string
  content: string
  remind_at: string
}

const authStore = useAuthStore()
const activeTab = ref<'mine' | 'due' | 'overdue'>('mine')
const reminders = ref<ReminderRecord[]>([])
const loading = ref(false)
const error = ref('')
const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const formRef = ref<FormInstance>()
const form = reactive<ReminderForm>(emptyForm())

const canCreate = computed(() => authStore.hasPermission('reminders:create'))
const canUpdate = computed(() => authStore.hasPermission('reminders:update'))
const canComplete = computed(() => authStore.hasPermission('reminders:complete'))
const canCancel = computed(() => authStore.hasPermission('reminders:cancel'))
const notifiedReminderIds = new Set<string>()
let pollingTimer: number | undefined

const rules: FormRules<ReminderForm> = {
  title: [
    { required: true, message: '请输入提醒标题', trigger: 'blur' },
    { max: 200, message: '标题不能超过 200 个字符', trigger: 'blur' },
  ],
  remind_at: [{ required: true, message: '请选择提醒时间', trigger: 'change' }],
}

function emptyForm(): ReminderForm {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return {
    title: '',
    content: '',
    remind_at: new Date(now.getTime() - offset).toISOString().slice(0, 16),
  }
}

function toIso(value: string) {
  return new Date(value).toISOString()
}

function formatDate(value: string) {
  return new Date(value).toLocaleString()
}

async function loadReminders() {
  loading.value = true
  error.value = ''
  try {
    const response =
      activeTab.value === 'due'
        ? await listDueReminders({ page: 1, page_size: 100 })
        : activeTab.value === 'overdue'
          ? await listOverdueReminders({ page: 1, page_size: 100 })
          : await listMyReminders({ page: 1, page_size: 100, sort_order: 'asc' })
    reminders.value = response.data.items
  } catch {
    error.value = '提醒加载失败，请重试。'
  } finally {
    loading.value = false
  }
}

async function pollDueReminders() {
  try {
    const response = await listDueReminders({ page: 1, page_size: 100 })
    for (const reminder of response.data.items) {
      if (notifiedReminderIds.has(reminder.id)) continue
      notifiedReminderIds.add(reminder.id)
      ElNotification({
        title: '提醒到期',
        message: reminder.title,
        type: 'warning',
        duration: 0,
      })
    }
  } catch {
    // The list view exposes request failures; background polling remains best effort.
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

function openEdit(reminder: ReminderRecord) {
  editingId.value = reminder.id
  const date = new Date(reminder.remind_at)
  const offset = date.getTimezoneOffset() * 60_000
  Object.assign(form, {
    title: reminder.title,
    content: reminder.content ?? '',
    remind_at: new Date(date.getTime() - offset).toISOString().slice(0, 16),
  })
  dialogVisible.value = true
}

async function saveReminder() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  const payload: ReminderPayload = {
    title: form.title.trim(),
    content: form.content.trim() || null,
    remind_at: toIso(form.remind_at),
    customer_id: null,
    follow_up_record_id: null,
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateReminder(editingId.value, payload)
      ElMessage.success('提醒已更新')
    } else {
      await createReminder(payload)
      ElMessage.success('提醒已创建')
    }
    dialogVisible.value = false
    await loadReminders()
  } catch {
    ElMessage.error('提醒保存失败，请检查权限和时间。')
  } finally {
    saving.value = false
  }
}

async function complete(reminder: ReminderRecord) {
  try {
    await completeReminder(reminder.id)
    ElMessage.success('提醒已完成')
    await loadReminders()
  } catch {
    ElMessage.error('提醒完成失败，请重试。')
  }
}

async function cancel(reminder: ReminderRecord) {
  try {
    await ElMessageBox.confirm(`取消提醒“${reminder.title}”？`, '确认取消', { type: 'warning' })
    await cancelReminder(reminder.id)
    ElMessage.success('提醒已取消')
    await loadReminders()
  } catch (reason: unknown) {
    if (reason !== 'cancel' && reason !== 'close') ElMessage.error('提醒取消失败')
  }
}

function statusLabel(status: ReminderRecord['status']) {
  return { pending: '待处理', completed: '已完成', cancelled: '已取消' }[status]
}

function statusType(status: ReminderRecord['status']) {
  return { pending: 'warning', completed: 'success', cancelled: 'info' }[status] as
    'warning' | 'success' | 'info'
}

onMounted(() => {
  void loadReminders()
  void pollDueReminders()
  pollingTimer = window.setInterval(() => void pollDueReminders(), 60_000)
})

onUnmounted(() => {
  if (pollingTimer !== undefined) window.clearInterval(pollingTimer)
})
</script>

<template>
  <section class="page-view">
    <div class="page-heading">
      <div>
        <p class="eyebrow">CRM / TASKS</p>
        <h1>我的待办</h1>
        <p class="page-description">集中处理到期和逾期提醒。</p>
      </div>
      <el-button v-if="canCreate" type="primary" @click="openCreate">新建提醒</el-button>
    </div>

    <el-tabs v-model="activeTab" @tab-change="loadReminders">
      <el-tab-pane label="我的待办" name="mine" />
      <el-tab-pane label="已到期" name="due" />
      <el-tab-pane label="已逾期" name="overdue" />
    </el-tabs>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false">
      <template #default
        ><el-button link type="primary" @click="loadReminders">重试</el-button></template
      >
    </el-alert>
    <el-table v-loading="loading" :data="reminders" row-key="id" class="data-table">
      <el-table-column label="提醒" min-width="260">
        <template #default="scope">
          <strong>{{ scope.row.title }}</strong>
          <p v-if="scope.row.content" class="table-secondary">{{ scope.row.content }}</p>
        </template>
      </el-table-column>
      <el-table-column label="提醒时间" min-width="180">
        <template #default="scope">
          <span :class="{ 'overdue-text': scope.row.is_overdue }">{{
            formatDate(scope.row.remind_at)
          }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="scope">
          <el-tag :type="statusType(scope.row.status)" effect="light">{{
            statusLabel(scope.row.status)
          }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="关联客户" min-width="160" prop="customer_name" />
      <el-table-column label="操作" width="250" fixed="right">
        <template #default="scope">
          <el-button
            v-if="canComplete && scope.row.status === 'pending'"
            link
            type="success"
            @click="complete(scope.row)"
          >
            完成
          </el-button>
          <el-button
            v-if="canCancel && scope.row.status === 'pending'"
            link
            type="warning"
            @click="cancel(scope.row)"
          >
            取消
          </el-button>
          <el-button
            v-if="canUpdate && scope.row.status === 'pending'"
            link
            type="primary"
            @click="openEdit(scope.row)"
          >
            编辑
          </el-button>
        </template>
      </el-table-column>
      <template #empty><el-empty description="暂无提醒" /></template>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑提醒' : '新建提醒'" width="560px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="标题" prop="title" required
          ><el-input v-model="form.title" maxlength="200"
        /></el-form-item>
        <el-form-item label="提醒时间" prop="remind_at" required
          ><el-input v-model="form.remind_at" type="datetime-local"
        /></el-form-item>
        <el-form-item label="备注"
          ><el-input
            v-model="form.content"
            type="textarea"
            :rows="4"
            maxlength="5000"
            show-word-limit
        /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveReminder">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>
