<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>规则管理</span>
        <el-button type="primary" @click="openCreate">新增规则</el-button>
      </div>
    </template>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="规则列表" name="rules">
        <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <el-table-column prop="rule_code" label="规则编码" min-width="180" show-overflow-tooltip />
      <el-table-column prop="rule_name" label="规则名称" min-width="160" show-overflow-tooltip />
      <el-table-column prop="rule_type" label="类型" width="100" />
      <el-table-column prop="severity" label="风险等级" width="90">
        <template #default="{ row }">
          <el-tag :type="severityType(row.severity)" size="small">{{ row.severity }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="启用" width="80">
        <template #default="{ row }">
          <el-switch
            :model-value="row.enabled"
            @change="(v: boolean) => toggle(row, v)"
          />
        </template>
      </el-table-column>
      <el-table-column prop="cooldown_seconds" label="冷却(秒)" width="90" />
      <el-table-column label="接收人" min-width="110" show-overflow-tooltip>
        <template #default="{ row }">{{ row.touser || '—' }}</template>
      </el-table-column>
      <el-table-column label="规则配置" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">{{ configText(row.rule_config) }}</template>
      </el-table-column>
      <el-table-column prop="version" label="版本" width="70" />
      <el-table-column prop="updated_at" label="更新时间" min-width="170" />
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="规则建议" name="suggestions">
        <el-table v-loading="suggestionLoading" :data="suggestions" border stripe style="width: 100%">
          <el-table-column prop="rule_name" label="建议规则" min-width="180" show-overflow-tooltip />
          <el-table-column prop="event_type" label="事件类型" min-width="120" show-overflow-tooltip />
          <el-table-column prop="severity" label="风险等级" width="90">
            <template #default="{ row }">
              <el-tag :type="severityType(row.severity)" size="small">{{ row.severity }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="阈值/窗口" width="120">
            <template #default="{ row }">{{ row.threshold }} 次 / {{ row.window_seconds }}s</template>
          </el-table-column>
          <el-table-column prop="reason" label="依据" min-width="220" show-overflow-tooltip />
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="suggestionStatusType(row.status)" size="small">{{ suggestionStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.status === 'pending'" size="small" type="primary" @click="accept(row)">采纳</el-button>
              <el-button v-if="row.status === 'pending'" size="small" @click="ignore(row)">忽略</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!suggestionLoading && !suggestions.length" description="暂无建议" />
      </el-tab-pane>
    </el-tabs>
  </el-card>

  <el-dialog v-model="dialogVisible" :title="editing ? '编辑规则' : '新增规则'" width="520px">
    <el-form :model="form" label-width="100px">
      <el-form-item label="规则编码" required>
        <el-input v-model="form.rule_code" :disabled="!!editing" placeholder="如 SSH_LOGIN_FAILURE_BURST" />
      </el-form-item>
      <el-form-item label="规则名称" required>
        <el-input v-model="form.rule_name" placeholder="如 SSH登录失败次数异常" />
      </el-form-item>
      <el-form-item label="风险等级">
        <el-select v-model="form.severity" style="width: 100%">
          <el-option v-for="s in severities" :key="s" :label="s" :value="s" />
        </el-select>
      </el-form-item>
      <el-form-item label="事件类型">
        <el-input v-model="form.event_type" placeholder="如 login_failure" />
      </el-form-item>
      <el-form-item label="时间窗口(秒)">
        <el-input-number v-model="form.window_seconds" :min="1" style="width: 100%" />
      </el-form-item>
      <el-form-item label="阈值">
        <el-input-number v-model="form.threshold" :min="1" style="width: 100%" />
      </el-form-item>
      <el-form-item label="分组字段">
        <el-input v-model="form.group_by" placeholder="逗号分隔，如 source_ip,device_id,username" />
      </el-form-item>
      <el-form-item label="冷却(秒)">
        <el-input-number v-model="form.cooldown_seconds" :min="0" style="width: 100%" />
      </el-form-item>
      <el-form-item label="接收人">
        <el-input v-model="form.touser" placeholder="UserID，留空则用设备/全局；多人用 | 分隔" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  acceptRuleSuggestion,
  createRule,
  ignoreRuleSuggestion,
  listRules,
  listRuleSuggestions,
  updateRule,
  type RuleItem,
  type RuleSuggestionItem,
} from '@/modules/log/api'

const items = ref<RuleItem[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref<RuleItem | null>(null)

const activeTab = ref('rules')
const suggestions = ref<RuleSuggestionItem[]>([])
const suggestionLoading = ref(false)

const severities = ['critical', 'high', 'medium', 'low']

const form = reactive({
  rule_code: '',
  rule_name: '',
  severity: 'medium',
  event_type: '',
  window_seconds: 300,
  threshold: 10,
  group_by: '',
  cooldown_seconds: 600,
  touser: '',
})

function severityType(sev: string) {
  if (sev === 'critical' || sev === 'high') return 'danger'
  if (sev === 'medium') return 'warning'
  return 'info'
}

function configText(config: Record<string, unknown>) {
  const c = config ?? {}
  const parts: string[] = []
  if (c.event_type) parts.push(`type=${c.event_type}`)
  if (c.window_seconds) parts.push(`window=${c.window_seconds}s`)
  if (c.threshold) parts.push(`≥${c.threshold}`)
  if (Array.isArray(c.group_by) && c.group_by.length) parts.push(`by=${c.group_by.join(',')}`)
  return parts.join(' ') || JSON.stringify(c)
}

async function load() {
  loading.value = true
  try {
    items.value = await listRules()
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.rule_code = ''
  form.rule_name = ''
  form.severity = 'medium'
  form.event_type = ''
  form.window_seconds = 300
  form.threshold = 10
  form.group_by = ''
  form.cooldown_seconds = 600
  form.touser = ''
}

function openCreate() {
  editing.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: RuleItem) {
  editing.value = row
  const c = row.rule_config ?? {}
  form.rule_code = row.rule_code
  form.rule_name = row.rule_name
  form.severity = row.severity
  form.event_type = (c.event_type as string) ?? ''
  form.window_seconds = (c.window_seconds as number) ?? 300
  form.threshold = (c.threshold as number) ?? 10
  form.group_by = Array.isArray(c.group_by) ? (c.group_by as string[]).join(',') : ''
  form.cooldown_seconds = row.cooldown_seconds
  form.touser = row.touser ?? ''
  dialogVisible.value = true
}

async function toggle(row: RuleItem, enabled: boolean) {
  try {
    await updateRule(row.rule_code, { enabled })
    row.enabled = enabled
    ElMessage.success(enabled ? '已启用' : '已停用')
  } catch {
    ElMessage.error('操作失败')
  }
}

async function save() {
  if (!form.rule_code || !form.rule_name) {
    ElMessage.warning('请填写规则编码和名称')
    return
  }
  const ruleConfig: Record<string, unknown> = {
    event_type: form.event_type,
    window_seconds: form.window_seconds,
    threshold: form.threshold,
    group_by: form.group_by.split(',').map((s) => s.trim()).filter(Boolean),
  }
  saving.value = true
  try {
    if (editing.value) {
      await updateRule(editing.value.rule_code, {
        rule_name: form.rule_name,
        severity: form.severity,
        cooldown_seconds: form.cooldown_seconds,
        touser: form.touser || undefined,
        rule_config: ruleConfig,
      })
      ElMessage.success('已更新')
    } else {
      await createRule({
        rule_code: form.rule_code,
        rule_name: form.rule_name,
        severity: form.severity,
        cooldown_seconds: form.cooldown_seconds,
        touser: form.touser || undefined,
        rule_config: ruleConfig,
      })
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '保存失败')
  } finally {
    saving.value = false
  }
}

function suggestionStatusLabel(status: string) {
  if (status === 'pending') return '待处理'
  if (status === 'accepted') return '已采纳'
  if (status === 'ignored') return '已忽略'
  return status
}

function suggestionStatusType(status: string) {
  if (status === 'pending') return 'warning'
  if (status === 'accepted') return 'success'
  return 'info'
}

async function loadSuggestions() {
  suggestionLoading.value = true
  try {
    suggestions.value = await listRuleSuggestions()
  } finally {
    suggestionLoading.value = false
  }
}

async function accept(row: RuleSuggestionItem) {
  try {
    const { rule_code } = await acceptRuleSuggestion(row.id)
    ElMessage.success(`已采纳，生成规则 ${rule_code}`)
    row.status = 'accepted'
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '采纳失败')
  }
}

async function ignore(row: RuleSuggestionItem) {
  try {
    await ignoreRuleSuggestion(row.id)
    ElMessage.success('已忽略')
    row.status = 'ignored'
  } catch {
    ElMessage.error('忽略失败')
  }
}

onMounted(() => {
  load()
  loadSuggestions()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
