<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>调用方台账</span>
        <el-button type="primary" @click="openCreate">新增调用方</el-button>
      </div>
    </template>

    <el-form :inline="true" class="search-bar">
      <el-form-item label="身份类型">
        <el-select v-model="filters.identity_type" placeholder="全部" clearable style="width: 140px">
          <el-option v-for="t in IDENTITY_TYPES" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="关联模型">
        <el-select v-model="filters.model_code" placeholder="全部" clearable filterable style="width: 200px">
          <el-option v-for="m in models" :key="m.model_code" :label="m.model_code" :value="m.model_code" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <el-table-column prop="consumer_name" label="名称" min-width="140" show-overflow-tooltip />
      <el-table-column label="身份类型" width="110">
        <template #default="{ row }">
          <el-tag :type="identityTypeTag(row.identity_type)" size="small">{{ identityTypeLabel(row.identity_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="标识" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.identifier" class="mono">{{ row.identifier }}</span>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="关联模型" min-width="230">
        <template #default="{ row }">
          <template v-if="row.model_codes && row.model_codes.length">
            <el-tag v-for="c in row.model_codes.slice(0, 3)" :key="c" size="small" class="model-tag">{{ c }}</el-tag>
            <el-tag v-if="row.model_codes.length > 3" size="small" type="info" class="model-tag">+{{ row.model_codes.length - 3 }}</el-tag>
          </template>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="负责人" min-width="110" show-overflow-tooltip>
        <template #default="{ row }">{{ row.contact || '—' }}</template>
      </el-table-column>
      <el-table-column label="备注" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">{{ row.remark || '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="130" fixed="right">
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

  <el-dialog v-model="dialogVisible" :title="editing ? '编辑调用方' : '新增调用方'" width="520px">
    <el-form :model="form" label-width="90px">
      <el-form-item label="编码" required>
        <el-input v-model="form.consumer_code" :disabled="editing" placeholder="唯一编码，如 sys-portal" />
      </el-form-item>
      <el-form-item label="名称" required>
        <el-input v-model="form.consumer_name" placeholder="如 智能门户系统" />
      </el-form-item>
      <el-form-item label="身份类型">
        <el-select v-model="form.identity_type" style="width: 100%">
          <el-option v-for="t in IDENTITY_TYPES" :key="t.value" :label="`${t.label}（${t.value}）`" :value="t.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="标识">
        <el-input v-model="form.identifier" placeholder="IP 地址 / 容器 ID / 系统标识" />
      </el-form-item>
      <el-form-item label="负责人">
        <el-input v-model="form.contact" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.remark" />
      </el-form-item>
      <el-form-item label="证据">
        <el-input v-model="form.evidence" type="textarea" :rows="2" placeholder="判定依据，如日志、抓包记录" />
      </el-form-item>
      <el-form-item label="关联模型">
        <el-select v-model="form.model_codes" multiple filterable style="width: 100%" placeholder="选择该调用方调用的模型">
          <el-option v-for="m in models" :key="m.model_code" :label="m.model_code" :value="m.model_code" />
        </el-select>
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
import {
  createModelConsumer,
  deleteModelConsumer,
  listModelConsumers,
  listModels,
  updateModelConsumer,
  type ConsumerItem,
  type ModelItem,
} from '@/modules/model/api'

const IDENTITY_TYPES: Array<{ value: string; label: string }> = [
  { value: 'external_ip', label: '外部IP' },
  { value: 'container', label: '本机容器' },
  { value: 'external_system', label: '外部系统' },
]

const IDENTITY_TAG: Record<string, 'primary' | 'success' | 'warning' | 'danger' | 'info'> = {
  external_ip: 'danger',
  container: 'primary',
  external_system: 'warning',
}

function identityTypeLabel(v: string) {
  return IDENTITY_TYPES.find((t) => t.value === v)?.label ?? v
}

function identityTypeTag(v: string) {
  return IDENTITY_TAG[v] ?? 'info'
}

const items = ref<ConsumerItem[]>([])
const models = ref<ModelItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref(false)
const filters = reactive({ identity_type: '', model_code: '' })

const form = reactive({
  consumer_code: '',
  consumer_name: '',
  identity_type: 'external_ip',
  identifier: '',
  contact: '',
  remark: '',
  evidence: '',
  model_codes: [] as string[],
})

async function load() {
  loading.value = true
  try {
    const result = await listModelConsumers({
      page: page.value,
      page_size: pageSize.value,
      identity_type: filters.identity_type || undefined,
      model_code: filters.model_code || undefined,
    })
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

async function loadModels() {
  const result = await listModels({ page_size: 200 })
  models.value = result.items
}

function search() {
  page.value = 1
  load()
}

function reset() {
  filters.identity_type = ''
  filters.model_code = ''
  search()
}

function openCreate() {
  editing.value = false
  Object.assign(form, {
    consumer_code: '',
    consumer_name: '',
    identity_type: 'external_ip',
    identifier: '',
    contact: '',
    remark: '',
    evidence: '',
    model_codes: [],
  })
  dialogVisible.value = true
}

function openEdit(row: ConsumerItem) {
  editing.value = true
  Object.assign(form, {
    consumer_code: row.consumer_code,
    consumer_name: row.consumer_name,
    identity_type: row.identity_type || 'external_ip',
    identifier: row.identifier || '',
    contact: row.contact || '',
    remark: row.remark || '',
    evidence: row.evidence || '',
    model_codes: row.model_codes ? [...row.model_codes] : [],
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.consumer_code || !form.consumer_name) {
    ElMessage.warning('请填写编码和名称')
    return
  }
  saving.value = true
  try {
    const payload = {
      consumer_name: form.consumer_name,
      identity_type: form.identity_type,
      identifier: form.identifier || undefined,
      contact: form.contact || undefined,
      remark: form.remark || undefined,
      evidence: form.evidence || undefined,
      model_codes: form.model_codes,
    }
    if (editing.value) {
      await updateModelConsumer(form.consumer_code, payload)
    } else {
      await createModelConsumer({ consumer_code: form.consumer_code, ...payload })
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

async function remove(row: ConsumerItem) {
  await ElMessageBox.confirm(`确定删除调用方「${row.consumer_name || row.consumer_code}」？`, '提示', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  try {
    await deleteModelConsumer(row.consumer_code)
    ElMessage.success('已删除')
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '删除失败')
  }
}

onMounted(() => {
  load()
  loadModels()
})
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
.mono {
  font-family: Consolas, Monaco, 'Courier New', monospace;
}
.muted {
  color: #c0c4cc;
}
.model-tag {
  margin-right: 4px;
  margin-bottom: 2px;
}
</style>
