<script setup lang="ts">
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  createContact,
  deleteContact,
  listContacts,
  setPrimaryContact,
  updateContact,
  type ContactPayload,
} from '@/api/contacts'
import { deleteCustomer, getCustomer } from '@/api/customers'
import {
  createFollowUp,
  listFollowUps,
  updateFollowUp,
  type FollowUpPayload,
} from '@/api/followups'
import {
  bindCustomerTag,
  createTag,
  deleteTag,
  listCustomerTags,
  listTags,
  unbindCustomerTag,
  updateTag,
  type TagPayload,
} from '@/api/tags'
import { useAuthStore } from '@/stores/auth'
import type {
  ContactRecord,
  CustomerDetail,
  CustomerTagRecord,
  FollowUpMethod,
  FollowUpRecord,
  TagRecord,
} from '@/types/api'

interface ContactForm {
  name: string
  title: string
  phone: string
  email: string
  contact_method: string
  is_primary: boolean
  remark: string
}

interface TagForm {
  name: string
  description: string
}

interface FollowUpForm {
  contact_id: string
  method: FollowUpMethod
  content: string
  followed_at: string
  result: string
  next_follow_up_at: string
}

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
const canContactRead = computed(() => authStore.hasPermission('contacts:read'))
const canContactCreate = computed(() => authStore.hasPermission('contacts:create'))
const canContactUpdate = computed(() => authStore.hasPermission('contacts:update'))
const canContactDelete = computed(() => authStore.hasPermission('contacts:delete'))
const canContactPrimary = computed(() => authStore.hasPermission('contacts:set_primary'))
const canTagRead = computed(() => authStore.hasPermission('tags:read'))
const canTagBind = computed(() => authStore.hasPermission('tags:bind'))
const canTagUnbind = computed(() => authStore.hasPermission('tags:unbind'))
const canTagManage = computed(
  () =>
    authStore.hasPermission('tags:create') ||
    authStore.hasPermission('tags:update') ||
    authStore.hasPermission('tags:delete'),
)
const canFollowUpRead = computed(() => authStore.hasPermission('follow_ups:read'))
const canFollowUpCreate = computed(() => authStore.hasPermission('follow_ups:create'))
const canFollowUpUpdate = computed(() => authStore.hasPermission('follow_ups:update'))

const contacts = ref<ContactRecord[]>([])
const contactsTotal = ref(0)
const contactsPage = ref(1)
const contactsPageSize = ref(10)
const contactsSearch = ref('')
const contactsLoading = ref(false)
const contactsError = ref('')
const contactDialogVisible = ref(false)
const contactSaving = ref(false)
const contactFormRef = ref<FormInstance>()
const editingContactId = ref<string | null>(null)
const contactForm = reactive<ContactForm>(emptyContactForm())

const contactRules: FormRules<ContactForm> = {
  name: [
    { required: true, message: '请输入联系人姓名', trigger: 'blur' },
    { max: 100, message: '姓名不能超过 100 个字符', trigger: 'blur' },
  ],
  title: [{ max: 100, message: '职务不能超过 100 个字符', trigger: 'blur' }],
  phone: [{ max: 40, message: '手机号不能超过 40 个字符', trigger: 'blur' }],
  email: [
    {
      validator: (_rule, value: string, callback) => {
        if (!value || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) callback()
        else callback(new Error('请输入有效的邮箱地址'))
      },
      trigger: 'blur',
    },
  ],
  contact_method: [{ max: 50, message: '联系方式不能超过 50 个字符', trigger: 'blur' }],
  remark: [{ max: 4000, message: '备注不能超过 4000 个字符', trigger: 'blur' }],
}

