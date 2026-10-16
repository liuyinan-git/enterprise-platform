import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'
import logRoutes from '@/modules/log/routes'
import agentRoutes from '@/modules/agent/routes'
import modelRoutes from '@/modules/model/routes'
import databaseRoutes from '@/modules/database/routes'
import platformRoutes from '@/platform/routes'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: MainLayout,
      redirect: '/dashboard',
      children: [
        ...platformRoutes,
        ...logRoutes,
        ...agentRoutes,
        ...modelRoutes,
        ...databaseRoutes,
      ],
    },
  ],
})

export default router
