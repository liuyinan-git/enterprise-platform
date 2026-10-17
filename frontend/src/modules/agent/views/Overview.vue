<template>
  <el-alert
    v-if="data?.degraded"
    class="degraded"
    type="warning"
    :closable="false"
    show-icon
    title="Docker 服务不可达，智能体容器状态暂无法判定"
    :description="data.error || '接口监控数据不受影响。'"
  />

  <StatCards :cards="cards" />

  <el-row :gutter="16">
    <el-col :md="12">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>智能体状态分布</span>
            <span v-if="data" class="hint">更新于 {{ data.generated_at.slice(11, 19) }}</span>
          </div>
        </template>
        <div ref="agentPieRef" class="chart"></div>
      </el-card>
    </el-col>
    <el-col :md="12">
      <el-card>
        <template #header>接口健康分布</template>
        <div ref="pieRef" class="chart"></div>
      </el-card>
    </el-col>
  </el-row>

  <el-card class="mt">
    <template #header>
      <div class="card-header">
        <span>已登记智能体</span>
        <el-button size="small" @click="load()">刷新</el-button>
      </div>
    </template>
    <el-table v-loading="loading" :data="data?.agents || []" border stripe style="width: 100%">
      <template #empty>
        <el-empty description="还没有登记智能体" :image-size="80" />
      </template>
      <el-table-column prop="agent_id" label="智能体 ID" min-width="140" show-overflow-tooltip />
      <el-table-column prop="agent_name" label="名称" min-width="140" show-overflow-tooltip />
      <el-table-column prop="agent_type" label="类型" width="110" />
      <el-table-column label="容器名称" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.container_name">{{ row.container_name }}</span>
          <span v-else class="muted">未绑定</span>
        </template>
      </el-table-column>
      <el-table-column label="容器状态" width="110">
        <template #default="{ row }">
          <el-tag v-if="row.container_found" :type="stateTagType(row.container_state || '')" size="small">
            {{ stateLabel(row.container_state || '') }}
          </el-tag>
          <el-tooltip v-else-if="row.status === 'unknown'" placement="top" content="Docker 不可达，无法判定">
            <el-tag type="info" size="small">未知</el-tag>
          </el-tooltip>
          <el-tag v-else-if="row.container_name" type="danger" size="small">未找到</el-tag>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="监控状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="项目" min-width="130" show-overflow-tooltip>
        <template #default="{ row }">
          <el-tag v-if="row.project_name" type="success" size="small">{{ row.project_name }}</el-tag>
          <span v-else class="muted">未分类</span>
        </template>
      </el-table-column>
      <el-table-column prop="endpoint_total" label="监控接口" width="100" />
      <el-table-column label="异常接口" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.endpoint_unhealthy" type="danger" size="small">{{ row.endpoint_unhealthy }}</el-tag>
          <span v-else class="muted">0</span>
        </template>
      </el-table-column>
      <el-table-column prop="last_seen_at" label="最后心跳" min-width="170" />
    </el-table>
  </el-card>

  <el-card class="mt">
    <template #header>
      <div class="card-header">
        <span>最近异常接口</span>
      </div>
    </template>
    <el-table v-loading="loading" :data="data?.failing_endpoints || []" border stripe style="width: 100%">
      <template #empty>
        <el-empty description="没有异常接口" :image-size="80" />
      </template>
      <el-table-column prop="endpoint_code" label="端点编码" min-width="140" show-overflow-tooltip />
      <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
      <el-table-column prop="agent_id" label="所属智能体" min-width="140" show-overflow-tooltip />
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
import {
  healthLabel,
  healthTagType,
  serviceTypeLabel,
  serviceTypeTagType,
  stateLabel,
  stateTagType,
  type StatCard,
} from '@/modules/agent/display'
import StatCards from '@/modules/agent/components/StatCards.vue'

const data = ref<OverviewData | null>(null)
const loading = ref(false)

const cards = computed<StatCard[]>(() => {
  const d = data.value
  if (!d) return []
  return [
    { label: '已录入智能体', value: d.agent_total },
    { label: '容器运行中', value: d.agent_online, tone: 'ok' },
    { label: '未运行 / 未找到', value: d.agent_offline, tone: d.agent_offline ? 'bad' : undefined },
    { label: '状态未知', value: d.agent_unknown, tone: d.agent_unknown ? 'warn' : undefined },
    { label: '未绑定容器', value: d.agent_unbound, tone: d.agent_unbound ? 'warn' : undefined },
    { label: '监控接口', value: d.api_total },
    { label: '接口正常', value: d.api_healthy, tone: 'ok' },
    { label: '接口异常', value: d.api_unhealthy, tone: d.api_unhealthy ? 'bad' : undefined },
  ]
})

function statusType(s: string) {
  if (s === 'online') return 'success'
  if (s === 'disabled') return 'warning'
  if (s === 'unknown') return 'info'
  return 'danger'
}
function statusText(s: string) {
  if (s === 'online') return '在线'
  if (s === 'disabled') return '停用'
  if (s === 'unknown') return '未知'
  return '离线'
}

const pieRef = ref<HTMLDivElement | null>(null)
const agentPieRef = ref<HTMLDivElement | null>(null)
let pie: echarts.ECharts | null = null
let agentPie: echarts.ECharts | null = null

function renderCharts() {
  const d = data.value
  if (!d) return

  if (agentPieRef.value) {
    if (!agentPie) agentPie = echarts.init(agentPieRef.value)
    const statusOrder: { key: 'online' | 'offline' | 'unknown' | 'disabled'; label: string }[] = [
      { key: 'online', label: '在线' },
      { key: 'offline', label: '离线' },
      { key: 'unknown', label: '未知' },
      { key: 'disabled', label: '停用' },
    ]
    const statusValues: Record<string, number> = {
      online: d.agent_online,
      offline: d.agent_offline,
      unknown: d.agent_unknown,
      disabled: 0,
    }
    agentPie.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0 },
      series: [{
        type: 'pie',
        radius: ['40%', '65%'],
        data: statusOrder
          .map((item) => ({ name: item.label, value: statusValues[item.key] || 0 }))
          .filter((item) => item.value > 0),
      }],
    })
  }

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
  agentPie?.resize()
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
  agentPie?.dispose()
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
.muted {
  color: #909399;
}
.mt {
  margin-top: 16px;
}
.chart {
  height: 300px;
}
</style>
