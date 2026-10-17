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
  /** 查看该菜单所需权限；缺省表示无需权限（登录即可见） */
  permission?: string
}

const menuGroups: { title: string; items: MenuItem[] }[] = [
  {
    title: '总览',
    items: [{ path: '/dashboard', title: '平台总览' }],
  },
  {
    title: '日志管控',
    items: [
      { path: '/logs', title: '日志检索', permission: 'log:view' },
      { path: '/events', title: '安全事件中心', permission: 'log:view' },
      { path: '/alerts', title: '告警管理', permission: 'log:view' },
      { path: '/rules', title: '规则管理', permission: 'log:view' },
      { path: '/devices', title: '设备管理', permission: 'log:view' },
      { path: '/collectors', title: '采集端管理', permission: 'log:view' },
    ],
  },
  {
    title: '智能体管控',
    items: [
      { path: '/agents', title: '智能体管理', permission: 'agent:view' },
      { path: '/agent/overview', title: '平台概览', permission: 'agent:view' },
      // 该页有容器启停按钮，页面可见靠 agent:view，按钮级再按 agent:container 控制
      { path: '/agent/containers', title: 'Docker 容器', permission: 'agent:view' },
      { path: '/agent/projects', title: '项目与分类规则', permission: 'agent:view' },
      { path: '/agent/endpoints', title: '接口监控', permission: 'agent:view' },
      { path: '/agent/langgraph', title: 'LangGraph 管理', permission: 'agent:view' },
      { path: '/agent/history', title: '监控历史', permission: 'agent:view' },
      { path: '/agent/settings', title: '系统设置', permission: 'agent:view' },
    ],
  },
  {
    title: '模型管控',
    items: [
      { path: '/model-providers', title: '部署节点', permission: 'model:view' },
      { path: '/models', title: '模型注册', permission: 'model:view' },
      { path: '/models/consumers', title: '调用方台账', permission: 'model:view' },
      { path: '/models/alerts', title: '模型告警', permission: 'model:view' },
      { path: '/model-usages', title: '用量统计', permission: 'model:view' },
    ],
  },
  {
    title: '数据库管控',
    items: [
      // 该页已合并「容器实况」，页面可见靠 database:view，按钮级再按 database:container 控制
      { path: '/database-instances', title: '数据库实例', permission: 'database:view' },
      { path: '/database-health', title: '健康检查', permission: 'database:view' },
      { path: '/database-backups', title: '备份记录', permission: 'database:view' },
    ],
  },
  // 网关管控暂不启用（后续需要再放开）
  /*
  {
    title: '网关管控',
    items: [
      { path: '/gateway/squid', title: 'Squid 服务管理', permission: 'gateway:view' },
      { path: '/gateway/squid-log', title: 'Squid 日志分析', permission: 'gateway:view' },
      { path: '/gateway/apisix', title: 'APISIX 管理台', permission: 'gateway:view' },
      { path: '/gateway/apisix-log', title: 'APISIX 日志分析', permission: 'gateway:view' },
    ],
  },
  */
  {
    title: '平台管理',
    items: [
      { path: '/wecom', title: '消息发送管理', permission: 'platform:wecom' },
      { path: '/files', title: '附件管理', permission: 'platform:files' },
      { path: '/system', title: '系统运行监控', permission: 'platform:system' },
      { path: '/rbac', title: '权限管理', permission: 'platform:rbac' },
    ],
  },
]

const route = useRoute()
const auth = useAuthStore()

const visibleMenuGroups = computed(() =>
  menuGroups
    .map((group) => ({ ...group, items: group.items.filter((item) => auth.canAccess(item.permission)) }))
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