const tags = ref<TagRecord[]>([])
const customerTags = ref<CustomerTagRecord[]>([])
const selectedTagId = ref('')
const tagsLoading = ref(false)
const tagsError = ref('')
const tagDialogVisible = ref(false)
const tagFormVisible = ref(false)
const tagSaving = ref(false)
const editingTagId = ref<string | null>(null)
const tagForm = reactive<TagForm>(emptyTagForm())
const availableTags = computed(() => {
  const boundIds = new Set(customerTags.value.map((item) => item.tag_id))
  return tags.value.filter((tag) => !boundIds.has(tag.id))
})
const canEditTag = computed(() => authStore.hasPermission('tags:update'))
const canDeleteTag = computed(() => authStore.hasPermission('tags:delete'))

const followUps = ref<FollowUpRecord[]>([])
const followUpsTotal = ref(0)
const followUpsLoading = ref(false)
const followUpsError = ref('')
const followUpDialogVisible = ref(false)
const followUpSaving = ref(false)
const followUpFormRef = ref<FormInstance>()
const editingFollowUpId = ref<string | null>(null)
const followUpForm = reactive<FollowUpForm>(emptyFollowUpForm())
const followUpRules: FormRules<FollowUpForm> = {
  method: [{ required: true, message: '请选择跟进方式', trigger: 'change' }],
  content: [
    { required: true, message: '请输入跟进内容', trigger: 'blur' },
    { max: 10000, message: '跟进内容不能超过 10000 个字符', trigger: 'blur' },
  ],
  followed_at: [{ required: true, message: '请选择跟进时间', trigger: 'change' }],
}

function emptyContactForm(): ContactForm {
  return {
    name: '',
    title: '',
    phone: '',
    email: '',
    contact_method: '',
    is_primary: false,
    remark: '',
  }
}

function emptyTagForm(): TagForm {
  return { name: '', description: '' }
}

function emptyFollowUpForm(): FollowUpForm {
  return {
    contact_id: '',
    method: 'phone',
    content: '',
    followed_at: toDateTimeLocal(new Date()),
    result: '',
    next_follow_up_at: '',
  }
}

function toDateTimeLocal(value: Date) {
  const offset = value.getTimezoneOffset() * 60_000
  return new Date(value.getTime() - offset).toISOString().slice(0, 16)
}

function toIso(value: string) {
  return value ? new Date(value).toISOString() : null
}

function nullable(value: string) {
  return value.trim() || null
}

function formatDate(value: string) {
  return new Date(value).toLocaleString()
}

function levelLabel(level: CustomerDetail['level']) {
  return { A: 'A 重点', B: 'B 优先', C: 'C 常规', D: 'D 观察' }[level]
}

function followUpMethodLabel(method: FollowUpMethod) {
  return {
    phone: '电话',
    visit: '上门拜访',
    wechat: '微信',
    email: '邮件',
    other: '其他',
  }[method]
}

async function loadContacts() {
  if (!customer.value || !canContactRead.value) return
  contactsLoading.value = true
  contactsError.value = ''
  try {
    const response = await listContacts(customerId.value, {
      search: contactsSearch.value.trim() || undefined,
      page: contactsPage.value,
      page_size: contactsPageSize.value,
    })
    contacts.value = response.data.items
    contactsTotal.value = response.data.total
  } catch {
    contactsError.value = '联系人加载失败，请重试。'
  } finally {
    contactsLoading.value = false
  }
}

function searchContacts() {
  contactsPage.value = 1
  void loadContacts()
}

async function loadTags() {
  if (!customer.value || !canTagRead.value) return
  tagsLoading.value = true
  tagsError.value = ''
  try {
    const [tagItems, boundItems] = await Promise.all([
      listTags(),
      listCustomerTags(customerId.value),
    ])
    tags.value = tagItems
    customerTags.value = boundItems
  } catch {
    tagsError.value = '客户标签加载失败，请重试。'
  } finally {
    tagsLoading.value = false
  }
}

