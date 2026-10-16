<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>数据库实例</span>
        <el-button type="primary" @click="openCreate">登记实例</el-button>
      </div>
    </template>

    <el-form :inline="true" class="search-bar">
      <el-form-item label="类型">
        <el-input v-model="filters.db_type" placeholder="按类型筛选" clearable style="width: 150px" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <el-table-column prop="instance_code" label="实例编码" min-width="130" show-overflow-tooltip />
      <el-table-column prop="instance_name" label="名称" min-width="140" show-overflow-tooltip />
      <el-table-column prop="db_type" label="类型" width="110" />
      <el-table-column label="地址" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ row.host }}:{{ row.port }}</template>
      </el-table-column>
      <el-table-column prop="database_name" label="库名" width="120" show-overflow-tooltip />
      <el-table-column prop="environment" label="环境" width="100" />
      <el-table-column label="健康状态" width="100">
        <template #default="{ row }">
          <el-tag :type="healthType(row.health_status)" size="small">{{ row.health_status }}</el-tag>
        </template>
      </el-table-column>
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

  <el-dialog v-model="dialogVisible" :title="editing ? '编辑实例' : '登记实例'" width="540px">
    <el-form :model="form" label-width="100px">
      <el-form-item label="实例编码" required>
        <el-input v-model="form.instance_code" :disabled="editing" />
      </el-form-item>
      <el-form-item label="名称" required>
        <el-input v-model="form.instance_name" />
      </el-form-item>
      <el-form-item label="类型" required>
        <el-select v-model="form.db_type" style="width: 100%">
          <el-option v-for="t in dbTypes" :key="t" :label="t" :value="t" />
        </el-select>
      </el-form-item>
      <el-form-item label="主机" required>
        <el-input v-model="form.host" placeholder="IP 或域名" />
      </el-form-item>
      <el-form-item label="端口" required>
        <el-input-number v-model="form.port" :min="1" :max="65535" style="width: 100%" />
      </el-form-item>
      <el-form-item label="库名">
        <el-input v-model="form.database_name" />
      </el-form-item>
      <el-form-item label="用户名">
        <el-input v-model="form.username" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input v-model="form.password" type="password" show-password :placeholder="editing ? '留空或 **** 开头则不修改' : ''" />
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
import {
  checkInstance,
  createInstance,
  deleteInstance,
  listInstances,
  updateInstance,
  type InstanceItem,
} from '@/modules/database/api'

const items = ref<InstanceItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref(false)

const dbTypes = ['mysql', 'postgres', 'redis', 'mongodb', 'sqlserver', 'oracle', 'other']
const environments = ['production', 'staging', 'development', 'internal', 'external']

const filters = reactive({ db_type: '' })
const form = reactive({
  instance_code: '',
  instance_name: '',
  db_type: 'mysql',
  host: '',
  port: 3306,
  database_name: '',
  username: '',
  password: '',
  environment: '',
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
    const result = await listInstances({
      page: page.value,
      page_size: pageSize.value,
      db_type: filters.db_type || undefined,
    })
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = false
  Object.assign(form, { instance_code: '', instance_name: '', db_type: 'mysql', host: '', port: 3306, database_name: '', username: '', password: '', environment: '', enabled: true })
  dialogVisible.value = true
}

function openEdit(row: InstanceItem) {
  editing.value = true
  Object.assign(form, {
    instance_code: row.instance_code,
    instance_name: row.instance_name,
    db_type: row.db_type,
    host: row.host,
    port: row.port,
    database_name: row.database_name || '',
    username: row.username || '',
    password: '',
    environment: row.environment || '',
    enabled: row.enabled,
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.instance_code || !form.instance_name || !form.host || !form.port) {
    ElMessage.warning('请填写实例编码、名称、主机和端口')
    return
  }
  saving.value = true
  try {
    const payload = {
      instance_name: form.instance_name,
      db_type: form.db_type,
      host: form.host,
      port: form.port,
      database_name: form.database_name || undefined,
      username: form.username || undefined,
      password: form.password || undefined,
      environment: form.environment || undefined,
      enabled: form.enabled,
    }
    if (editing.value) {
      await updateInstance(form.instance_code, payload)
    } else {
      await createInstance({ instance_code: form.instance_code, ...payload })
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

async function check(row: InstanceItem) {
  try {
    const result = await checkInstance(row.instance_code)
    ElMessage.success(`检测完成：${result.health_status}${result.latency_ms != null ? `（${result.latency_ms}ms）` : ''}`)
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '检测失败')
  }
}

async function remove(row: InstanceItem) {
  await ElMessageBox.confirm(`确定删除实例「${row.instance_name || row.instance_code}」？`, '提示', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  try {
    await deleteInstance(row.instance_code)
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
  filters.db_type = ''
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
