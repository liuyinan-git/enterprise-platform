<template>
  <el-alert
    v-if="degraded"
    class="degraded"
    type="warning"
    :closable="false"
    show-icon
    title="Docker 服务不可达，容器实况暂不可用"
    :description="degradeError || '分类规则与接口监控不受影响。'"
  />

  <el-card>
    <template #header>
      <div class="card-header">
        <span>Docker 容器</span>
        <div class="header-actions">
          <span v-if="generatedAt" class="hint">
            实况更新于 {{ generatedAt.slice(11, 19) }} · 共 {{ total }} 个
          </span>
          <el-button size="small" @click="load()">刷新</el-button>
          <el-button size="small" :loading="discovering" @click="discover">重新发现</el-button>
          <el-button size="small" @click="openAudits">操作记录</el-button>
        </div>
      </div>
    </template>

    <el-form :inline="true" class="search-bar">
      <el-form-item label="关键词">
        <el-input v-model="filters.q" placeholder="容器名 / 镜像" clearable style="width: 180px" />
      </el-form-item>
      <el-form-item label="项目">
        <el-select v-model="filters.project_key" clearable placeholder="全部" style="width: 200px">
          <el-option label="未分类" value="unclassified" />
          <el-option label="规则冲突" value="conflict" />
          <el-option
            v-for="p in summary?.projects || []"
            :key="p.project_key"
            :label="`${p.project_name}（${p.total}）`"
            :value="p.project_key"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filters.state" clearable placeholder="全部" style="width: 130px">
          <el-option label="运行中" value="running" />
          <el-option label="已停止" value="exited" />
          <el-option label="已暂停" value="paused" />
          <el-option label="已创建" value="created" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-checkbox v-model="filters.include_protected">含受保护</el-checkbox>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="load()">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <el-table-column prop="name" label="容器名" min-width="160" show-overflow-tooltip />
      <el-table-column prop="container_id" label="短 ID" width="110" />
      <el-table-column prop="image" label="镜像" min-width="180" show-overflow-tooltip />
      <el-table-column label="项目" min-width="160">
        <template #default="{ row }">
          <el-tooltip
            v-if="row.conflict"
            placement="top"
            :content="`同时命中：${row.candidates.join('、')}｜${matchedByLabel(row.matched_by)}`"
          >
            <el-tag :type="projectTagType(row)" size="small">{{ projectLabel(row) }}</el-tag>
          </el-tooltip>
          <el-tag v-else :type="projectTagType(row)" size="small">{{ projectLabel(row) }}</el-tag>
          <div class="sub">{{ matchedByLabel(row.matched_by) }}</div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="stateTagType(row.state)" size="small">{{ stateLabel(row.state) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="端口" min-width="150">
        <template #default="{ row }">
          <div v-for="p in row.ports" :key="p" class="sub">{{ p }}</div>
          <span v-if="!row.ports.length">—</span>
        </template>
      </el-table-column>
      <el-table-column label="保护" width="80">
        <template #default="{ row }">
          <el-tooltip v-if="row.protected" placement="top" :content="row.protected_reason || '受保护'">
            <el-tag type="warning" size="small">受保护</el-tag>
          </el-tooltip>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row }">
          <ContainerActions
            :container="row"
            :operable="canControl && isOperable(row)"
            @log="openLog"
            @action="runAction"
          />
          <el-button size="small" @click="openDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <ContainerLogDialog v-model:visible="logVisible" :container-id="logTarget?.container_id || ''" :container-name="logTarget?.name" />

  <el-drawer v-model="detailVisible" :title="`容器详情 · ${detailTarget?.name || ''}`" size="52%">
    <div v-loading="detailLoading">
      <el-descriptions v-if="detail" :column="1" border>
        <el-descriptions-item label="容器 ID">{{ detailTarget?.full_id }}</el-descriptions-item>
        <el-descriptions-item label="镜像">{{ detailTarget?.image }}</el-descriptions-item>
        <el-descriptions-item label="项目">
          {{ projectLabel(detailTarget!) }}<span v-if="detailTarget?.matched_by"> · {{ matchedByLabel(detailTarget.matched_by) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="状态">{{ stateLabel(detailTarget?.state || '') }}（{{ detailTarget?.status }}）</el-descriptions-item>
        <el-descriptions-item label="启动时间">{{ detail.started_at || '—' }}</el-descriptions-item>
        <el-descriptions-item label="结束时间">{{ detail.finished_at || '—' }}</el-descriptions-item>
        <el-descriptions-item label="退出码">{{ detail.exit_code ?? '—' }}</el-descriptions-item>
        <el-descriptions-item label="重启次数">{{ detail.restart_count ?? '—' }}</el-descriptions-item>
        <el-descriptions-item label="重启策略">{{ detail.restart_policy || '—' }}</el-descriptions-item>
        <el-descriptions-item label="健康检查">{{ detail.health || '—' }}</el-descriptions-item>
        <el-descriptions-item label="网络">{{ detail.networks.join('、') || '—' }}</el-descriptions-item>
        <el-descriptions-item label="挂载数">{{ detail.mount_count }}</el-descriptions-item>
        <el-descriptions-item label="入口命令">
          {{ [detail.command, ...(detail.args || [])].filter(Boolean).join(' ') || '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="可操作性">
          <el-tag v-if="detail.refusal_reason" type="warning" size="small">{{ detail.refusal_reason }}</el-tag>
          <el-tag v-else type="success" size="small">可执行启停</el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <el-card v-if="execInfo" class="mt" shadow="never">
        <template #header>宿主机命令（平台不提供 Web 终端）</template>
        <div class="exec-row">
          <code class="exec-code">{{ execInfo.command }}</code>
          <el-button size="small" @click="copy(execInfo.command)">复制</el-button>
        </div>
        <div class="exec-row">
          <code class="exec-code">{{ execInfo.fallback_command }}</code>
          <el-button size="small" @click="copy(execInfo.fallback_command)">复制</el-button>
        </div>
        <div class="hint">{{ execInfo.host_note }}</div>
      </el-card>
    </div>
  </el-drawer>

  <el-drawer v-model="auditVisible" title="容器操作记录" size="62%" @open="loadAudits">
    <el-table v-loading="auditLoading" :data="auditItems" border stripe style="width: 100%">
      <el-table-column prop="created_at" label="时间" width="180" />
      <el-table-column prop="container_name" label="容器" min-width="150" show-overflow-tooltip />
      <el-table-column prop="project_key" label="项目" width="120" />
      <el-table-column label="动作" width="90">
        <template #default="{ row }">{{ actionLabel(row.action) }}</template>
      </el-table-column>
      <el-table-column label="结果" width="100">
        <template #default="{ row }">
          <el-tag :type="auditResultType(row.result)" size="small">{{ auditResultLabel(row.result) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="operator" label="操作人" width="120" />
      <el-table-column label="说明" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">{{ row.detail ? JSON.stringify(row.detail) : '—' }}</template>
      </el-table-column>
    </el-table>
    <el-pagination
      class="pager"
      layout="total, prev, pager, next"
      :total="auditTotal"
      v-model:current-page="auditPage"
      v-model:page-size="auditPageSize"
      @current-change="loadAudits"
    />
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  discoverContainers,
  fetchContainer,
  listContainerAudits,
  listContainers,
  runContainerAction,
  type AgentContainerItem,
  type ContainerAction,
  type ContainerAuditItem,
  type ContainerDetail,
  type ExecCommandInfo,
  type ProjectSummary,
} from '@/modules/agent/api'
import { useAuthStore } from '@/core/auth/store'
import { copyText } from '@/core/util/clipboard'
import {
  actionLabel,
  auditResultLabel,
  auditResultType,
  isOperable,
  matchedByLabel,
  projectLabel,
  projectTagType,
  stateLabel,
  stateTagType,
} from '@/modules/agent/display'
import ContainerActions from '@/modules/agent/components/ContainerActions.vue'
import ContainerLogDialog from '@/modules/agent/components/ContainerLogDialog.vue'

const auth = useAuthStore()
/** 前端按钮门禁；服务端会独立再校验一次，前端隐藏只是 UX */
const canControl = computed(() => auth.canAccess('agent:container'))

const items = ref<AgentContainerItem[]>([])
const summary = ref<ProjectSummary | null>(null)
const total = ref(0)
const loading = ref(false)
const discovering = ref(false)
const degraded = ref(false)
const degradeError = ref<string | null>(null)
const generatedAt = ref('')

const logVisible = ref(false)
const logTarget = ref<AgentContainerItem | null>(null)

const detailVisible = ref(false)
const detailLoading = ref(false)
const detailTarget = ref<AgentContainerItem | null>(null)
const detail = ref<ContainerDetail | null>(null)
const execInfo = ref<ExecCommandInfo | null>(null)

const auditVisible = ref(false)
const auditLoading = ref(false)
const auditItems = ref<ContainerAuditItem[]>([])
const auditTotal = ref(0)
const auditPage = ref(1)
const auditPageSize = ref(20)

const filters = reactive({
  q: '',
  project_key: '',
  state: '',
  include_protected: true,
})

function errDetail(e: unknown): string | undefined {
  return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
}

async function load() {
  loading.value = true
  try {
    const result = await listContainers({
      q: filters.q || undefined,
      project_key: filters.project_key || undefined,
      state: filters.state || undefined,
      include_protected: filters.include_protected,
    })
    items.value = result.items
    total.value = result.total
    summary.value = result.summary
    degraded.value = result.degraded
    degradeError.value = result.error
    generatedAt.value = result.generated_at
  } catch (e: unknown) {
    ElMessage.error(errDetail(e) || '加载失败')
  } finally {
    loading.value = false
  }
}

async function discover() {
  discovering.value = true
  try {
    const result = await discoverContainers()
    ElMessage.success(
      `发现 ${result.discovered} 个容器：已分类 ${result.classified}，未分类 ${result.unclassified}，冲突 ${result.conflict}`,
    )
    await load()
  } catch (e: unknown) {
    ElMessage.error(errDetail(e) || '发现失败')
  } finally {
    discovering.value = false
  }
}

function reset() {
  filters.q = ''
  filters.project_key = ''
  filters.state = ''
  filters.include_protected = true
  load()
}

function openLog(container: AgentContainerItem) {
  logTarget.value = container
  logVisible.value = true
}

async function openDetail(container: AgentContainerItem) {
  detailTarget.value = container
  detail.value = null
  execInfo.value = null
  detailVisible.value = true
  detailLoading.value = true
  try {
    const result = await fetchContainer(container.container_id)
    detail.value = result.detail
    execInfo.value = result.exec_command
  } catch (e: unknown) {
    ElMessage.error(errDetail(e) || '详情加载失败')
  } finally {
    detailLoading.value = false
  }
}

async function copy(text: string) {
  const okFlag = await copyText(text)
  if (okFlag) ElMessage.success('已复制')
  else ElMessage.warning('复制失败，请手动选中')
}

async function runAction(container: AgentContainerItem, action: ContainerAction) {
  const verb = actionLabel(action)
  try {
    await ElMessageBox.confirm(
      `即将【${verb}】容器「${container.name}」(${container.image})，所属项目「${projectLabel(container)}」。该操作会中断其服务，确认继续？`,
      '危险操作',
      { type: 'warning', confirmButtonText: verb, cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await runContainerAction(container.container_id, action)
    ElMessage.success(`已${verb}`)
    load()
  } catch (e: unknown) {
    ElMessage.error(errDetail(e) || `${verb}失败`)
  }
}

async function loadAudits() {
  auditLoading.value = true
  try {
    const result = await listContainerAudits({ page: auditPage.value, page_size: auditPageSize.value })
    auditItems.value = result.items
    auditTotal.value = result.total
  } catch (e: unknown) {
    ElMessage.error(errDetail(e) || '加载操作记录失败')
  } finally {
    auditLoading.value = false
  }
}

function openAudits() {
  auditVisible.value = true
}

onMounted(load)
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
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.hint {
  color: #909399;
  font-size: 12px;
}
.search-bar {
  margin-bottom: 8px;
}
.sub {
  color: #909399;
  font-size: 12px;
  line-height: 1.5;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
.mt {
  margin-top: 16px;
}
.exec-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.exec-code {
  flex: 1;
  padding: 6px 8px;
  overflow-x: auto;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 12px;
  white-space: nowrap;
}
</style>
