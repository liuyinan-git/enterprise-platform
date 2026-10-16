<template>
  <el-card>
    <template #header>日志检索</template>

    <el-form :inline="true" class="search-bar">
      <el-form-item label="关键词">
        <el-input
          v-model="filters.keyword"
          placeholder="事件类型/类别/用户/主机"
          clearable
          style="width: 200px"
          @keyup.enter="search"
        />
      </el-form-item>
      <el-form-item label="设备类型">
        <el-select v-model="filters.device_type" placeholder="全部" clearable style="width: 140px">
          <el-option v-for="t in deviceTypes" :key="t" :label="t" :value="t" />
        </el-select>
      </el-form-item>
      <el-form-item label="日志级别">
        <el-select v-model="filters.severity" placeholder="全部" clearable style="width: 140px">
          <el-option v-for="s in severities" :key="s" :label="s" :value="s" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table
      v-loading="loading"
      :data="items"
      border
      stripe
      style="width: 100%"
      @row-click="openDetail"
    >
      <el-table-column prop="event_time" label="事件时间" min-width="170" />
      <el-table-column prop="device_type" label="设备类型" min-width="90" />
      <el-table-column prop="device_id" label="设备" min-width="100" show-overflow-tooltip />
      <el-table-column prop="event_category" label="类别" min-width="100" />
      <el-table-column prop="event_type" label="事件类型" min-width="130" show-overflow-tooltip />
      <el-table-column prop="process_name" label="进程/模块" min-width="130" show-overflow-tooltip />
      <el-table-column prop="severity" label="日志级别" width="90">
        <template #default="{ row }">
          <el-tag :type="severityType(row.severity)" size="small">{{ row.severity }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="source_ip" label="来源 IP" min-width="120" />
      <el-table-column prop="username" label="用户" min-width="90" show-overflow-tooltip />
      <el-table-column prop="security_label" label="安全标签" min-width="90" />
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

  <el-drawer v-model="detailVisible" title="日志详情" size="480px">
    <div v-loading="detailLoading">
      <el-descriptions v-if="detail" :column="1" border>
        <el-descriptions-item label="事件 ID">{{ detail.id }}</el-descriptions-item>
        <el-descriptions-item label="事件时间">{{ detail.event_time || '-' }}</el-descriptions-item>
        <el-descriptions-item label="设备类型">{{ detail.device_type }}</el-descriptions-item>
        <el-descriptions-item label="设备 ID">{{ detail.device_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="主机名">{{ detail.hostname || '-' }}</el-descriptions-item>
        <el-descriptions-item label="事件类别">{{ detail.event_category }}</el-descriptions-item>
        <el-descriptions-item label="事件类型">{{ detail.event_type }}</el-descriptions-item>
        <el-descriptions-item label="日志级别">{{ detail.severity }}</el-descriptions-item>
        <el-descriptions-item label="安全标签">{{ detail.security_label }}</el-descriptions-item>
        <el-descriptions-item label="来源 IP">{{ detail.source_ip || '-' }}</el-descriptions-item>
        <el-descriptions-item label="目标 IP">{{ detail.dest_ip || '-' }}</el-descriptions-item>
        <el-descriptions-item label="来源端口">{{ detail.source_port ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="目标端口">{{ detail.dest_port ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="用户名">{{ detail.username || '-' }}</el-descriptions-item>
        <el-descriptions-item label="进程">{{ detail.process_name || '-' }}</el-descriptions-item>
      </el-descriptions>

      <template v-if="detail?.raw">
        <h4 class="section-title">原始报文</h4>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="来源">{{ detail.raw.source_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="批次">{{ detail.raw.batch_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="格式">{{ detail.raw.format_type || '-' }}</el-descriptions-item>
          <el-descriptions-item label="接收时间">{{ detail.raw.received_at || '-' }}</el-descriptions-item>
        </el-descriptions>
        <pre class="raw-message">{{ detail.raw.raw_message || '-' }}</pre>
      </template>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { getLogDetail, listLogs, type LogDetail, type LogEventItem } from '@/modules/log/api'

const items = ref<LogEventItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<LogDetail | null>(null)

const deviceTypes = ['server', 'firewall', 'router', 'switch', 'pc', 'rpa', 'application', 'database', 'other']
const severities = ['debug', 'info', 'notice', 'warning', 'error', 'critical']

const filters = reactive({ keyword: '', device_type: '', severity: '' })

function severityType(sev: string) {
  if (sev === 'critical' || sev === 'error') return 'danger'
  if (sev === 'warning') return 'warning'
  return 'info'
}

async function load() {
  loading.value = true
  try {
    const result = await listLogs({
      page: page.value,
      page_size: pageSize.value,
      keyword: filters.keyword || undefined,
      device_type: filters.device_type || undefined,
      severity: filters.severity || undefined,
    })
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

async function openDetail(row: LogEventItem) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await getLogDetail(row.id)
  } finally {
    detailLoading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function reset() {
  filters.keyword = ''
  filters.device_type = ''
  filters.severity = ''
  search()
}

onMounted(load)
</script>

<style scoped>
.search-bar {
  margin-bottom: 8px;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
.section-title {
  margin: 16px 0 8px;
}
.raw-message {
  margin-top: 8px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
  line-height: 1.6;
}
</style>
