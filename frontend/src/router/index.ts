import { createRouter, createWebHistory } from 'vue-router'

import MainLayout from '@/layouts/MainLayout.vue'
import { can, currentRole, permissionForRoute } from '@/permissions'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: MainLayout,
      children: [
        { path: '', redirect: '/agent' },
        { path: 'agent', name: 'agent', component: () => import('@/views/AgentView.vue') },
        { path: 'dashboard', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
        { path: 'elements', name: 'elements', component: () => import('@/views/ElementsView.vue') },
        { path: 'quotes', name: 'quotes', component: () => import('@/views/QuotesView.vue') },
        { path: 'marks', name: 'marks', component: () => import('@/views/MarksView.vue') },
        { path: 'reports', name: 'reports', component: () => import('@/views/ReportsView.vue') },
        { path: 'suppliers', name: 'suppliers', component: () => import('@/views/SuppliersView.vue') },
        { path: 'admin', name: 'admin', component: () => import('@/views/AdminView.vue') },
        { path: '403', name: 'forbidden', component: () => import('@/views/ForbiddenView.vue') },
      ],
    },
  ],
})

router.beforeEach((to) => {
  if (!to.meta.public && !localStorage.getItem('token')) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  // 按路由名查权限矩阵；未登记的路由（登录、403）只校验登录态
  const permission = permissionForRoute(to.name)
  if (permission && !can(currentRole(), permission)) {
    return { name: 'forbidden', query: { from: to.fullPath } }
  }
})

export default router
