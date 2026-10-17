<template>
  <el-drawer
    :model-value="modelValue"
    :title="`容器详情 · ${container?.name || ''}`"
    size="52%"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-loading="loading">
      <el-descriptions v-if="detail" :column="1" border>
        <el-descriptions-item label="容器 ID">{{ container?.full_id }}</el-descriptions-item>
        <el-descriptions-item label="镜像">{{ container?.image }}</el-descriptions-item>
        <el-descriptions-item label="项目">
          {{ container ? projectLabel(container) : '—' }}
          <span v-if="container?.matched_by"> · {{ matchedByLabel(container.matched_by) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          {{ stateLabel(container?.state || '') }}（{{ container?.status }}）
        </el-descriptions-item>
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
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  fetchContainer,
  type AgentContainerItem,
  type ContainerDetail,
  type ExecCommandInfo,
} from '@/modules/agent/api'
import { copyText } from '@/core/util/clipboard'
import { matchedByLabel, projectLabel, stateLabel } from '@/modules/agent/display'

const props = defineProps<{
  modelValue: boolean
  container: AgentContainerItem | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const loading = ref(false)
const detail = ref<ContainerDetail | null>(null)
const execInfo = ref<ExecCommandInfo | null>(null)

function errDetail(e: unknown): string | undefined {
  return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
}

async function load() {
  const target = props.container
  if (!target) return
  loading.value = true
  detail.value = null
  execInfo.value = null
  try {
    const result = await fetchContainer(target.container_id)
    detail.value = result.detail
    execInfo.value = result.exec_command
  } catch (e: unknown) {
    ElMessage.error(errDetail(e) || '详情加载失败')
  } finally {
    loading.value = false
  }
}

async function copy(text: string) {
  const okFlag = await copyText(text)
  if (okFlag) ElMessage.success('已复制')
  else ElMessage.warning('复制失败，请手动选中')
}

watch(
  () => [props.modelValue, props.container?.container_id] as const,
  ([visible]) => {
    if (visible) load()
  },
)
</script>

<style scoped>
.hint {
  color: #909399;
  font-size: 12px;
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
