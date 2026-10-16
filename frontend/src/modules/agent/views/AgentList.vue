<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>智能体管理</span>
        <el-button type="primary" @click="openCreate">登记智能体</el-button>
      </div>
    </template>

    <el-form :inline="true" class="search-bar">
      <el-form-item label="类型">
        <el-input v-model="filters.agent_type" placeholder="按类型筛选" clearable style="width: 160px" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <el-table-column prop="agent_id" label="智能体 ID" min-width="140" show-overflow-tooltip />
      <el-table-column prop="agent_name" label="名称" min-width="140" show-overflow-tooltip />
      <el-table-column prop="agent_type" label="类型" width="120" />
      <el-table-column prop="version" label="版本" width="100" />
      <el-table-column prop="owner" label="负责人" width="110" />
      <el-table-column prop="environment" label="环境" width="100" />
      <el-table-column prop="last_seen_at" label="最后心跳" min-width="170" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
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

  <el-dialog v-model="dialogVisible" :title="editing ? '编辑智能体' : '登记智能体'" width="520px">
    <el-form :model="form" label-width="100px">
      <el-form-item label="智能体 ID" required>
        <el-input v-model="form.agent_id" :disabled="editing" />
      </el-form-item>
      <el-form-item label="名称" required>
        <el-input v-model="form.agent_name" />
      </el-form-item>
      <el-form-item label="类型">
        <el-input v-model="form.agent_type" placeholder="如 chatbot / workflow / rag" />
      </el-form-item>
      <el-form-item label="版本">
        <el-input v-model="form.version" />
      </el-form-item>
      <el-form-item label="负责人">
        <el-input v-model="form.owner" />
      </el-form-item>
      <el-form-item label="环境">
        <el-select v-model="form.environment" clearable style="width: 100%">
          <el-option v-for="e in environments" :key="e" :label="e" :value="e" />
        </el-select>
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.enabled" />
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteAgent, listAgents, registerAgent, updateAgent, type AgentItem } from '@/modules/agent/api'

const items = ref<AgentItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref(false)

const environments = ['production', 'staging', 'development', 'internal', 'external']

const filters = reactive({ agent_type: '' })
const form = reactive({
  agent_id: '',
  agent_name: '',
  agent_type: '',
  version: '',
  owner: '',
  environment: '',
  enabled: true,
})

function statusType(s: string) {
  if (s === 'online') return 'success'
  if (s === 'disabled') return 'warning'
  return 'info'
}
function statusText(s: string) {
  if (s === 'online') return '在线'
  if (s === 'disabled') return '停用'
  return '离线'
}

async function load() {
  loading.value = true
  try {
    const result = await listAgents({
      page: page.value,
      page_size: pageSize.value,
      agent_type: filters.agent_type || undefined,
    })
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = false
  Object.assign(form, { agent_id: '', agent_name: '', agent_type: '', version: '', owner: '', environment: '', enabled: true })
  dialogVisible.value = true
}

function openEdit(row: AgentItem) {
  editing.value = true
  Object.assign(form, {
    agent_id: row.agent_id,
    agent_name: row.agent_name,
    agent_type: row.agent_type,
    version: row.version || '',
    owner: row.owner || '',
    environment: row.environment || '',
    enabled: row.enabled,
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.agent_id || !form.agent_name) {
    ElMessage.warning('请填写智能体 ID 和名称')
    return
  }
  saving.value = true
  try {
    const payload = {
      agent_name: form.agent_name,
      agent_type: form.agent_type,
      version: form.version || undefined,
      owner: form.owner || undefined,
      environment: form.environment || undefined,
      enabled: form.enabled,
    }
    if (editing.value) {
      await updateAgent(form.agent_id, payload)
    } else {
      await registerAgent({ agent_id: form.agent_id, ...payload })
    }
    ElMessage.success('已保存')
    dialogVisible.value = false
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '保存失败')
  } finally {
    saving.value = false
  }
}

async function remove(row: AgentItem) {
  await ElMessageBox.confirm(`确定删除智能体「${row.agent_name || row.agent_id}」？`, '提示', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  try {
    await deleteAgent(row.agent_id)
    ElMessage.success('已删除')
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '删除失败')
  }
}

function search() {
  page.value = 1
  load()
}
function reset() {
  filters.agent_type = ''
  search()
}

onMounted(load)
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.search-bar {
  margin-bottom: 8px;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
