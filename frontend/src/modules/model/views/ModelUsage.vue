<template>
  <div>
    <el-card v-loading="allLoading" class="mb">
      <div class="stat-value">{{ totalCalls }}</div>
      <div class="stat-label">总调用次数（所有模型累计）</div>
    </el-card>

    <template v-if="hasData">
      <el-row :gutter="16">
        <el-col :xs="24" :lg="12">
          <el-card>
            <template #header>近 14 日每日调用量趋势</template>
            <div ref="trendRef" class="chart"></div>
          </el-card>
        </el-col>
        <el-col :xs="24" :lg="12">
          <el-card>
            <template #header>模型调用量排行</template>
            <div ref="rankRef" class="chart"></div>
          </el-card>
        </el-col>
      </el-row>

      <el-card class="mt">
        <template #header>
          <span>用量明细</span>
        </template>

        <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
          <el-table-column prop="model_code" label="模型编码" min-width="160" show-overflow-tooltip />
          <el-table-column prop="call_count" label="调用次数" width="120" />
          <el-table-column prop="input_tokens" label="输入 tokens" width="130" />
          <el-table-column prop="output_tokens" label="输出 tokens" width="130" />
          <el-table-column prop="recorded_day" label="日期" width="120" />
        </el-table>

        <el-pagination
          class="pager"
          layout="total, sizes, prev, pager, next"
          :total="total"
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          @current-change="load"
          @size-change="load"
        />
      </el-card>
    </template>

    <el-card v-else-if="!allLoading" class="mt">
      <el-empty description="暂无用量数据（服务可能不支持 /metrics 采集，或周期任务未运行）" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { listUsages, type UsageItem } from '@/modules/model/api'

const items = ref<UsageItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

// 全量数据（汇总卡片 + 图表聚合用；后端 page_size 上限 200，逐页拉取）
const allUsages = ref<UsageItem[]>([])
const allLoading = ref(false)
const totalCalls = computed(() => allUsages.value.reduce((sum, u) => sum + u.call_count, 0))
const hasData = computed(() => allUsages.value.length > 0)

const trendRef = ref<HTMLDivElement | null>(null)
const rankRef = ref<HTMLDivElement | null>(null)
let trendChart: echarts.ECharts | null = null
let rankChart: echarts.ECharts | null = null

async function load() {
  loading.value = true
  try {
    const result = await listUsages({ page: page.value, page_size: pageSize.value })
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

async function loadAll() {
  allLoading.value = true
  try {
    const collected: UsageItem[] = []
    let pageNum = 1
    let totalCount = 0
    while (pageNum <= 10) {
      const result = await listUsages({ page: pageNum, page_size: 200 })
      totalCount = result.total
      collected.push(...result.items)
      if (collected.length >= totalCount || result.items.length === 0) break
      pageNum += 1
    }
    allUsages.value = collected
    if (hasData.value) renderCharts()
  } finally {
    allLoading.value = false
  }
}

function lastNDays(n: number): string[] {
  const days: string[] = []
  const today = new Date()
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(today)
    d.setDate(d.getDate() - i)
    const month = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    days.push(`${d.getFullYear()}-${month}-${day}`)
  }
  return days
}

async function renderCharts() {
  await nextTick()
  renderTrend()
  renderRank()
}

function renderTrend() {
  if (!trendRef.value) return
  const days = lastNDays(14)
  const byDay = new Map<string, number>()
  for (const u of allUsages.value) {
    byDay.set(u.recorded_day, (byDay.get(u.recorded_day) || 0) + u.call_count)
  }
  if (!trendChart) trendChart = echarts.init(trendRef.value)
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: days },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      { name: '调用次数', type: 'line', smooth: true, areaStyle: {}, data: days.map((d) => byDay.get(d) || 0) },
    ],
  })
}

function renderRank() {
  if (!rankRef.value) return
  const byModel = new Map<string, number>()
  for (const u of allUsages.value) {
    const key = u.model_code || '未知模型'
    byModel.set(key, (byModel.get(key) || 0) + u.call_count)
  }
  const entries = [...byModel.entries()].sort((a, b) => a[1] - b[1])
  if (!rankChart) rankChart = echarts.init(rankRef.value)
  rankChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 20, right: 30, top: 30, bottom: 30, containLabel: true },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: entries.map((e) => e[0]) },
    series: [{ name: '调用次数', type: 'bar', data: entries.map((e) => e[1]) }],
  })
}

function onResize() {
  trendChart?.resize()
  rankChart?.resize()
}

onMounted(() => {
  load()
  loadAll()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  trendChart?.dispose()
  trendChart = null
  rankChart?.dispose()
  rankChart = null
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
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
