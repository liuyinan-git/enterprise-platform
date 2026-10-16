<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>附件管理</span>
        <div class="upload-area">
          <el-input v-model="uploader" placeholder="上传人" clearable style="width: 140px" />
          <el-upload :http-request="doUpload" :show-file-list="false" multiple>
            <el-button type="primary">上传附件</el-button>
          </el-upload>
        </div>
      </div>
    </template>

    <el-form :inline="true" class="search-bar">
      <el-form-item label="类型">
        <el-select v-model="filters.category" placeholder="全部" clearable style="width: 140px">
          <el-option v-for="c in categories" :key="c.value" :label="c.label" :value="c.value" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <el-table-column prop="filename" label="文件名" min-width="220" show-overflow-tooltip />
      <el-table-column label="上传人" width="100" show-overflow-tooltip>
        <template #default="{ row }">{{ row.uploader || '—' }}</template>
      </el-table-column>
      <el-table-column label="类型" width="90">
        <template #default="{ row }">
          <el-tag size="small">{{ categoryLabel(row.category) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="大小" width="100">
        <template #default="{ row }">{{ formatSize(row.size) }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="上传时间" min-width="170" />
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="download(row)">下载</el-button>
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
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteFile,
  fileDownloadUrl,
  listFiles,
  uploadFile,
  type AttachmentItem,
} from '@/api/client'

const items = ref<AttachmentItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const uploader = ref('')

const categories = [
  { value: 'document', label: '文档' },
  { value: 'spreadsheet', label: '表格' },
  { value: 'image', label: '图片' },
  { value: 'video', label: '视频' },
]
const filters = reactive({ category: '' })

function categoryLabel(c: string) {
  return categories.find((x) => x.value === c)?.label ?? c
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

async function load() {
  loading.value = true
  try {
    const result = await listFiles({
      page: page.value,
      page_size: pageSize.value,
      category: filters.category || undefined,
    })
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

async function doUpload(options: { file: File }) {
  try {
    await uploadFile(options.file, uploader.value || undefined)
    ElMessage.success('上传成功')
    load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(msg || '上传失败')
  }
}

function download(row: AttachmentItem) {
  window.open(fileDownloadUrl(row.id), '_blank')
}

async function remove(row: AttachmentItem) {
  await ElMessageBox.confirm(`确定删除「${row.filename}」？`, '提示', { type: 'warning' })
  try {
    await deleteFile(row.id)
    ElMessage.success('已删除')
    load()
  } catch {
    ElMessage.error('删除失败')
  }
}

function search() {
  page.value = 1
  load()
}

function reset() {
  filters.category = ''
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
.upload-area {
  display: flex;
  align-items: center;
  gap: 8px;
}
.search-bar {
  margin-bottom: 8px;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
