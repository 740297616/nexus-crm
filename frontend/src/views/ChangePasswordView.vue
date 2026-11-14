<script setup lang="ts">
import { reactive } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '@/stores/auth'
import type { ApiErrorBody } from '@/types/api'

const router = useRouter()
const authStore = useAuthStore()
const form = reactive({ currentPassword: '', newPassword: '', confirmPassword: '' })

function errorMessage(error: unknown) {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    return error.response?.data.error.message ?? '密码修改失败，请稍后再试'
  }
  return '密码修改失败，请稍后再试'
}

async function submit() {
  if (form.newPassword !== form.confirmPassword) {
    ElMessage.error('两次输入的新密码不一致')
    return
  }
  try {
    await authStore.changePassword(form.currentPassword, form.newPassword)
    ElMessage.success('密码已修改，请重新登录')
    await router.replace('/login')
  } catch (error: unknown) {
    ElMessage.error(errorMessage(error))
  }
}
</script>

<template>
  <section class="page-view password-page">
    <div class="page-heading">
      <div>
        <p class="eyebrow">ACCOUNT SECURITY</p>
        <h1>修改密码</h1>
        <p class="page-description">修改密码后，当前账户的 Refresh Token 会全部失效。</p>
      </div>
    </div>
    <el-card class="password-card" shadow="never">
      <el-form :model="form" label-position="top" @submit.prevent="submit">
        <el-form-item label="当前密码">
          <el-input
            v-model="form.currentPassword"
            autocomplete="current-password"
            show-password
            type="password"
          />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input
            v-model="form.newPassword"
            autocomplete="new-password"
            show-password
            type="password"
          />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input
            v-model="form.confirmPassword"
            autocomplete="new-password"
            show-password
            type="password"
          />
        </el-form-item>
        <el-button native-type="submit" type="primary">保存密码</el-button>
      </el-form>
    </el-card>
  </section>
</template>
