<template>
  <template v-if="container">
    <el-button size="small" @click="emit('log', container)">日志</el-button>
    <template v-if="operable">
      <el-button v-if="canStart(container)" size="small" type="success" @click="emit('action', container, 'start')">
        启动
      </el-button>
      <template v-if="canStop(container)">
        <el-button size="small" type="warning" @click="emit('action', container, 'stop')">停止</el-button>
        <el-button size="small" type="danger" @click="emit('action', container, 'restart')">重启</el-button>
      </template>
    </template>
  </template>
  <span v-else class="muted">—</span>
</template>

<script setup lang="ts">
import type { AgentContainerItem, ContainerAction } from '@/modules/agent/api'
import { canStart, canStop } from '@/modules/agent/display'

// 声明即自动暴露给模板，无需赋值给变量
defineProps<{
  container: AgentContainerItem | null
  /** 分类/保护/权限三道门禁都通过才为 true；不通过时不渲染生命周期按钮（不是置灰） */
  operable: boolean
}>()

const emit = defineEmits<{
  (e: 'log', container: AgentContainerItem): void
  (e: 'action', container: AgentContainerItem, action: ContainerAction): void
}>()
</script>

<style scoped>
.muted {
  color: #909399;
}
</style>
