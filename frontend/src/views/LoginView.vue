<script setup lang="ts">
import { reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '@/stores/auth'
import type { ApiErrorBody } from '@/types/api'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const form = reactive({ identifier: '', password: '' })

function errorMessage(error: unknown) {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    return error.response?.data.error.message ?? '登录失败，请稍后再试'
  }
  return '登录失败，请稍后再试'
}

async function submit() {
  try {
    await authStore.login(form.identifier, form.password)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.replace(redirect)
  } catch (error: unknown) {
    ElMessage.error(errorMessage(error))
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-card">
      <div class="login-brand">
        <div class="brand-mark">N</div>
        <div>
          <strong>Nexus CRM</strong>
          <span>企业客户管理平台</span>
        </div>
      </div>
      <div class="login-heading">
        <p class="eyebrow">WELCOME BACK</p>
        <h1>登录账户</h1>
        <p>使用企业账户进入管理后台。</p>
      </div>
      <el-form :model="form" label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名或邮箱">
          <el-input
            v-model="form.identifier"
            autocomplete="username"
            placeholder="请输入用户名或邮箱"
            size="large"
          />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            autocomplete="current-password"
            placeholder="请输入密码"
            show-password
            size="large"
            type="password"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-button
          :loading="authStore.isLoading"
          class="login-submit"
          native-type="submit"
          size="large"
          type="primary"
        >
          登录
        </el-button>
      </el-form>
      <p class="security-note">认证信息仅保存在当前会话内，不写入浏览器持久化存储。</p>
    </section>
  </main>
</template>
