<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>模型注册</span>
        <el-button type="primary" @click="openCreate">新增模型</el-button>
      </div>
    </template>

    <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <el-table-column prop="model_code" label="模型编码" min-width="130" show-overflow-tooltip />
      <el-table-column prop="model_name" label="模型名" min-width="150" show-overflow-tooltip />
      <el-table-column prop="provider_name" label="供应商" width="130" show-overflow-tooltip />
      <el-table-column prop="version" label="版本" width="100" />
      <el-table-column prop="context_window" label="上下文" width="100" />
      <el-table-column label="健康状态" width="100">
        <template #default="{ row }">
          <el-tag :type="healthType(row.health_status)" size="small">{{ row.health_status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="last_check_at" label="最后检测" min-width="170" />
      <el-table-column label="操作" width="210" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="check(row)">检测</el-button>
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

  <el-dialog v-model="dialogVisible" :title="editing ? '编辑模型' : '新增模型'" width="520px">
    <el-form :model="form" label-width="110px">
      <el-form-item label="模型编码" required>
        <el-input v-model="form.model_code" :disabled="editing" />
      </el-form-item>
      <el-form-item label="模型名" required>
        <el-input v-model="form.model_name" placeholder="如 deepseek-chat" />
      </el-form-item>
      <el-form-item label="供应商" required>
        <el-select v-model="form.provider_code" style="width: 100%" :disabled="editing">
          <el-option v-for="p in providers" :key="p.provider_code" :label="p.provider_name" :value="p.provider_code" />
        </el-select>
      </el-form-item>
      <el-form-item label="版本">
        <el-input v-model="form.version" />
      </el-form-item>
      <el-form-item label="上下文长度">
        <el-input-number v-model="form.context_window" :min="0" style="width: 100%" />
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
import {
  checkModel,
  createModel,
  deleteModel,
  listModels,
  listProviders,
  updateModel,
  type ModelItem,
  type ProviderItem,
} from '@/modules/model/api'

const items = ref<ModelItem[]>([])
const providers = ref<ProviderItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref(false)

const form = reactive({
  model_code: '',
  model_name: '',
  provider_code: '',
  version: '',
  context_window: 4096,
  enabled: true,
})

function healthType(s: string) {
  if (s === 'healthy') return 'success'
  if (s === 'unhealthy') return 'danger'
  return 'info'
}

async function load() {
  loading.value = true
  try {
    const result = await listModels({ page: page.value, page_size: pageSize.value })
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

async function loadProviders() {
  const result = await listProviders({ page_size: 200 })
  providers.value = result.items
}

function openCreate() {
  editing.value = false
  Object.assign(form, { model_code: '', model_name: '', provider_code: providers.value[0]?.provider_code || '', version: '', context_window: 4096, enabled: true })
  dialogVisible.value = true
}

function openEdit(row: ModelItem) {
  editing.value = true
  Object.assign(form, {
    model_code: row.model_code,
    model_name: row.model_name,
    provider_code: row.provider_code || '',
    version: row.version || '',
    context_window: row.context_window ?? 4096,
    enabled: row.enabled,
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.model_code || !form.model_name || !form.provider_code) {
    ElMessage.warning('请填写模型编码、模型名和供应商')
    return
  }
  saving.value = true
  try {
    const payload = {
      model_name: form.model_name,
      version: form.version || undefined,
      context_window: form.context_window,
      enabled: form.enabled,
    }
    if (editing.value) {
      await updateModel(form.model_code, payload)
    } else {
      await createModel({ model_code: form.model_code, provider_code: form.provider_code, ...payload })
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

async function check(row: ModelItem) {
  try {
    const result = await checkModel(row.model_code)
    ElMessage.success(`检测完成：${result.health_status}（${result.detail}）`)
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '检测失败')
  }
}

async function remove(row: ModelItem) {
  await ElMessageBox.confirm(`确定删除模型「${row.model_name || row.model_code}」？`, '提示', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  try {
    await deleteModel(row.model_code)
    ElMessage.success('已删除')
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '删除失败')
  }
}

onMounted(() => {
  load()
  loadProviders()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
