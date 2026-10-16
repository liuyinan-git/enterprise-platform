<template>
  <el-card>
    <template #header>安全事件中心</template>

    <el-form :inline="true" class="search-bar">
      <el-form-item label="状态">
        <el-select v-model="filters.status" placeholder="全部" clearable style="width: 140px">
          <el-option v-for="s in statuses" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="风险等级">
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
      <el-table-column prop="event_no" label="事件编号" min-width="200" show-overflow-tooltip />
      <el-table-column prop="event_title" label="事件名称" min-width="160" show-overflow-tooltip />
      <el-table-column prop="severity" label="风险等级" width="90">
        <template #default="{ row }">
          <el-tag :type="severityType(row.severity)" size="small">{{ row.severity }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="source_ip" label="来源 IP" min-width="120" />
      <el-table-column prop="device_id" label="设备" min-width="100" show-overflow-tooltip />
      <el-table-column prop="occurrence_count" label="次数" width="80" />
      <el-table-column prop="last_seen_at" label="最近发生" min-width="170" />
      <el-table-column prop="assigned_to" label="分派" min-width="100" show-overflow-tooltip />
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

  <el-drawer v-model="detailVisible" title="事件详情" size="640px">
    <div v-loading="detailLoading">
      <template v-if="detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="事件编号">{{ detail.event_no }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusLabel(detail.status) }}</el-descriptions-item>
          <el-descriptions-item label="事件名称" :span="2">{{ detail.event_title }}</el-descriptions-item>
          <el-descriptions-item label="风险等级">{{ detail.severity }}</el-descriptions-item>
          <el-descriptions-item label="累计次数">{{ detail.occurrence_count }}</el-descriptions-item>
          <el-descriptions-item label="来源 IP">{{ detail.source_ip || '-' }}</el-descriptions-item>
          <el-descriptions-item label="设备">{{ detail.device_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="首次发生">{{ detail.first_seen_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="最近发生">{{ detail.last_seen_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="分派给">{{ detail.assigned_to || '-' }}</el-descriptions-item>
          <el-descriptions-item label="关闭时间">{{ detail.resolved_at || '-' }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.resolution_note" label="处理备注" :span="2">
            {{ detail.resolution_note }}
          </el-descriptions-item>
        </el-descriptions>

        <el-form :inline="true" class="action-bar">
          <el-form-item label="流转状态">
            <el-select v-model="action.status" style="width: 130px">
              <el-option v-for="s in statuses" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="分派给">
            <el-input v-model="action.assigned_to" placeholder="处理人" style="width: 140px" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="saving" @click="saveAction">保存</el-button>
          </el-form-item>
        </el-form>

        <div class="ai-section">
          <div class="ai-header">
            <h4 class="section-title">AI 研判</h4>
            <el-button
              v-if="!detail.ai_analysis"
              size="small"
              type="primary"
              :loading="aiLoading"
              @click="runAi"
            >
              AI 研判
            </el-button>
          </div>
          <el-alert
            v-if="detail.ai_analysis?.status === 'failed'"
            type="error"
            :title="'AI 研判失败：' + detail.ai_analysis.error"
            :closable="false"
          />
          <template v-else-if="detail.ai_analysis">
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="摘要">{{ detail.ai_analysis.summary }}</el-descriptions-item>
              <el-descriptions-item label="风险研判">{{ riskLabel(detail.ai_analysis.risk_assessment) }}</el-descriptions-item>
              <el-descriptions-item label="置信度">{{ detail.ai_analysis.confidence }}</el-descriptions-item>
              <el-descriptions-item label="需人工复核">{{ detail.ai_analysis.needs_human_review ? '是' : '否' }}</el-descriptions-item>
            </el-descriptions>
            <template v-if="detail.ai_analysis.evidence?.length">
              <div class="ai-sub">已确认事实</div>
              <ul class="ai-list">
                <li v-for="(e, i) in detail.ai_analysis.evidence" :key="i">{{ e }}</li>
              </ul>
            </template>
            <template v-if="detail.ai_analysis.limitations?.length">
              <div class="ai-sub">局限与未知</div>
              <ul class="ai-list">
                <li v-for="(e, i) in detail.ai_analysis.limitations" :key="i">{{ e }}</li>
              </ul>
            </template>
            <template v-if="detail.ai_analysis.recommendations?.length">
              <div class="ai-sub">核查建议</div>
              <ul class="ai-list">
                <li v-for="(e, i) in detail.ai_analysis.recommendations" :key="i">{{ e }}</li>
              </ul>
            </template>
            <div class="ai-meta">{{ detail.ai_analysis.model }} · {{ detail.ai_analysis.analyzed_at }}</div>
          </template>
        </div>

        <h4 class="section-title">关联证据日志（{{ detail.evidence.length }}）</h4>
        <el-table :data="detail.evidence" border size="small" max-height="240">
          <el-table-column prop="event_time" label="时间" min-width="160" />
          <el-table-column prop="event_type" label="事件类型" min-width="120" show-overflow-tooltip />
          <el-table-column prop="severity" label="日志级别" width="90" />
          <el-table-column prop="source_ip" label="来源 IP" min-width="110" />
          <el-table-column prop="username" label="用户" min-width="90" show-overflow-tooltip />
        </el-table>

        <h4 class="section-title">告警记录（{{ detail.alerts.length }}）</h4>
        <el-table :data="detail.alerts" border size="small">
          <el-table-column prop="alert_no" label="告警编号" min-width="200" show-overflow-tooltip />
          <el-table-column prop="channel" label="渠道" width="110" />
          <el-table-column prop="status" label="状态" width="90" />
          <el-table-column prop="attempt_count" label="尝试" width="70" />
          <el-table-column prop="sent_at" label="发送时间" min-width="160" />
        </el-table>
      </template>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getEvent,
  listEvents,
  patchEvent,
  triggerAiAnalysis,
  type EventDetail,
  type SecurityEventItem,
} from '@/modules/log/api'

const items = ref<SecurityEventItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<EventDetail | null>(null)
const saving = ref(false)
const aiLoading = ref(false)
const action = reactive({ status: '', assigned_to: '' })

const statuses = [
  { value: 'open', label: '待处理' },
  { value: 'confirmed', label: '已确认' },
  { value: 'closed', label: '已关闭' },
]
const severities = ['critical', 'high', 'medium', 'low']

const filters = reactive({ status: '', severity: '' })

function severityType(sev: string) {
  if (sev === 'critical' || sev === 'high') return 'danger'
  if (sev === 'medium') return 'warning'
  return 'info'
}

function statusType(status: string) {
  if (status === 'open') return 'danger'
  if (status === 'confirmed') return 'warning'
  return 'success'
}

function statusLabel(status: string) {
  return statuses.find((s) => s.value === status)?.label ?? status
}

async function load() {
  loading.value = true
  try {
    const result = await listEvents({
      page: page.value,
      page_size: pageSize.value,
      status: filters.status || undefined,
      severity: filters.severity || undefined,
    })
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

async function openDetail(row: SecurityEventItem) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  action.status = row.status
  action.assigned_to = row.assigned_to ?? ''
  try {
    detail.value = await getEvent(row.event_no)
    action.status = detail.value.status
    action.assigned_to = detail.value.assigned_to ?? ''
  } finally {
    detailLoading.value = false
  }
}

async function saveAction() {
  if (!detail.value) return
  saving.value = true
  try {
    const updated = await patchEvent(detail.value.event_no, {
      status: action.status || undefined,
      assigned_to: action.assigned_to || undefined,
    })
    detail.value = { ...detail.value, ...updated }
    ElMessage.success('已保存')
    load()
  } finally {
    saving.value = false
  }
}

function riskLabel(r?: string) {
  if (r === 'malicious') return '恶意'
  if (r === 'suspicious') return '可疑'
  if (r === 'normal') return '正常'
  return r || '-'
}

async function runAi() {
  if (!detail.value) return
  aiLoading.value = true
  try {
    const result = await triggerAiAnalysis(detail.value.event_no)
    detail.value.ai_analysis = result.ai_analysis
    ElMessage.success('AI 研判完成')
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || 'AI 研判失败')
  } finally {
    aiLoading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function reset() {
  filters.status = ''
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
.action-bar {
  margin-top: 16px;
}
.ai-section {
  margin-top: 16px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
}
.ai-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.ai-sub {
  margin-top: 12px;
  font-weight: 600;
  color: #303133;
}
.ai-list {
  margin: 6px 0 0;
  padding-left: 20px;
}
.ai-meta {
  margin-top: 8px;
  color: #909399;
  font-size: 12px;
}
</style>
