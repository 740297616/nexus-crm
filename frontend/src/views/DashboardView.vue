<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const cards = [
  { label: '客户总数', value: '—', hint: 'Phase 3 开始接入真实数据' },
  { label: '本周跟进', value: '—', hint: 'Phase 4 开始接入真实数据' },
  { label: '待跟进客户', value: '—', hint: '数据权限模块完成后展示' },
]
</script>

<template>
  <section class="page-view">
    <div class="page-heading">
      <div>
        <p class="eyebrow">NEXUS CRM</p>
        <h1>工作台</h1>
        <p class="page-description">项目基础设施已就绪，业务模块将在后续 Phase 接入。</p>
      </div>
      <el-tag type="info" effect="plain">Phase 0</el-tag>
    </div>

    <div class="stat-grid">
      <el-card v-for="card in cards" :key="card.label" shadow="never" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
        <span class="stat-hint">{{ card.hint }}</span>
      </el-card>
    </div>

    <el-card shadow="never" class="welcome-card">
      <el-result
        icon="success"
        title="基础管理后台已启动"
        sub-title="当前页面仅提供布局和导航占位，不包含业务功能。"
      >
        <template #extra>
          <el-button
            v-if="authStore.hasPermission('customers:page')"
            type="primary"
            @click="$router.push('/customers')"
          >
            查看占位页面
          </el-button>
        </template>
      </el-result>
    </el-card>
  </section>
</template>
