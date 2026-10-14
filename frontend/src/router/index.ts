import { createRouter, createWebHistory } from 'vue-router'

import MainLayout from '@/layouts/MainLayout.vue'

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
      ],
    },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (!to.meta.public && !token) {
    return { name: 'login' }
  }
})

export default router
