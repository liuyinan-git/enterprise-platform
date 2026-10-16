<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>模型供应商</span>
        <el-button type="primary" @click="openCreate">新增供应商</el-button>
      </div>
    </template>

    <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <el-table-column prop="provider_code" label="编码" min-width="130" show-overflow-tooltip />
      <el-table-column prop="provider_name" label="名称" min-width="140" show-overflow-tooltip />
      <el-table-column prop="provider_type" label="类型" width="120" />
      <el-table-column prop="base_url" label="接口地址" min-width="220" show-overflow-tooltip />
      <el-table-column prop="api_key_masked" label="密钥" width="120" />
      <el-table-column label="启用" width="80">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '启用' : '停用' }}</el-tag>
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

  <el-dialog v-model="dialogVisible" :title="editing ? '编辑供应商' : '新增供应商'" width="520px">
    <el-form :model="form" label-width="110px">
      <el-form-item label="编码" required>
        <el-input v-model="form.provider_code" :disabled="editing" />
      </el-form-item>
      <el-form-item label="名称" required>
        <el-input v-model="form.provider_name" />
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="form.provider_type" style="width: 100%">
          <el-option v-for="t in providerTypes" :key="t" :label="t" :value="t" />
        </el-select>
      </el-form-item>
      <el-form-item label="接口地址">
        <el-input v-model="form.base_url" placeholder="https://api.deepseek.com/v1" />
      </el-form-item>
      <el-form-item label="API Key">
        <el-input v-model="form.api_key" type="password" show-password :placeholder="editing ? '留空或 **** 开头则不修改' : ''" />
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
import { createProvider, deleteProvider, listProviders, updateProvider, type ProviderItem } from '@/modules/model/api'

const items = ref<ProviderItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref(false)

const providerTypes = ['openai', 'deepseek', 'ollama', 'anthropic', 'other']

const form = reactive({
  provider_code: '',
  provider_name: '',
  provider_type: 'openai',
  base_url: '',
  api_key: '',
  enabled: true,
})

async function load() {
  loading.value = true
  try {
    const result = await listProviders({ page: page.value, page_size: pageSize.value })
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = false
  Object.assign(form, { provider_code: '', provider_name: '', provider_type: 'openai', base_url: '', api_key: '', enabled: true })
  dialogVisible.value = true
}

function openEdit(row: ProviderItem) {
  editing.value = true
  Object.assign(form, {
    provider_code: row.provider_code,
    provider_name: row.provider_name,
    provider_type: row.provider_type,
    base_url: row.base_url,
    api_key: '',
    enabled: row.enabled,
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.provider_code || !form.provider_name) {
    ElMessage.warning('请填写编码和名称')
    return
  }
  saving.value = true
  try {
    const payload = {
      provider_name: form.provider_name,
      provider_type: form.provider_type,
      base_url: form.base_url,
      api_key: form.api_key || undefined,
      enabled: form.enabled,
    }
    if (editing.value) {
      await updateProvider(form.provider_code, payload)
    } else {
      await createProvider({ provider_code: form.provider_code, ...payload })
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

async function remove(row: ProviderItem) {
  await ElMessageBox.confirm(`确定删除供应商「${row.provider_name || row.provider_code}」？`, '提示', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  try {
    await deleteProvider(row.provider_code)
    ElMessage.success('已删除')
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '删除失败')
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
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
