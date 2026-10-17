import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: 'gateway/squid', name: 'gateway-squid', component: () => import('./views/SquidAdmin.vue'), meta: { title: 'Squid 服务管理' } },
  { path: 'gateway/squid-log', name: 'gateway-squid-log', component: () => import('./views/SquidLog.vue'), meta: { title: 'Squid 日志分析' } },
  { path: 'gateway/apisix', name: 'gateway-apisix', component: () => import('./views/ApisixAdmin.vue'), meta: { title: 'APISIX 管理台' } },
  { path: 'gateway/apisix-log', name: 'gateway-apisix-log', component: () => import('./views/ApisixLog.vue'), meta: { title: 'APISIX 日志分析' } },
]

export default routes