async function loadFollowUps() {
  if (!customer.value || !canFollowUpRead.value) return
  followUpsLoading.value = true
  followUpsError.value = ''
  try {
    const response = await listFollowUps(customerId.value, { page: 1, page_size: 100 })
    followUps.value = response.data.items
    followUpsTotal.value = response.data.total
  } catch {
    followUpsError.value = '跟进记录加载失败，请重试。'
  } finally {
    followUpsLoading.value = false
  }
}

async function loadCustomer() {
  loading.value = true
  loadError.value = ''
  try {
    customer.value = await getCustomer(customerId.value)
    await Promise.all([loadContacts(), loadTags(), loadFollowUps()])
  } catch {
    customer.value = null
    loadError.value = '客户不存在、已删除或当前账号无权查看。'
  } finally {
    loading.value = false
  }
}

function openFollowUpCreate() {
  editingFollowUpId.value = null
  Object.assign(followUpForm, emptyFollowUpForm())
  followUpDialogVisible.value = true
}

function openFollowUpEdit(record: FollowUpRecord) {
  editingFollowUpId.value = record.id
  Object.assign(followUpForm, {
    contact_id: record.contact_id ?? '',
    method: record.method,
    content: record.content,
    followed_at: toDateTimeLocal(new Date(record.followed_at)),
    result: record.result ?? '',
    next_follow_up_at: record.next_follow_up_at
      ? toDateTimeLocal(new Date(record.next_follow_up_at))
      : '',
  })
  followUpDialogVisible.value = true
}

async function saveFollowUp() {
  if (!followUpFormRef.value) return
  try {
    await followUpFormRef.value.validate()
  } catch {
    return
  }
  const payload: FollowUpPayload = {
    contact_id: followUpForm.contact_id || null,
    method: followUpForm.method,
    content: followUpForm.content.trim(),
    followed_at: toIso(followUpForm.followed_at) ?? new Date().toISOString(),
    result: nullable(followUpForm.result),
    next_follow_up_at: toIso(followUpForm.next_follow_up_at),
  }
  followUpSaving.value = true
  try {
    if (editingFollowUpId.value) {
      await updateFollowUp(customerId.value, editingFollowUpId.value, payload)
      ElMessage.success('跟进记录已更新')
    } else {
      await createFollowUp(customerId.value, payload)
      ElMessage.success('跟进记录已创建')
    }
    followUpDialogVisible.value = false
    await loadFollowUps()
  } catch {
    ElMessage.error('跟进记录保存失败，请检查权限、时间和关联联系人。')
  } finally {
    followUpSaving.value = false
  }
}

function openContactCreate() {
  editingContactId.value = null
  Object.assign(contactForm, emptyContactForm())
  contactDialogVisible.value = true
}

function openContactEdit(contact: ContactRecord) {
  editingContactId.value = contact.id
  Object.assign(contactForm, {
    name: contact.name,
    title: contact.title ?? '',
    phone: contact.phone ?? '',
    email: contact.email ?? '',
    contact_method: contact.contact_method ?? '',
    is_primary: contact.is_primary,
    remark: contact.remark ?? '',
  })
  contactDialogVisible.value = true
}

async function saveContact() {
  if (!contactFormRef.value) return
  try {
    await contactFormRef.value.validate()
  } catch {
    return
  }
  const payload: ContactPayload = {
    name: contactForm.name.trim(),
    title: nullable(contactForm.title),
    phone: nullable(contactForm.phone),
    email: nullable(contactForm.email),
    contact_method: nullable(contactForm.contact_method),
    is_primary: contactForm.is_primary,
    remark: nullable(contactForm.remark),
  }
  contactSaving.value = true
  try {
    if (editingContactId.value) {
      const updatePayload: Partial<Omit<ContactPayload, 'is_primary'>> = {
        name: payload.name,
        title: payload.title,
        phone: payload.phone,
        email: payload.email,
        contact_method: payload.contact_method,
        remark: payload.remark,
      }
      await updateContact(customerId.value, editingContactId.value, updatePayload)
      ElMessage.success('联系人已更新')
    } else {
      await createContact(customerId.value, payload)
      ElMessage.success('联系人已创建')
    }
    contactDialogVisible.value = false
    await loadContacts()
  } catch {
    ElMessage.error('联系人保存失败，请检查权限和字段内容。')
  } finally {
    contactSaving.value = false
  }
}

