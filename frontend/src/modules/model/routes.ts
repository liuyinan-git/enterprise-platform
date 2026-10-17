import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: 'model-providers', name: 'model-providers', component: () => import('./views/ModelProviders.vue'), meta: { title: '部署节点' } },
  { path: 'models', name: 'models', component: () => import('./views/ModelRegistry.vue'), meta: { title: '模型注册' } },
  { path: 'models/consumers', name: 'models-consumers', component: () => import('./views/ModelConsumers.vue'), meta: { title: '调用方台账' } },
  { path: 'models/alerts', name: 'models-alerts', component: () => import('./views/ModelAlerts.vue'), meta: { title: '模型告警' } },
  { path: 'model-usages', name: 'model-usages', component: () => import('./views/ModelUsage.vue'), meta: { title: '用量统计' } },
]

export default routes
