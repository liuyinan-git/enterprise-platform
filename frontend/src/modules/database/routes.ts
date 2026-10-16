import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: 'database-instances', name: 'database-instances', component: () => import('./views/DatabaseInstances.vue'), meta: { title: '数据库实例' } },
  { path: 'database-health', name: 'database-health', component: () => import('./views/DatabaseHealth.vue'), meta: { title: '健康检查' } },
  { path: 'database-backups', name: 'database-backups', component: () => import('./views/DatabaseBackups.vue'), meta: { title: '备份记录' } },
]

export default routes
