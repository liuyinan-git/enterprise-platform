import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: MainLayout,
      redirect: '/dashboard',
      children: [
        {
          path: 'dashboard',
          name: 'dashboard',
          component: () => import('@/views/Dashboard.vue'),
          meta: { title: '安全态势总览' },
        },
        {
          path: 'logs',
          name: 'logs',
          component: () => import('@/views/LogSearch.vue'),
          meta: { title: '日志检索' },
        },
        {
          path: 'events',
          name: 'events',
          component: () => import('@/views/SecurityEvents.vue'),
          meta: { title: '安全事件中心' },
        },
        {
          path: 'alerts',
          name: 'alerts',
          component: () => import('@/views/Alerts.vue'),
          meta: { title: '告警管理' },
        },
        {
          path: 'rules',
          name: 'rules',
          component: () => import('@/views/Rules.vue'),
          meta: { title: '规则管理' },
        },
        {
          path: 'devices',
          name: 'devices',
          component: () => import('@/views/Devices.vue'),
          meta: { title: '设备管理' },
        },
        {
          path: 'collectors',
          name: 'collectors',
          component: () => import('@/views/Collectors.vue'),
          meta: { title: '采集端管理' },
        },
        {
          path: 'wecom',
          name: 'wecom',
          component: () => import('@/views/WecomConfig.vue'),
          meta: { title: '消息发送管理' },
        },
        {
          path: 'files',
          name: 'files',
          component: () => import('@/views/Files.vue'),
          meta: { title: '附件管理' },
        },
        {
          path: 'system',
          name: 'system',
          component: () => import('@/views/SystemMonitor.vue'),
          meta: { title: '系统运行监控' },
        },
      ],
    },
  ],
})

export default router
