<template>
  <el-card>
    <template #header>告警管理</template>

    <el-form :inline="true" class="search-bar">
      <el-form-item label="发送状态">
        <el-select v-model="filters.status" placeholder="全部" clearable style="width: 140px">
          <el-option v-for="s in statuses" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="渠道">
        <el-select v-model="filters.channel" placeholder="全部" clearable style="width: 140px">
          <el-option v-for="c in channels" :key="c" :label="c" :value="c" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <el-table-column prop="alert_no" label="告警编号" min-width="200" show-overflow-tooltip />
      <el-table-column prop="security_event_id" label="事件 ID" width="90" />
      <el-table-column prop="channel" label="渠道" width="110" />
      <el-table-column label="接收人" min-width="120" show-overflow-tooltip>
        <template #default="{ row }">{{ row.receiver_key || '—' }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="attempt_count" label="尝试次数" width="90" />
      <el-table-column prop="sent_at" label="发送时间" min-width="170" />
      <el-table-column prop="created_at" label="创建时间" min-width="170" />
      <el-table-column label="错误信息" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">{{ row.last_error || '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="row.status !== 'sent'"
            size="small"
            type="primary"
            :loading="row._retrying"
            @click.stop="retry(row)"
          >
            重试
          </el-button>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
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

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listAlerts, retryAlert, type AlertItem } from '@/api/client'

const items = ref<(AlertItem & { _retrying?: boolean })[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

const statuses = [
  { value: 'pending', label: '待发送' },
  { value: 'sent', label: '已发送' },
  { value: 'failed', label: '失败' },
]
const channels = ['wecom']
const filters = reactive({ status: '', channel: '' })

function statusType(status: string) {
  if (status === 'sent') return 'success'
  if (status === 'failed') return 'danger'
  return 'warning'
}

function statusLabel(status: string) {
  return statuses.find((s) => s.value === status)?.label ?? status
}

async function load() {
  loading.value = true
  try {
    const result = await listAlerts({
      page: page.value,
      page_size: pageSize.value,
      status: filters.status || undefined,
      channel: filters.channel || undefined,
    })
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

async function retry(row: AlertItem & { _retrying?: boolean }) {
  row._retrying = true
  try {
    const updated = await retryAlert(row.alert_no)
    Object.assign(row, updated)
    ElMessage.success(updated.status === 'sent' ? '发送成功' : '发送失败，请查看错误信息')
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '重试失败')
  } finally {
    row._retrying = false
  }
}

function search() {
  page.value = 1
  load()
}

function reset() {
  filters.status = ''
  filters.channel = ''
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
.muted {
  color: #c0c4cc;
}
</style>
