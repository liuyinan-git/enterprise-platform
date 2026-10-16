import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  // 既有的智能体台账。注意它与下面的 /agent/* 是**不同前缀**：
  // 台账沿用 `/agents`（后端 /api/v1/agents），AI Agent 平台用 `/agent/*`（后端 /api/v1/agent/*）。
  { path: 'agents', name: 'agents', component: () => import('./views/AgentList.vue'), meta: { title: '智能体管理' } },

  // AI Agent 统一管理平台
  { path: 'agent/overview', name: 'agent-overview', component: () => import('./views/Overview.vue'), meta: { title: '平台概览' } },
  { path: 'agent/containers', name: 'agent-containers', component: () => import('./views/Containers.vue'), meta: { title: 'Docker 容器' } },
  { path: 'agent/projects', name: 'agent-projects', component: () => import('./views/Projects.vue'), meta: { title: '项目与分类规则' } },
  { path: 'agent/endpoints', name: 'agent-endpoints', component: () => import('./views/Endpoints.vue'), meta: { title: '接口监控' } },
  { path: 'agent/langgraph', name: 'agent-langgraph', component: () => import('./views/LangGraph.vue'), meta: { title: 'LangGraph 管理' } },
  { path: 'agent/history', name: 'agent-history', component: () => import('./views/HealthHistory.vue'), meta: { title: '监控历史' } },
  { path: 'agent/settings', name: 'agent-settings', component: () => import('./views/Settings.vue'), meta: { title: '系统设置' } },
]

export default routes
