<template>
  <el-alert
    v-if="conflicts.length"
    class="conflict-alert"
    type="warning"
    :closable="false"
    show-icon
    title="分类规则存在冲突"
    :description="conflictText"
  />

  <el-alert
    v-if="degraded"
    class="conflict-alert"
    type="warning"
    :closable="false"
    show-icon
    title="Docker 服务不可达，项目容器数暂不可用"
    :description="degradeError || '规则本身可正常编辑。'"
  />

  <el-card>
    <template #header>
      <div class="card-header">
        <span>项目汇总</span>
        <div class="header-actions">
          <el-button size="small" @click="load()">刷新</el-button>
        </div>
      </div>
    </template>
    <el-table v-loading="loading" :data="projectRows" border stripe style="width: 100%">
      <el-table-column prop="project_name" label="项目" min-width="180" show-overflow-tooltip />
      <el-table-column prop="project_key" label="项目 key" min-width="140" show-overflow-tooltip />
      <el-table-column label="容器总数" width="110" />
      <el-table-column label="运行中" width="100" />
      <el-table-column label="已停止" width="100" />
      <el-table-column label="规则状态" width="110">
        <template #default="{ row }">
          <el-tag v-if="row.special" type="info" size="small" effect="plain">—</el-tag>
          <el-tag v-else :type="row.enabled ? 'success' : 'info'" size="small">
            {{ row.enabled ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-card class="mt">
    <template #header>
      <div class="card-header">
        <span>分类规则</span>
        <div class="header-actions">
          <el-button type="primary" size="small" @click="openCreate">新增规则</el-button>
        </div>
      </div>
    </template>
    <el-table v-loading="loading" :data="rules" border stripe style="width: 100%">
      <template #empty>
        <el-empty description="还没有分类规则" :image-size="80" />
      </template>
      <el-table-column prop="project_key" label="项目 key" min-width="130" show-overflow-tooltip />
      <el-table-column prop="project_name" label="项目名" min-width="150" show-overflow-tooltip />
      <el-table-column label="compose 项目名" min-width="180">
        <template #default="{ row }">
          <el-tag v-for="n in row.compose_project_names" :key="n" size="small" class="chip">{{ n }}</el-tag>
          <span v-if="!row.compose_project_names.length">—</span>
        </template>
      </el-table-column>
      <el-table-column label="容器名正则" min-width="200">
        <template #default="{ row }">
          <el-tag v-for="n in row.container_name_patterns" :key="n" size="small" type="warning" class="chip">{{ n }}</el-tag>
          <span v-if="!row.container_name_patterns.length">—</span>
        </template>
      </el-table-column>
      <el-table-column label="启用" width="90">
        <template #default="{ row }">
          <el-switch
            :model-value="row.enabled"
            size="small"
            :disabled="!canEdit"
            @change="(v: string | number | boolean) => toggle(row, Boolean(v))"
          />
        </template>
      </el-table-column>
      <el-table-column prop="priority" label="优先级" width="90" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button size="small" :disabled="!canEdit" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" :disabled="!canEdit" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="hint">
      容器名那一侧填的是<strong>正则</strong>，按 re.search 忽略大小写匹配；compose 项目名是精确匹配。
      一条容器同时命中多条规则时不指派任何项目（标为「规则冲突」），需人工消除冲突。
    </div>
  </el-card>

  <el-dialog v-model="dialogVisible" :title="editing ? '编辑规则' : '新增规则'" width="600px">
    <el-form :model="form" label-width="120px">
      <el-form-item label="项目 key" required>
        <el-input v-model="form.project_key" :disabled="editing" placeholder="如 hermes" />
      </el-form-item>
      <el-form-item label="项目名" required>
        <el-input v-model="form.project_name" placeholder="如 Hermes 网关" />
      </el-form-item>
      <el-form-item label="compose 项目名">
        <el-select
          v-model="form.compose_project_names"
          multiple
          filterable
          allow-create
          default-first-option
          :reserve-keyword="false"
          placeholder="输入后回车添加，精确匹配"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="容器名正则">
        <el-select
          v-model="form.container_name_patterns"
          multiple
          filterable
          allow-create
          default-first-option
          :reserve-keyword="false"
          placeholder="输入后回车添加，如 ^hermes-"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="优先级">
        <el-input-number v-model="form.priority" :min="0" :max="10000" />
        <div class="hint">数字小者优先。冲突时不会被自动采纳，仅作为人工消除冲突的参考顺序。</div>
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.enabled" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createProjectRule,
  deleteProjectRule,
  fetchProjects,
  listProjectRules,
  setProjectRuleEnabled,
  updateProjectRule,
  type ProjectRule,
  type RuleConflict,
} from '@/modules/agent/api'
import { useAuthStore } from '@/core/auth/store'

const auth = useAuthStore()
/** 规则写操作的门禁；服务端会独立再校验一次 */
const canEdit = computed(() => auth.canAccess(['agent_admin']))

interface ProjectRow {
  project_key: string
  project_name: string
  enabled: boolean | null
  total: number
  running: number
  stopped: number
  special: boolean
}

const rules = ref<ProjectRule[]>([])
const conflicts = ref<RuleConflict[]>([])
const summaryRows = ref<ProjectRow[]>([])
const loading = ref(false)
const degraded = ref(false)
const degradeError = ref<string | null>(null)

const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref(false)

const form = reactive({
  project_key: '',
  project_name: '',
  compose_project_names: [] as string[],
  container_name_patterns: [] as string[],
  priority: 100,
  enabled: true,
  description: '',
})

const projectRows = computed(() => summaryRows.value)

const conflictText = computed(() =>
  conflicts.value
    .map((c) => `${c.field === 'compose_project_names' ? 'compose 项目名' : '容器名正则'}「${c.value}」被 ${c.project_keys.join('、')} 同时声明`)
    .join('；'),
)

function errDetail(e: unknown): string | undefined {
  return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
}

async function load() {
  loading.value = true
  try {
    const [ruleResult, projectResult] = await Promise.all([listProjectRules(), fetchProjects()])
    rules.value = ruleResult.items
    conflicts.value = ruleResult.conflicts.concat(projectResult.conflicts)
    degraded.value = projectResult.degraded
    degradeError.value = projectResult.error
    summaryRows.value = [
      ...projectResult.projects.map((p) => ({
        project_key: p.project_key,
        project_name: p.project_name,
        enabled: p.enabled,
        total: p.total,
        running: p.running,
        stopped: p.stopped,
        special: false,
      })),
      {
        project_key: projectResult.unclassified.key,
        project_name: projectResult.unclassified.name,
        enabled: null,
        total: projectResult.unclassified.total,
        running: projectResult.unclassified.running,
        stopped: projectResult.unclassified.stopped,
        special: true,
      },
      {
        project_key: projectResult.conflict.key,
        project_name: projectResult.conflict.name,
        enabled: null,
        total: projectResult.conflict.total,
        running: projectResult.conflict.running,
        stopped: projectResult.conflict.stopped,
        special: true,
      },
    ]
  } catch (e: unknown) {
    ElMessage.error(errDetail(e) || '加载失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = false
  Object.assign(form, {
    project_key: '',
    project_name: '',
    compose_project_names: [],
    container_name_patterns: [],
    priority: 100,
    enabled: true,
    description: '',
  })
  dialogVisible.value = true
}

function openEdit(row: ProjectRule) {
  editing.value = true
  Object.assign(form, {
    project_key: row.project_key,
    project_name: row.project_name,
    compose_project_names: [...row.compose_project_names],
    container_name_patterns: [...row.container_name_patterns],
    priority: row.priority,
    enabled: row.enabled,
    description: row.description || '',
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.project_key || !form.project_name) {
    ElMessage.warning('请填写项目 key 与项目名')
    return
  }
  saving.value = true
  try {
    const payload = {
      project_name: form.project_name,
      compose_project_names: form.compose_project_names,
      container_name_patterns: form.container_name_patterns,
      priority: form.priority,
      enabled: form.enabled,
      description: form.description || undefined,
    }
    if (editing.value) {
      await updateProjectRule(form.project_key, payload)
    } else {
      await createProjectRule({ project_key: form.project_key, ...payload })
    }
    ElMessage.success('已保存')
    dialogVisible.value = false
    load()
  } catch (e: unknown) {
    ElMessage.error(errDetail(e) || '保存失败')
  } finally {
    saving.value = false
  }
}

async function toggle(row: ProjectRule, enabled: boolean) {
  try {
    await setProjectRuleEnabled(row.project_key, enabled)
    ElMessage.success(enabled ? '已启用' : '已停用')
    load()
  } catch (e: unknown) {
    ElMessage.error(errDetail(e) || '操作失败')
  }
}

async function remove(row: ProjectRule) {
  try {
    await ElMessageBox.confirm(
      `确定删除分类规则「${row.project_name}」？删除的只是规则，不会影响任何实际容器；原本归到该项目的容器会退回「未分类」并变为只读。`,
      '提示',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await deleteProjectRule(row.project_key)
    ElMessage.success('已删除')
    load()
  } catch (e: unknown) {
    ElMessage.error(errDetail(e) || '删除失败')
  }
}

onMounted(load)
</script>

<style scoped>
.conflict-alert {
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
  margin-top: 8px;
  color: #909399;
  font-size: 12px;
  line-height: 1.6;
}
.chip {
  margin-right: 4px;
}
.mt {
  margin-top: 16px;
}
</style>
