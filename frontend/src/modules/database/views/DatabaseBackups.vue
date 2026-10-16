<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>备份记录</span>
        <el-button type="primary" @click="openCreate">登记备份</el-button>
      </div>
    </template>

    <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <el-table-column prop="instance_code" label="实例编码" min-width="150" show-overflow-tooltip />
      <el-table-column prop="backup_type" label="备份类型" width="110" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'success' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="size" label="大小(字节)" width="120" />
      <el-table-column prop="started_at" label="开始时间" min-width="170" />
      <el-table-column prop="finished_at" label="完成时间" min-width="170" />
      <el-table-column prop="result" label="结果" min-width="150" show-overflow-tooltip />
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

  <el-dialog v-model="dialogVisible" title="登记备份" width="520px">
    <el-form :model="form" label-width="110px">
      <el-form-item label="实例编码" required>
        <el-select v-model="form.instance_code" style="width: 100%">
          <el-option v-for="i in instances" :key="i.instance_code" :label="i.instance_name" :value="i.instance_code" />
        </el-select>
      </el-form-item>
      <el-form-item label="备份类型">
        <el-select v-model="form.backup_type" style="width: 100%">
          <el-option v-for="t in backupTypes" :key="t" :label="t" :value="t" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="form.status" style="width: 100%">
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failed" />
          <el-option label="进行中" value="running" />
        </el-select>
      </el-form-item>
      <el-form-item label="大小(字节)">
        <el-input-number v-model="form.size" :min="0" style="width: 100%" />
      </el-form-item>
      <el-form-item label="结果说明">
        <el-input v-model="form.result" />
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
import { listBackups, listInstances, registerBackup, type BackupItem, type InstanceItem } from '@/modules/database/api'

const items = ref<BackupItem[]>([])
const instances = ref<InstanceItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)

const backupTypes = ['full', 'incremental', 'log']

const form = reactive({
  instance_code: '',
  backup_type: 'full',
  status: 'success',
  size: 0,
  result: '',
})

async function load() {
  loading.value = true
  try {
    const result = await listBackups({ page: page.value, page_size: pageSize.value })
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

async function loadInstances() {
  const result = await listInstances({ page_size: 200 })
  instances.value = result.items
}

function openCreate() {
  Object.assign(form, { instance_code: instances.value[0]?.instance_code || '', backup_type: 'full', status: 'success', size: 0, result: '' })
  dialogVisible.value = true
}

async function save() {
  if (!form.instance_code) {
    ElMessage.warning('请选择实例')
    return
  }
  saving.value = true
  try {
    await registerBackup({
      instance_code: form.instance_code,
      backup_type: form.backup_type,
      status: form.status,
      size: form.size,
      result: form.result || undefined,
    })
    ElMessage.success('已登记')
    dialogVisible.value = false
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '登记失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  load()
  loadInstances()
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
