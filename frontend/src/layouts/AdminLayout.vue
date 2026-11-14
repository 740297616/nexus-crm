<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  DataAnalysis,
  Fold,
  Collection,
  Menu as MenuIcon,
  Setting,
  User,
  UserFilled,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import { useAppStore } from '@/stores/app'

const appStore = useAppStore()
const route = useRoute()
const router = useRouter()

const activeMenu = computed(() => route.path)
const pageTitle = computed(() => String(route.meta.title ?? '工作台'))

const menuItems = [
  { index: '/', title: '工作台', icon: DataAnalysis },
  { index: '/customers', title: '客户管理', icon: Collection },
  { index: '/contacts', title: '联系人管理', icon: User },
  { index: '/follow-ups', title: '跟进记录', icon: UserFilled },
  { index: '/settings', title: '系统设置', icon: Setting },
]

function navigate(path: string) {
  void router.push(path)
}

function showProfilePlaceholder() {
  ElMessage.info('用户中心将在认证模块完成后启用')
}
</script>

<template>
  <el-container class="admin-shell">
    <el-aside :width="appStore.sidebarCollapsed ? '72px' : '232px'" class="admin-sidebar">
      <div class="brand" :class="{ compact: appStore.sidebarCollapsed }">
        <div class="brand-mark">N</div>
        <span v-if="!appStore.sidebarCollapsed" class="brand-name">Nexus CRM</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="appStore.sidebarCollapsed"
        class="navigation-menu"
        @select="navigate"
      >
        <el-menu-item v-for="item in menuItems" :key="item.index" :index="item.index">
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="topbar">
        <div class="topbar-left">
          <el-button text class="collapse-button" @click="appStore.toggleSidebar">
            <el-icon :size="20"
              ><Fold v-if="!appStore.sidebarCollapsed" /><MenuIcon v-else
            /></el-icon>
          </el-button>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>Nexus CRM</el-breadcrumb-item>
            <el-breadcrumb-item>{{ pageTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <el-dropdown trigger="click" @command="showProfilePlaceholder">
          <button class="user-profile" type="button">
            <el-avatar :size="34">A</el-avatar>
            <span class="user-copy">
              <strong>访客用户</strong>
              <small>基础布局预览</small>
            </span>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">个人信息</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <el-main class="main-content">
        <RouterView />
      </el-main>
    </el-container>
  </el-container>
</template>
