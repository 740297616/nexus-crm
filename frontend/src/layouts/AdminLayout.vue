<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  DataAnalysis,
  Fold,
  Collection,
  Menu as MenuIcon,
  OfficeBuilding,
  Setting,
  User,
  UserFilled,
  Key,
  Bell,
} from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'

const appStore = useAppStore()
const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const activeMenu = computed(() => route.path)
const pageTitle = computed(() => String(route.meta.title ?? '工作台'))

const menuItems = computed(() =>
  [
    { index: '/', title: '工作台', icon: DataAnalysis, permission: 'dashboard:menu' },
    { index: '/users', title: '用户管理', icon: User, permission: 'users:menu' },
    {
      index: '/departments',
      title: '部门管理',
      icon: OfficeBuilding,
      permission: 'departments:menu',
    },
    { index: '/roles', title: '角色权限', icon: Key, permission: 'roles:menu' },
    { index: '/customers', title: '客户管理', icon: Collection, permission: 'customers:menu' },
    { index: '/follow-ups', title: '跟进记录', icon: UserFilled, permission: 'follow_ups:menu' },
    { index: '/reminders', title: '我的待办', icon: Bell, permission: 'reminders:menu' },
    { index: '/contacts', title: '联系人管理', icon: UserFilled, permission: 'contacts:menu' },
    { index: '/settings', title: '系统设置', icon: Setting, permission: 'settings:menu' },
  ].filter((item) => authStore.hasPermission(item.permission)),
)

function navigate(path: string) {
  void router.push(path)
}

function showProfilePlaceholder() {
  void router.push('/settings/password')
}

async function logout() {
  await authStore.logout()
  await router.push('/login')
}

function handleUserCommand(command: string) {
  if (command === 'profile') {
    showProfilePlaceholder()
  } else if (command === 'logout') {
    void logout()
  }
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
        <el-dropdown trigger="click" @command="handleUserCommand">
          <button class="user-profile" type="button">
            <el-avatar :size="34">A</el-avatar>
            <span class="user-copy">
              <strong>{{ authStore.user?.display_name ?? authStore.user?.username }}</strong>
              <small>{{ authStore.user?.email ?? '已认证用户' }}</small>
            </span>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">修改密码</el-dropdown-item>
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
