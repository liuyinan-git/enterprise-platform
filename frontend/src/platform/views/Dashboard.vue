<template>
  <div>
    <el-card class="mb">
      <template #header>后端连接状态</template>
      <div v-if="loading">正在检测…</div>
      <el-tag v-else-if="health" type="success">后端就绪 · 数据库 {{ health.database }}</el-tag>
      <el-tag v-else type="danger">后端不可达（请确认 7550 端口服务已启动）</el-tag>
    </el-card>

    <el-row :gutter="16">
      <el-col v-for="mod in modules" :key="mod.title" :xs="24" :sm="12" :md="6">
        <el-card class="module-card">
          <div class="module-title">{{ mod.title }}</div>
          <div class="module-stats">
            <div v-for="s in mod.stats" :key="s.label" class="stat">
              <div class="stat-value">{{ s.value }}</div>
              <div class="stat-label">{{ s.label }}</div>
            </div>
          </div>
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
import { getOverview, type PlatformOverview } from '@/platform/monitoring/api'

const loading = ref(true)
const health = ref<HealthResp | null>(null)
const overview = ref<PlatformOverview | null>(null)

const modules = computed(() => {
  const o = overview.value
  if (!o) return []
  const fmtRatio = (a: number | null, b: number | null) =>
    a == null || b == null ? '—' : `${a}/${b}`
  return [
    {
      title: '日志管控',
      stats: [
        { label: '接入设备', value: o.log.device_total },
        { label: '今日日志', value: o.log.event_today },
        { label: '未关闭事件', value: o.log.open_events },
        { label: '待发告警', value: o.log.pending_alerts },
      ],
    },
    {
      title: '智能体管控',
      stats: [
        { label: '项目', value: o.agent.project_count },
        { label: '接口健康', value: fmtRatio(o.agent.api_healthy, o.agent.api_total) },
        { label: '容器运行', value: fmtRatio(o.agent.running_count, o.agent.container_count) },
      ],
    },
    {
      title: '模型管控',
      stats: [
        { label: '部署节点', value: o.model.provider_count },
        { label: '模型', value: o.model.model_count },
        { label: '调用方', value: o.model.consumer_count },
        { label: '告警', value: o.model.alert_count },
      ],
    },
    {
      title: '数据库管控',
      stats: [
        { label: '实例', value: o.database.instance_count },
        { label: '备份', value: o.database.backup_count },
        { label: '容器', value: o.database.container_count == null ? '—' : o.database.container_count },
      ],
    },
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
    overview.value = await getOverview()
    renderChart()
  } catch {
    overview.value = null
  }
}

function renderChart() {
  if (!chartRef.value || !overview.value) return
  const trend = overview.value.log.trend
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
.module-card {
  margin-bottom: 16px;
}
.module-title {
  font-weight: 600;
  margin-bottom: 12px;
  color: #303133;
}
.module-stats {
  display: flex;
  flex-wrap: wrap;
}
.stat {
  width: 50%;
  margin-bottom: 10px;
}
.stat-value {
  font-size: 22px;
  font-weight: 600;
}
.stat-label {
  color: #909399;
  font-size: 13px;
  margin-top: 2px;
}
.chart {
  height: 320px;
}
</style>
