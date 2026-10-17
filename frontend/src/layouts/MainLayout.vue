<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">企业管控平台</div>
      <el-menu
        :default-active="activeMenu"
        router
        background-color="#001529"
        text-color="#a6b7cf"
        active-text-color="#409eff"
      >
        <el-sub-menu v-for="group in visibleMenuGroups" :key="group.title" :index="group.title">
          <template #title>
            <span>{{ group.title }}</span>
          </template>
          <el-menu-item v-for="item in group.items" :key="item.path" :index="item.path">
            <span>{{ item.title }}</span>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <span class="header-title">{{ currentTitle }}</span>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/core/auth/store'

interface MenuItem {
  path: string
  title: string
  roles: string[]
}

const menuGroups: { title: string; items: MenuItem[] }[] = [
  {
    title: '总览',
    items: [{ path: '/dashboard', title: '安全态势总览', roles: [] }],
  },
  {
    title: '日志管控',
    items: [
      { path: '/logs', title: '日志检索', roles: ['viewer', 'log_admin'] },
      { path: '/events', title: '安全事件中心', roles: ['viewer', 'log_admin'] },
      { path: '/alerts', title: '告警管理', roles: ['viewer', 'log_admin'] },
      { path: '/rules', title: '规则管理', roles: ['viewer', 'log_admin'] },
      { path: '/devices', title: '设备管理', roles: ['viewer', 'log_admin'] },
      { path: '/collectors', title: '采集端管理', roles: ['viewer', 'log_admin'] },
    ],
  },
  {
    title: '智能体管控',
    items: [
      { path: '/agents', title: '智能体管理', roles: ['viewer', 'agent_admin'] },
      { path: '/agent/overview', title: '平台概览', roles: ['viewer', 'agent_admin'] },
      // 该页有容器启停按钮，因此容器操作角色也要能进（照数据库实例页的既有做法）
      {
        path: '/agent/containers',
        title: 'Docker 容器',
        roles: ['viewer', 'agent_admin', 'agent_container_admin'],
      },
      { path: '/agent/projects', title: '项目与分类规则', roles: ['viewer', 'agent_admin'] },
      { path: '/agent/endpoints', title: '接口监控', roles: ['viewer', 'agent_admin'] },
      { path: '/agent/langgraph', title: 'LangGraph 管理', roles: ['viewer', 'agent_admin'] },
      { path: '/agent/history', title: '监控历史', roles: ['viewer', 'agent_admin'] },
      { path: '/agent/settings', title: '系统设置', roles: ['viewer', 'agent_admin'] },
    ],
  },
  {
    title: '模型管控',
    items: [
      { path: '/model-providers', title: '部署节点', roles: ['viewer', 'model_admin'] },
      { path: '/models', title: '模型注册', roles: ['viewer', 'model_admin'] },
      { path: '/models/consumers', title: '调用方台账', roles: ['viewer', 'model_admin'] },
      { path: '/models/alerts', title: '模型告警', roles: ['viewer', 'model_admin'] },
      { path: '/model-usages', title: '用量统计', roles: ['viewer', 'model_admin'] },
    ],
  },
  {
    title: '数据库管控',
    items: [
      // 该页已合并「容器实况」，因此容器操作角色也要能进
      { path: '/database-instances', title: '数据库实例', roles: ['viewer', 'database_admin', 'database_container_admin'] },
      { path: '/database-health', title: '健康检查', roles: ['viewer', 'database_admin'] },
      { path: '/database-backups', title: '备份记录', roles: ['viewer', 'database_admin'] },
    ],
  },
  {
    title: '平台管理',
    items: [
      { path: '/wecom', title: '消息发送管理', roles: ['admin'] },
      { path: '/files', title: '附件管理', roles: ['admin'] },
      { path: '/system', title: '系统运行监控', roles: ['viewer'] },
    ],
  },
]

const route = useRoute()
const auth = useAuthStore()

const visibleMenuGroups = computed(() =>
  menuGroups
    .map((group) => ({ ...group, items: group.items.filter((item) => auth.canAccess(item.roles)) }))
    .filter((group) => group.items.length > 0),
)

const activeMenu = computed(() => route.path)
const currentTitle = computed(() => (route.meta.title as string) || '')
</script>

<style scoped>
.layout {
  height: 100%;
}
.aside {
  background-color: #001529;
}
.logo {
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  padding: 18px 16px;
}
.header {
  display: flex;
  align-items: center;
  border-bottom: 1px solid #e4e7ed;
}
.header-title {
  font-size: 16px;
  font-weight: 600;
}
</style>
