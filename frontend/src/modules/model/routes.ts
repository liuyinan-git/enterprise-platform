import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: 'model-providers', name: 'model-providers', component: () => import('./views/ModelProviders.vue'), meta: { title: '模型供应商' } },
  { path: 'models', name: 'models', component: () => import('./views/ModelRegistry.vue'), meta: { title: '模型注册' } },
  { path: 'model-usages', name: 'model-usages', component: () => import('./views/ModelUsage.vue'), meta: { title: '用量统计' } },
]

export default routes
