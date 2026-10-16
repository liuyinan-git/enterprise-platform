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
        <el-sub-menu v-for="group in menuGroups" :key="group.title" :index="group.title">
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

const menuGroups = [
  {
    title: '总览',
    items: [{ path: '/dashboard', title: '安全态势总览' }],
  },
  {
    title: '日志管控',
    items: [
      { path: '/logs', title: '日志检索' },
      { path: '/events', title: '安全事件中心' },
      { path: '/alerts', title: '告警管理' },
      { path: '/rules', title: '规则管理' },
      { path: '/devices', title: '设备管理' },
      { path: '/collectors', title: '采集端管理' },
    ],
  },
  {
    title: '智能体管控',
    items: [{ path: '/agents', title: '智能体管理' }],
  },
  {
    title: '模型管控',
    items: [
      { path: '/model-providers', title: '模型供应商' },
      { path: '/models', title: '模型注册' },
      { path: '/model-usages', title: '用量统计' },
    ],
  },
  {
    title: '数据库管控',
    items: [
      { path: '/database-instances', title: '数据库实例' },
      { path: '/database-health', title: '健康检查' },
      { path: '/database-backups', title: '备份记录' },
    ],
  },
  {
    title: '平台管理',
    items: [
      { path: '/wecom', title: '消息发送管理' },
      { path: '/files', title: '附件管理' },
      { path: '/system', title: '系统运行监控' },
    ],
  },
]

const route = useRoute()
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
