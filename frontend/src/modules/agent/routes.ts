import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: 'agents', name: 'agents', component: () => import('./views/AgentList.vue'), meta: { title: '智能体管理' } },
]

export default routes
