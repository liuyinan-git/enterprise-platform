import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: 'logs', name: 'logs', component: () => import('./views/LogSearch.vue'), meta: { title: '日志检索' } },
  { path: 'events', name: 'events', component: () => import('./views/SecurityEvents.vue'), meta: { title: '安全事件中心' } },
  { path: 'alerts', name: 'alerts', component: () => import('./views/Alerts.vue'), meta: { title: '告警管理' } },
  { path: 'rules', name: 'rules', component: () => import('./views/Rules.vue'), meta: { title: '规则管理' } },
  { path: 'devices', name: 'devices', component: () => import('./views/Devices.vue'), meta: { title: '设备管理' } },
  { path: 'collectors', name: 'collectors', component: () => import('./views/Collectors.vue'), meta: { title: '采集端管理' } },
]

export default routes
