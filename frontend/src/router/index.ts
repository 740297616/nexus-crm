import { createRouter, createWebHistory } from 'vue-router'

import AdminLayout from '@/layouts/AdminLayout.vue'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { title: '登录' },
    },
    {
      path: '/forbidden',
      name: 'forbidden',
      component: () => import('@/views/ForbiddenView.vue'),
      meta: { title: '无权访问', requiresAuth: true },
    },
    {
      path: '/',
      component: AdminLayout,
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
          meta: { title: '工作台', permission: 'dashboard:page' },
        },
        {
          path: 'users',
          name: 'users',
          component: () => import('@/views/UsersView.vue'),
          meta: { title: '用户管理', permission: 'users:page' },
        },
        {
          path: 'departments',
          name: 'departments',
          component: () => import('@/views/DepartmentsView.vue'),
          meta: { title: '部门管理', permission: 'departments:page' },
        },
        {
          path: 'roles',
          name: 'roles',
          component: () => import('@/views/RolesView.vue'),
          meta: { title: '角色权限', permission: 'roles:page' },
        },
        {
          path: 'customers',
          name: 'customers',
          component: () => import('@/views/CustomersView.vue'),
          meta: { title: '客户管理', permission: 'customers:page' },
        },
        {
          path: 'customers/new',
          name: 'customer-create',
          component: () => import('@/views/CustomerFormView.vue'),
          meta: { title: '新建客户', permission: 'customers:page' },
        },
        {
          path: 'customers/:customerId/edit',
          name: 'customer-edit',
          component: () => import('@/views/CustomerFormView.vue'),
          meta: { title: '编辑客户', permission: 'customers:page' },
        },
        {
          path: 'customers/:customerId',
          name: 'customer-detail',
          component: () => import('@/views/CustomerDetailView.vue'),
          meta: { title: '客户详情', permission: 'customers:page' },
        },
        {
          path: 'contacts',
          name: 'contacts',
          component: () => import('@/views/PlaceholderView.vue'),
          meta: { title: '联系人管理', permission: 'contacts:page' },
        },
        {
          path: 'follow-ups',
          name: 'follow-ups',
          component: () => import('@/views/PlaceholderView.vue'),
          meta: { title: '跟进记录', permission: 'follow_ups:page' },
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('@/views/PlaceholderView.vue'),
          meta: { title: '系统设置', permission: 'settings:page' },
        },
        {
          path: 'settings/password',
          name: 'change-password',
          component: () => import('@/views/ChangePasswordView.vue'),
          meta: { title: '修改密码' },
        },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const authStore = useAuthStore()
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && authStore.isAuthenticated) {
    return { name: 'dashboard' }
  }
  const requiredPermission = to.meta.permission
  if (typeof requiredPermission === 'string' && !authStore.hasPermission(requiredPermission)) {
    return { name: 'forbidden' }
  }
  return true
})

export default router
