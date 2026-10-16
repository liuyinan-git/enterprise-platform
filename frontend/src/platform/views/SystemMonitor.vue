<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>系统运行监控</span>
        <div>
          <el-button :disabled="loading" @click="load">刷新</el-button>
          <el-button type="danger" plain :disabled="loading" @click="reset">还原</el-button>
        </div>
      </div>
    </template>

    <template v-if="overview">
      <h4 class="section-title">接入流水</h4>
      <el-row :gutter="16">
        <el-col v-for="s in flowStats" :key="s.label" :xs="12" :sm="8" :md="6">
          <el-card class="stat-card" shadow="never">
            <div class="stat-value">{{ s.value }}</div>
            <div class="stat-label">{{ s.label }}</div>
          </el-card>
        </el-col>
      </el-row>

      <h4 class="section-title">处理队列</h4>
      <el-row :gutter="16">
        <el-col v-for="s in queueStats" :key="s.label" :xs="12" :sm="8" :md="6">
          <el-card class="stat-card" shadow="never">
            <div class="stat-value" :class="{ warn: s.warn }">{{ s.value }}</div>
            <div class="stat-label">{{ s.label }}</div>
          </el-card>
        </el-col>
      </el-row>

      <h4 class="section-title">业务产出</h4>
      <el-row :gutter="16">
        <el-col v-for="s in outputStats" :key="s.label" :xs="12" :sm="8" :md="6">
          <el-card class="stat-card" shadow="never">
            <div class="stat-value">{{ s.value }}</div>
            <div class="stat-label">{{ s.label }}</div>
          </el-card>
        </el-col>
      </el-row>
    </template>
    <el-empty v-else-if="!loading" description="暂无数据" />
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getSystemOverview, resetSystem, type SystemOverview } from '@/platform/monitoring/api'

const overview = ref<SystemOverview | null>(null)
const loading = ref(false)

const flowStats = computed(() => {
  const o = overview.value
  if (!o) return []
  return [
    { label: '原始日志总量', value: o.raw_total },
    { label: '标准化日志', value: o.event_total },
    { label: '接收批次', value: o.batch_total },
  ]
})

const queueStats = computed(() => {
  const o = overview.value
  if (!o) return []
  return [
    { label: '待处理原始日志', value: o.raw_pending, warn: o.raw_pending > 0 },
    { label: '解析失败', value: o.raw_failed, warn: o.raw_failed > 0 },
    { label: '待调度任务', value: o.task_pending },
    { label: '执行中任务', value: o.task_running },
    { label: '失败任务', value: o.task_failed, warn: o.task_failed > 0 },
  ]
})

const outputStats = computed(() => {
  const o = overview.value
  if (!o) return []
  return [
    { label: '安全事件', value: o.security_event_total },
    { label: '告警记录', value: o.alert_total },
    { label: '登记设备', value: o.device_total },
  ]
})

async function load() {
  loading.value = true
  try {
    overview.value = await getSystemOverview()
  } finally {
    loading.value = false
  }
}

async function reset() {
  await ElMessageBox.confirm(
    '确定清空所有日志、安全事件与告警记录吗？此操作不可恢复。',
    '还原提示',
    { type: 'warning', confirmButtonText: '确定清空', cancelButtonText: '取消' },
  )
  try {
    await resetSystem()
    ElMessage.success('已清空')
    load()
  } catch (e) {
    ElMessage.error(
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '清空失败',
    )
  }
}

onMounted(load)
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.section-title {
  margin: 8px 0 12px;
}
.stat-card {
  margin-bottom: 12px;
  text-align: center;
}
.stat-value {
  font-size: 26px;
  font-weight: 600;
}
.stat-value.warn {
  color: #f56c6c;
}
.stat-label {
  color: #909399;
  margin-top: 4px;
  font-size: 13px;
}
</style>
