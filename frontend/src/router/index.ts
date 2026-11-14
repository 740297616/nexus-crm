import { createRouter, createWebHistory } from 'vue-router'

import AdminLayout from '@/layouts/AdminLayout.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: AdminLayout,
      children: [
        {
          path: '',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
          meta: { title: '工作台' },
        },
        {
          path: 'customers',
          name: 'customers',
          component: () => import('@/views/PlaceholderView.vue'),
          meta: { title: '客户管理' },
        },
        {
          path: 'contacts',
          name: 'contacts',
          component: () => import('@/views/PlaceholderView.vue'),
          meta: { title: '联系人管理' },
        },
        {
          path: 'follow-ups',
          name: 'follow-ups',
          component: () => import('@/views/PlaceholderView.vue'),
          meta: { title: '跟进记录' },
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('@/views/PlaceholderView.vue'),
          meta: { title: '系统设置' },
        },
      ],
    },
  ],
})

export default router
