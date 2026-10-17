import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: 'rbac', name: 'rbac', component: () => import('./views/PermissionManagement.vue'), meta: { title: '权限管理' } },
]

export default routes
