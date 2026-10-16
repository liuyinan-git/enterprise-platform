<template>
  <div>
    <el-card class="mb">
      <template #header>后端连接状态</template>
      <div v-if="loading">正在检测…</div>
      <el-tag v-else-if="health" type="success">后端就绪 · 数据库 {{ health.database }}</el-tag>
      <el-tag v-else type="danger">后端不可达（请确认 7553 端口服务已启动）</el-tag>
    </el-card>

    <el-row :gutter="16">
      <el-col v-for="s in stats" :key="s.label" :xs="12" :sm="6">
        <el-card>
          <div class="stat-value">{{ s.value }}</div>
          <div class="stat-label">{{ s.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="mt">
      <template #header>近 7 日日志趋势</template>
      <div ref="chartRef" class="chart"></div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { getHealth, type HealthResp } from '@/core/api/client'
import { getDashboardOverview, type DashboardOverview } from '@/platform/monitoring/api'

const loading = ref(true)
const health = ref<HealthResp | null>(null)
const overview = ref<DashboardOverview | null>(null)

const stats = computed(() => {
  const o = overview.value
  return [
    { label: '接入设备', value: o ? o.device_total : '—' },
    { label: '今日日志', value: o ? o.event_today : '—' },
    { label: '未关闭事件', value: o ? o.open_events : '—' },
    { label: '待发告警', value: o ? o.pending_alerts : '—' },
  ]
})

const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

async function load() {
  loading.value = true
  try {
    health.value = await getHealth()
  } catch {
    health.value = null
  } finally {
    loading.value = false
  }

  try {
    overview.value = await getDashboardOverview()
    renderChart()
  } catch {
    overview.value = null
  }
}

function renderChart() {
  if (!chartRef.value || !overview.value) return
  const trend = overview.value.trend
  if (!chart) chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: trend.map((t) => t.date) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      { name: '日志量', type: 'line', smooth: true, areaStyle: {}, data: trend.map((t) => t.count) },
    ],
  })
}

function onResize() {
  chart?.resize()
}

onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
})
</script>

<style scoped>
.mb {
  margin-bottom: 16px;
}
.mt {
  margin-top: 16px;
}
.stat-value {
  font-size: 28px;
  font-weight: 600;
}
.stat-label {
  color: #909399;
  margin-top: 4px;
}
.chart {
  height: 320px;
}
</style>
