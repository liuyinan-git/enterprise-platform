import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: 'dashboard', name: 'dashboard', component: () => import('./views/Dashboard.vue'), meta: { title: '平台总览' } },
  { path: 'wecom', name: 'wecom', component: () => import('./views/WecomConfig.vue'), meta: { title: '消息发送管理' } },
  { path: 'files', name: 'files', component: () => import('./views/Files.vue'), meta: { title: '附件管理' } },
  { path: 'system', name: 'system', component: () => import('./views/SystemMonitor.vue'), meta: { title: '系统运行监控' } },
]

export default routes
