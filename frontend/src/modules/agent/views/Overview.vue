<template>
  <el-alert
    v-if="data?.degraded"
    class="degraded"
    type="warning"
    :closable="false"
    show-icon
    title="Docker 服务不可达，容器类统计暂不可用"
    :description="data.error || '接口监控数据不受影响。'"
  />

  <StatCards :cards="cards" />

  <el-row :gutter="16">
    <el-col :md="12">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>接口健康分布</span>
            <span v-if="data" class="hint">更新于 {{ data.generated_at.slice(11, 19) }}</span>
          </div>
        </template>
        <div ref="pieRef" class="chart"></div>
      </el-card>
    </el-col>
    <el-col :md="12">
      <el-card>
        <template #header>按服务类型的接口数</template>
        <div ref="barRef" class="chart"></div>
      </el-card>
    </el-col>
  </el-row>

  <el-card class="mt">
    <template #header>
      <div class="card-header">
        <span>最近异常接口</span>
        <el-button size="small" @click="load()">刷新</el-button>
      </div>
    </template>
    <el-table v-loading="loading" :data="data?.failing_endpoints || []" border stripe style="width: 100%">
      <template #empty>
        <el-empty description="没有异常接口" :image-size="80" />
      </template>
      <el-table-column prop="endpoint_code" label="端点编码" min-width="140" show-overflow-tooltip />
      <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
      <el-table-column label="类型" width="120">
        <template #default="{ row }">
          <el-tag :type="serviceTypeTagType(row.service_type)" size="small">{{ serviceTypeLabel(row.service_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="healthTagType(row.health_status)" size="small">{{ healthLabel(row.health_status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="last_http_status" label="HTTP" width="80" />
      <el-table-column label="连续失败" width="100">
        <template #default="{ row }">
          <el-tag type="danger" size="small" effect="plain">{{ row.consecutive_failures }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="last_error" label="最近错误" min-width="220" show-overflow-tooltip />
      <el-table-column prop="last_check_at" label="最近检查" width="180" />
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { fetchAgentOverview, type OverviewData } from '@/modules/agent/api'
import { healthLabel, healthTagType, serviceTypeLabel, serviceTypeTagType, type StatCard } from '@/modules/agent/display'
import StatCards from '@/modules/agent/components/StatCards.vue'

const data = ref<OverviewData | null>(null)
const loading = ref(false)

const cards = computed<StatCard[]>(() => {
  const d = data.value
  if (!d) return []
  return [
    { label: '纳管项目', value: d.project_count },
    { label: '容器总数', value: d.container_count },
    { label: '运行中', value: d.running_count, tone: 'ok' },
    { label: '已停止', value: d.stopped_count, tone: d.stopped_count ? 'warn' : undefined },
    { label: '未分类容器', value: d.unclassified_count, tone: d.unclassified_count ? 'warn' : undefined },
    { label: '监控接口', value: d.api_total },
    { label: '接口正常', value: d.api_healthy, tone: 'ok' },
    { label: '接口异常', value: d.api_unhealthy, tone: d.api_unhealthy ? 'bad' : undefined },
  ]
})

const pieRef = ref<HTMLDivElement | null>(null)
const barRef = ref<HTMLDivElement | null>(null)
let pie: echarts.ECharts | null = null
let bar: echarts.ECharts | null = null

function renderCharts() {
  const d = data.value
  if (!d) return

  if (pieRef.value) {
    if (!pie) pie = echarts.init(pieRef.value)
    const order = ['healthy', 'unhealthy', 'timeout', 'error', 'unknown']
    pie.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0 },
      series: [{
        type: 'pie',
        radius: ['40%', '65%'],
        data: order
          .map((key) => ({ name: healthLabel(key), value: d.api_by_status[key] || 0 }))
          .filter((item) => item.value > 0),
      }],
    })
  }

  if (barRef.value) {
    if (!bar) bar = echarts.init(barRef.value)
    const types = Object.keys(d.api_by_type)
    bar.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 40, right: 20, top: 30, bottom: 30 },
      xAxis: { type: 'category', data: types.map((t) => serviceTypeLabel(t)) },
      yAxis: { type: 'value', minInterval: 1 },
      series: [{ type: 'bar', barMaxWidth: 48, data: types.map((t) => d.api_by_type[t]) }],
    })
  }
}

function errDetail(e: unknown): string | undefined {
  return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
}

/**
 * silent=true 用于 30s 轮询：不翻 v-loading（不闪屏）、不弹错误提示。
 */
async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    data.value = await fetchAgentOverview()
    renderCharts()
  } catch (e: unknown) {
    if (!silent) ElMessage.error(errDetail(e) || '加载失败')
  } finally {
    if (!silent) loading.value = false
  }
}

function onResize() {
  pie?.resize()
  bar?.resize()
}

// 30s 静默轮询：仅在页面可见且没有在途请求时刷新；卸载必须清掉定时器。
let timer: ReturnType<typeof setInterval> | undefined

onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
  timer = setInterval(() => {
    if (document.visibilityState === 'visible' && !loading.value) load(true)
  }, 30000)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
  window.removeEventListener('resize', onResize)
  pie?.dispose()
  bar?.dispose()
})
</script>

<style scoped>
.degraded {
  margin-bottom: 12px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.hint {
  color: #909399;
  font-size: 12px;
}
.mt {
  margin-top: 16px;
}
.chart {
  height: 300px;
}
</style>