async function removeContact(contact: ContactRecord) {
  try {
    await ElMessageBox.confirm(`软删除联系人“${contact.name}”？`, '确认删除', { type: 'warning' })
    await deleteContact(customerId.value, contact.id)
    ElMessage.success('联系人已删除')
    if (contacts.value.length === 1 && contactsPage.value > 1) contactsPage.value -= 1
    await loadContacts()
  } catch (error: unknown) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('联系人删除失败')
  }
}

async function makePrimary(contact: ContactRecord) {
  try {
    await setPrimaryContact(customerId.value, contact.id)
    ElMessage.success('主要联系人已更新')
    await loadContacts()
  } catch {
    ElMessage.error('主要联系人更新失败，请重试。')
  }
}

function changeContactPage(page: number) {
  contactsPage.value = page
  void loadContacts()
}

function changeContactPageSize(pageSize: number) {
  contactsPageSize.value = pageSize
  contactsPage.value = 1
  void loadContacts()
}

async function bindSelectedTag() {
  if (!selectedTagId.value) return
  try {
    await bindCustomerTag(customerId.value, selectedTagId.value)
    selectedTagId.value = ''
    ElMessage.success('标签已绑定')
    await loadTags()
  } catch {
    ElMessage.error('标签绑定失败，可能已绑定或已超出权限范围。')
  }
}

async function unbindTag(tag: CustomerTagRecord) {
  try {
    await ElMessageBox.confirm(`移除标签“${tag.tag_name}”？`, '确认解绑', { type: 'warning' })
    await unbindCustomerTag(customerId.value, tag.tag_id)
    ElMessage.success('标签已解绑')
    await loadTags()
  } catch (error: unknown) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('标签解绑失败')
  }
}

function openTagManagement() {
  tagDialogVisible.value = true
  tagFormVisible.value = false
}

function openTagCreate() {
  editingTagId.value = null
  Object.assign(tagForm, emptyTagForm())
  tagFormVisible.value = true
}

function openTagEdit(tag: TagRecord) {
  editingTagId.value = tag.id
  Object.assign(tagForm, { name: tag.name, description: tag.description ?? '' })
  tagFormVisible.value = true
}

async function saveTag() {
  const payload: TagPayload = {
    name: tagForm.name.trim(),
    description: nullable(tagForm.description),
  }
  if (!payload.name) {
    ElMessage.warning('请输入标签名称')
    return
  }
  tagSaving.value = true
  try {
    if (editingTagId.value) {
      await updateTag(editingTagId.value, payload)
      ElMessage.success('标签已更新')
    } else {
      await createTag(payload)
      ElMessage.success('标签已创建')
    }
    tagFormVisible.value = false
    await loadTags()
  } catch {
    ElMessage.error('标签保存失败，标签名称可能已存在。')
  } finally {
    tagSaving.value = false
  }
}

