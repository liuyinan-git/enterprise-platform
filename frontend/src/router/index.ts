import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'
import logRoutes from '@/modules/log/routes'
import agentRoutes from '@/modules/agent/routes'
import modelRoutes from '@/modules/model/routes'
import databaseRoutes from '@/modules/database/routes'
import platformRoutes from '@/platform/routes'
import { useAuthStore } from '@/core/auth/store'
import { getAccessToken } from '@/core/auth/oidc'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/auth/callback',
      name: 'auth-callback',
      component: () => import('@/views/AuthCallback.vue'),
      meta: { title: '登录回调' },
    },
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

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.initialized) {
    await auth.initAuth()
  }
  // 回调页放行
  if (to.path === '/auth/callback') {
    return true
  }
  // 启用 OIDC 且无 token 时跳转外部登录
  if (auth.authEnabled && !getAccessToken()) {
    await auth.startLogin()
    return false
  }
  return true
})

export default router
