<template>
  <el-card v-loading="loading">
    <template #header>
      <div class="card-header">
        <span>系统设置（只读）</span>
        <span v-if="data" class="hint">读取于 {{ data.generated_at.slice(11, 19) }}</span>
      </div>
    </template>

    <el-empty v-if="!data && !loading" description="暂无数据" :image-size="80" />

    <template v-if="data">
      <h4 class="section">调度配置</h4>
      <div class="hint">
        由 {{ data.schedule.source }} 提供。{{ data.schedule.note }}
      </div>
      <el-table :data="data.schedule.items" border stripe size="small" style="width: 100%">
        <el-table-column prop="name" label="任务名" min-width="180" />
        <el-table-column prop="task" label="Celery 任务" min-width="200" />
        <el-table-column label="间隔" width="140">
          <template #default="{ row }">
            {{ row.interval_seconds == null ? '—' : `${row.interval_seconds} 秒` }}
          </template>
        </el-table-column>
      </el-table>

      <h4 class="section">调度运行状态</h4>
      <div class="hint">
        配置表说明「应何时跑」，这里说明「是否真的在跑」。按平台自身 compose 服务
        （{{ data.docker.protected_project }}）检测；本地直接用 celery 命令启动时显示「未检测到」属正常。
      </div>
      <el-table :data="runtimeRows" border stripe size="small" style="width: 100%">
        <el-table-column prop="label" label="服务" width="190" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.tag" size="small">{{ row.text }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="detail" label="说明" min-width="320" show-overflow-tooltip />
      </el-table>
      <div class="hint">
        scheduler 不在跑时，上面的调度配置不会触发任何任务；worker 不在跑时，任务即使被触发也无人执行。
        接口自动探测、监控历史清理、智能体离线告警都依赖这两者。
      </div>

      <h4 class="section">超时配置</h4>
      <el-table :data="timeoutRows" border stripe size="small" style="width: 100%">
        <el-table-column prop="label" label="项目" min-width="200" />
        <el-table-column prop="value" label="当前值" width="120" />
        <el-table-column prop="env" label="环境变量" min-width="280" />
      </el-table>

      <h4 class="section">存储与保留</h4>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="历史保留天数">
          {{ data.storage.history_retention_days }} 天（AGENT_HISTORY_RETENTION_DAYS）
        </el-descriptions-item>
        <el-descriptions-item label="历史记录总数">{{ data.storage.history_total }}</el-descriptions-item>
        <el-descriptions-item label="最早一条历史">{{ data.storage.history_oldest_at || '—' }}</el-descriptions-item>
        <el-descriptions-item label="分类规则数">{{ data.storage.rule_count }}</el-descriptions-item>
        <el-descriptions-item label="端点登记数">{{ data.storage.endpoint_count }}</el-descriptions-item>
        <el-descriptions-item label="日志时间戳">
          {{ data.docker.log_timestamps ? '开启（服务端转本地时间）' : '关闭' }}
        </el-descriptions-item>
        <el-descriptions-item label="日志行数上限">
          默认 {{ data.docker.log_tail_default }} / 最大 {{ data.docker.log_tail_max }}
        </el-descriptions-item>
        <el-descriptions-item label="探测响应摘要上限">{{ data.probe.max_excerpt_chars }} 字符</el-descriptions-item>
      </el-descriptions>

      <h4 class="section">连接状态</h4>
      <el-table :data="connectionRows" border stripe size="small" style="width: 100%">
        <el-table-column prop="label" label="目标" min-width="180" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.ok ? 'success' : 'danger'" size="small">{{ row.ok ? '正常' : '不可达' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="100">
          <template #default="{ row }">{{ row.latency_ms }}ms</template>
        </el-table-column>
        <el-table-column label="说明" min-width="300" show-overflow-tooltip>
          <template #default="{ row }">{{ row.error || row.detail || '—' }}</template>
        </el-table-column>
      </el-table>

      <h4 class="section">权限</h4>
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="网关认证">
          <el-tag :type="data.auth.gateway_auth_enabled ? 'success' : 'warning'" size="small">
            {{ data.auth.gateway_auth_enabled ? '已开启' : '未开启（匿名 admin）' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="当前用户">
          {{ currentUser.username }}<span class="muted">（{{ currentUser.user_id }}）</span>
        </el-descriptions-item>
        <el-descriptions-item label="当前角色">
          <template v-if="currentUser.roles.length">
            <el-tag v-for="role in currentUser.roles" :key="role" class="role-tag" size="small">{{ role }}</el-tag>
          </template>
          <span v-else class="muted">无角色</span>
        </el-descriptions-item>
        <el-descriptions-item label="当前权限">
          <template v-if="currentUser.permissions.length">
            <el-tag v-for="perm in currentUser.permissions" :key="perm" class="role-tag" size="small" type="info">
              {{ perm }}
            </el-tag>
          </template>
          <span v-else class="muted">无权限</span>
        </el-descriptions-item>
        <el-descriptions-item label="读接口">
          <el-tag :type="can(data.auth.permissions.read) ? 'success' : 'info'" size="small">
            {{ can(data.auth.permissions.read) ? '允许' : '拒绝' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="台账写">
          <el-tag :type="can(data.auth.permissions.ledger_write) ? 'success' : 'info'" size="small">
            {{ can(data.auth.permissions.ledger_write) ? '允许' : '拒绝' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="容器启停">
          <el-tag :type="can(data.auth.permissions.container_action) ? 'success' : 'info'" size="small">
            {{ can(data.auth.permissions.container_action) ? '允许' : '拒绝' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
      <div class="hint">
        以上按本次请求实际解析出的角色与权限动态计算（admin 恒放行，{{ data.auth.gateway_auth_enabled ? '来源为 APISIX 注入的 x-user-* 请求头' : '当前为匿名 admin，所有能力均放行' }}）。<br />
        权限策略：读接口 {{ data.auth.permissions.read.join(' / ') }}；台账写 {{ data.auth.permissions.ledger_write.join(' / ') }}；
        容器启停 {{ data.auth.permissions.container_action.join(' / ') }}——容器启停刻意与台账编辑分开授权，
        前者会真的中断在跑的服务，影响面差一个量级。
      </div>

      <h4 class="section">Docker 代理与保护</h4>
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="代理地址">{{ data.docker.proxy_url_masked }}（主机名已隐去）</el-descriptions-item>
        <el-descriptions-item label="受保护项目">{{ data.docker.protected_project }}（该项目下的容器一律禁启停）</el-descriptions-item>
        <el-descriptions-item label="TLS 校验">{{ data.probe.verify_tls ? '开启' : '关闭（AGENT_PROBE_VERIFY_TLS=false）' }}</el-descriptions-item>
      </el-descriptions>
    </template>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchSystemStatus, type SystemStatusData } from '@/modules/agent/api'

const data = ref<SystemStatusData | null>(null)
const loading = ref(false)

// 后端按本次请求动态解析，网关认证关闭时返回 anonymous / [admin]
const currentUser = computed(
  () =>
    data.value?.auth.current_user ?? {
      user_id: '—',
      username: '—',
      roles: [] as string[],
      permissions: [] as string[],
    },
)

function can(allowed: string[]): boolean {
  if (currentUser.value.roles.includes('admin')) return true
  return allowed.some((perm) => currentUser.value.permissions.includes(perm))
}

type TagType = 'success' | 'warning' | 'info' | 'danger'

const RUNTIME_LABELS: Record<string, string> = {
  worker: 'Worker（任务执行）',
  scheduler: 'Scheduler（beat 定时）',
}

const runtimeRows = computed(() => {
  const source = data.value?.runtime
  return Object.keys(RUNTIME_LABELS).map((key) => {
    const rt = source?.[key as 'worker' | 'scheduler']
    let text = '未知'
    let tag: TagType = 'warning'
    if (rt?.ok) {
      text = '运行中'
      tag = 'success'
    } else if (rt?.state === 'not_found') {
      text = '未检测到'
      tag = 'info'
    } else if (rt?.state === 'unknown') {
      text = '无法检测'
      tag = 'warning'
    } else if (rt) {
      text = '未运行'
      tag = 'danger'
    }
    const detail =
      rt?.error ||
      [rt?.status, rt?.container_id ? `容器 ${rt.container_id}` : ''].filter(Boolean).join(' · ') ||
      '—'
    return { label: RUNTIME_LABELS[key], text, tag, detail }
  })
})

const TIMEOUT_LABELS: Record<string, string> = {
  docker_request_seconds: 'Docker 读请求',
  docker_action_seconds: 'Docker 写请求（启停）',
  docker_stop_grace_seconds: '容器停止宽限期',
  probe_default_seconds: '端点探测默认超时',
  probe_max_seconds: '端点探测最大超时',
  agent_offline_grace_seconds: '智能体心跳离线宽限',
}

const timeoutRows = computed(() => {
  const source = data.value?.timeouts || {}
  return Object.keys(source).map((key) => ({
    label: TIMEOUT_LABELS[key] || key,
    value: `${String(source[key].value)} 秒`,
    env: source[key].env || '',
  }))
})

const connectionRows = computed(() => {
  const d = data.value
  if (!d) return []
  return [
    { label: 'Docker 代理', ...d.docker },
    { label: 'MySQL', ...d.connections.mysql },
    { label: 'Redis', ...d.connections.redis },
  ]
})

function errDetail(e: unknown): string | undefined {
  return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
}

async function load() {
  loading.value = true
  try {
    data.value = await fetchSystemStatus()
  } catch (e: unknown) {
    ElMessage.error(errDetail(e) || '加载失败')
  } finally {
    loading.value = false
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
.section {
  margin: 20px 0 8px;
  font-size: 14px;
}
.hint {
  margin-bottom: 8px;
  color: #909399;
  font-size: 12px;
  line-height: 1.6;
}
.muted {
  color: #909399;
}
.role-tag {
  margin-right: 6px;
}
</style>