async function removeTag(tag: TagRecord) {
  try {
    await ElMessageBox.confirm(
      `删除标签“${tag.name}”？已存在的客户关系会保留，但不再显示该标签。`,
      '确认删除',
      { type: 'warning' },
    )
    await deleteTag(tag.id)
    ElMessage.success('标签已删除')
    await loadTags()
  } catch (error: unknown) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('标签删除失败')
  }
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

      <section v-if="canContactRead" class="customer-detail-section">
        <div class="section-heading-row">
          <div>
            <h2>联系人</h2>
            <p>联系人属于当前客户，权限和数据范围随客户生效</p>
          </div>
          <el-button v-if="canContactCreate" type="primary" @click="openContactCreate"
            >新增联系人</el-button
          >
        </div>
        <div class="related-toolbar">
          <el-input
            v-model="contactsSearch"
            clearable
            placeholder="搜索姓名、职务、手机号或邮箱"
            class="related-search"
            @keyup.enter="searchContacts"
            @clear="searchContacts"
          />
          <el-button @click="searchContacts">查询</el-button>
        </div>
        <el-alert
          v-if="contactsError"
          :title="contactsError"
          type="error"
          show-icon
          :closable="false"
        >
          <template #default
            ><el-button link type="primary" @click="loadContacts">重试</el-button></template
          >
        </el-alert>
        <el-table v-loading="contactsLoading" :data="contacts" row-key="id" class="data-table">
          <el-table-column label="联系人" min-width="160">
            <template #default="scope">
              <button class="related-name-button" type="button" @click="openContactEdit(scope.row)">
                <strong>{{ scope.row.name }}</strong>
                <el-tag v-if="scope.row.is_primary" type="success" size="small">主要</el-tag>
              </button>
            </template>
          </el-table-column>
          <el-table-column label="职务" min-width="120" prop="title" />
          <el-table-column label="手机号" min-width="140" prop="phone" />
          <el-table-column label="邮箱" min-width="200" prop="email" />
          <el-table-column label="联系方式" min-width="120" prop="contact_method" />
          <el-table-column label="更新时间" min-width="170">
            <template #default="scope">{{ formatDate(scope.row.updated_at) }}</template>
          </el-table-column>
          <el-table-column
            v-if="canContactUpdate || canContactDelete || canContactPrimary"
            label="操作"
            width="240"
            fixed="right"
          >
            <template #default="scope">
              <el-button
                v-if="canContactPrimary && !scope.row.is_primary"
                link
                type="success"
                @click="makePrimary(scope.row)"
                >设为主要</el-button
              >
              <el-button
                v-if="canContactUpdate"
                link
                type="primary"
                @click="openContactEdit(scope.row)"
                >编辑</el-button
              >
              <el-button
                v-if="canContactDelete"
                link
                type="danger"
                @click="removeContact(scope.row)"
                >删除</el-button
              >
            </template>
          </el-table-column>
          <template #empty><el-empty description="暂无联系人" /></template>
        </el-table>
        <div class="pagination-row">
          <span>共 {{ contactsTotal }} 位联系人</span>
          <el-pagination
            :current-page="contactsPage"
            :page-size="contactsPageSize"
            :page-sizes="[10, 20, 50]"
            :total="contactsTotal"
            layout="sizes, prev, pager, next"
            @current-change="changeContactPage"
            @size-change="changeContactPageSize"
          />
        </div>
      </section>

      <section v-if="canTagRead" class="customer-detail-section">
        <div class="section-heading-row">
          <div>
            <h2>客户标签</h2>
            <p>标签用于筛选和归类客户，删除标签不会破坏历史关联</p>
          </div>
          <el-button v-if="canTagManage" @click="openTagManagement">管理标签</el-button>
        </div>
        <el-alert v-if="tagsError" :title="tagsError" type="error" show-icon :closable="false" />
        <div v-loading="tagsLoading" class="customer-tags-area">
          <div class="bound-tags">
            <el-tag
              v-for="tag in customerTags"
              :key="tag.tag_id"
              :closable="canTagUnbind"
              effect="plain"
              @close="unbindTag(tag)"
              >{{ tag.tag_name }}</el-tag
            >
            <span v-if="!customerTags.length" class="related-muted">暂无标签</span>
          </div>
          <el-select
            v-if="canTagBind"
            v-model="selectedTagId"
            clearable
            filterable
            placeholder="绑定标签"
            class="tag-select"
            @change="bindSelectedTag"
          >
            <el-option
              v-for="tag in availableTags"
              :key="tag.id"
              :label="tag.name"
              :value="tag.id"
            />
          </el-select>
        </div>
      </section>

      <section v-if="canFollowUpRead" class="customer-detail-section">
        <div class="section-heading-row">
          <div>
            <h2>跟进时间线</h2>
            <p>记录客户沟通过程和下次跟进安排</p>
          </div>
          <el-button v-if="canFollowUpCreate" type="primary" @click="openFollowUpCreate"
            >新增跟进</el-button
          >
        </div>
        <el-alert
          v-if="followUpsError"
          :title="followUpsError"
          type="error"
          show-icon
          :closable="false"
        >
          <template #default
            ><el-button link type="primary" @click="loadFollowUps">重试</el-button></template
          >
        </el-alert>
        <el-skeleton v-if="followUpsLoading" :rows="4" animated />
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
                <el-tag size="small" effect="plain">{{
                  followUpMethodLabel(record.method)
                }}</el-tag>
                <strong>{{ record.user_name }}</strong>
                <span v-if="record.contact_name" class="related-muted"
                  >联系 {{ record.contact_name }}</span
                >
              </div>
              <el-button
                v-if="canFollowUpUpdate"
                link
                type="primary"
                @click="openFollowUpEdit(record)"
              >
                编辑
              </el-button>
            </div>
            <p class="timeline-content">{{ record.content }}</p>
            <p v-if="record.result" class="timeline-result">结果：{{ record.result }}</p>
            <p v-if="record.next_follow_up_at" class="timeline-result">
              下次跟进：{{ formatDate(record.next_follow_up_at) }}
            </p>
          </el-timeline-item>
        </el-timeline>
        <div v-if="followUpsTotal > followUps.length" class="timeline-more-hint">
          仅显示最近 100 条记录
        </div>
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
          <el-table-column label="操作" width="110"
            ><template #default="scope">{{
              scope.row.action === 'assigned' ? '分配' : '转移'
            }}</template></el-table-column
          >
          <el-table-column label="原负责人" min-width="140"
            ><template #default="scope">{{
              scope.row.previous_owner_name || '—'
            }}</template></el-table-column
          >
          <el-table-column label="新负责人" min-width="140" prop="new_owner_name" />
          <el-table-column label="新所属部门" min-width="140" prop="new_department_name" />
          <el-table-column label="操作人" min-width="140" prop="transferred_by_name" />
          <el-table-column label="原因" min-width="180"
            ><template #default="scope">{{ scope.row.reason || '—' }}</template></el-table-column
          >
          <el-table-column label="操作时间" min-width="180"
            ><template #default="scope">{{
              formatDate(scope.row.created_at)
            }}</template></el-table-column
          >
        </el-table>
        <el-empty v-else description="暂无负责人变更记录" />
      </section>
    </template>

    <el-dialog
      v-model="followUpDialogVisible"
      :title="editingFollowUpId ? '编辑跟进记录' : '新增跟进记录'"
      width="680px"
    >
      <el-form
        ref="followUpFormRef"
        :model="followUpForm"
        :rules="followUpRules"
        label-position="top"
      >
        <div class="form-grid">
          <el-form-item label="跟进方式" prop="method" required>
            <el-select v-model="followUpForm.method" class="full-width">
              <el-option label="电话跟进" value="phone" />
              <el-option label="上门拜访" value="visit" />
              <el-option label="微信沟通" value="wechat" />
              <el-option label="邮件沟通" value="email" />
              <el-option label="其他方式" value="other" />
            </el-select>
          </el-form-item>
          <el-form-item label="关联联系人">
            <el-select v-model="followUpForm.contact_id" clearable class="full-width">
              <el-option
                v-for="contact in contacts"
                :key="contact.id"
                :label="contact.name"
                :value="contact.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="跟进时间" prop="followed_at" required>
            <el-input v-model="followUpForm.followed_at" type="datetime-local" />
          </el-form-item>
          <el-form-item label="下次跟进时间">
            <el-input v-model="followUpForm.next_follow_up_at" type="datetime-local" />
          </el-form-item>
        </div>
        <el-form-item label="跟进内容" prop="content" required>
          <el-input
            v-model="followUpForm.content"
            type="textarea"
            :rows="5"
            maxlength="10000"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="跟进结果">
          <el-input
            v-model="followUpForm.result"
            type="textarea"
            :rows="3"
            maxlength="2000"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="followUpDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="followUpSaving" @click="saveFollowUp">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="contactDialogVisible"
      :title="editingContactId ? '编辑联系人' : '新增联系人'"
      width="640px"
    >
      <el-form ref="contactFormRef" :model="contactForm" :rules="contactRules" label-position="top">
        <div class="form-grid">
          <el-form-item label="姓名" prop="name" required
            ><el-input v-model="contactForm.name"
          /></el-form-item>
          <el-form-item label="职务" prop="title"
            ><el-input v-model="contactForm.title"
          /></el-form-item>
          <el-form-item label="手机号" prop="phone"
            ><el-input v-model="contactForm.phone"
          /></el-form-item>
          <el-form-item label="邮箱" prop="email"
            ><el-input v-model="contactForm.email"
          /></el-form-item>
          <el-form-item label="联系方式" prop="contact_method"
            ><el-select v-model="contactForm.contact_method" clearable class="full-width"
              ><el-option label="电话" value="电话" /><el-option
                label="邮箱"
                value="邮箱" /><el-option label="微信" value="微信" /><el-option
                label="其他"
                value="其他" /></el-select
          ></el-form-item>
          <el-form-item v-if="!editingContactId" label="主要联系人"
            ><el-switch v-model="contactForm.is_primary" active-text="设为主要联系人"
          /></el-form-item>
          <el-form-item v-else label="主要联系人">
            <el-tag :type="contactForm.is_primary ? 'success' : 'info'">
              {{ contactForm.is_primary ? '当前为主要联系人' : '可在列表操作中设置' }}
            </el-tag>
          </el-form-item>
        </div>
        <el-form-item label="备注" prop="remark"
          ><el-input
            v-model="contactForm.remark"
            type="textarea"
            :rows="4"
            maxlength="4000"
            show-word-limit
        /></el-form-item>
      </el-form>
      <template #footer
        ><el-button @click="contactDialogVisible = false">取消</el-button
        ><el-button type="primary" :loading="contactSaving" @click="saveContact"
          >保存</el-button
        ></template
      >
    </el-dialog>

    <el-dialog v-model="tagDialogVisible" title="标签管理" width="620px">
      <div class="tag-management-heading">
        <span>当前可用标签 {{ tags.length }} 个</span
        ><el-button
          v-if="authStore.hasPermission('tags:create')"
          type="primary"
          @click="openTagCreate"
          >新建标签</el-button
        >
      </div>
      <el-table :data="tags" row-key="id" class="data-table">
        <el-table-column label="标签名称" prop="name" />
        <el-table-column label="说明" prop="description" />
        <el-table-column v-if="canEditTag || canDeleteTag" label="操作" width="150"
          ><template #default="scope"
            ><el-button v-if="canEditTag" link type="primary" @click="openTagEdit(scope.row)"
              >编辑</el-button
            ><el-button v-if="canDeleteTag" link type="danger" @click="removeTag(scope.row)"
              >删除</el-button
            ></template
          ></el-table-column
        >
        <template #empty><el-empty description="暂无标签" /></template>
      </el-table>
      <el-form v-if="tagFormVisible" label-position="top" class="tag-form">
        <el-form-item label="标签名称" required
          ><el-input v-model="tagForm.name" maxlength="100"
        /></el-form-item>
        <el-form-item label="说明"
          ><el-input v-model="tagForm.description" maxlength="500"
        /></el-form-item>
        <div class="tag-form-actions">
          <el-button @click="tagFormVisible = false">取消</el-button
          ><el-button type="primary" :loading="tagSaving" @click="saveTag">保存</el-button>
        </div>
      </el-form>
    </el-dialog>
  </section>
</template>
