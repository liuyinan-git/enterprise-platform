<template>
  <el-card class="unregistered">
    <template #header>
      <div class="card-header">
        <span>未登记容器（{{ total }}）</span>
        <div class="header-right">
          <span class="hint">
            既不在台账中、也未被任何台账行关联的容器<template v-if="hiddenUnknown">
              ；另有 {{ hiddenUnknown }} 个未分类容器未显示</template
            >
          </span>
          <el-select v-model="filter" size="small" style="width: 168px">
            <el-option label="全部受管类型" :value="UNREGISTERED_MANAGED" />
            <el-option label="全部容器（含未分类）" :value="UNREGISTERED_ALL" />
            <el-option v-for="t in MANAGED_TYPES" :key="t" :label="t" :value="t">
              <span>{{ t }}</span>
              <span class="option-count">{{ typeCount[t] || 0 }}</span>
            </el-option>
          </el-select>
          <el-switch v-model="showProtected" size="small" active-text="显示平台自身容器" />
        </div>
      </div>
    </template>

    <el-table v-loading="loading" :data="items" border stripe style="width: 100%">
      <el-table-column prop="name" label="容器名" min-width="160" show-overflow-tooltip />
      <el-table-column prop="container_id" label="短 ID" width="120" />
      <el-table-column label="类型" width="100">
        <template #default="{ row }">
          <el-tooltip :content="typeSourceLabel(row.managed_type_source)" placement="top">
            <el-tag :type="typeTagType(row.managed_type)" size="small" effect="plain">
              {{ typeLabel(row.managed_type) }}
            </el-tag>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column prop="image" label="镜像" min-width="200" show-overflow-tooltip />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="stateTagType(row.state)" size="small">{{ stateLabel(row.state) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="端口" min-width="150">
        <template #default="{ row }">
          <span v-if="row.ports.length">{{ row.ports.join('、') }}</span>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="保护" width="90">
        <template #default="{ row }">
          <el-tooltip v-if="row.protected" :content="row.protected_reason || ''" placement="top">
            <el-tag type="info" size="small">受保护</el-tag>
          </el-tooltip>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="容器操作" width="250" fixed="right">
        <template #default="{ row }">
          <ContainerActions
            :container="row"
            :operable="canControl && isOperable(row)"
            @log="emit('log', $event)"
            @action="(container, action) => emit('action', container, action)"
          />
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && !items.length" description="没有未登记的容器" />
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ContainerAction, ContainerItem } from '@/modules/database/api'
import {
  MANAGED_TYPES,
  UNREGISTERED_ALL,
  UNREGISTERED_MANAGED,
  isOperable,
  stateLabel,
  stateTagType,
  typeLabel,
  typeSourceLabel,
  typeTagType,
} from '@/modules/database/container-display'
import ContainerActions from '@/modules/database/components/ContainerActions.vue'

const props = defineProps<{
  items: ContainerItem[]
  total: number
  loading: boolean
  includeProtected: boolean
  /** 当前用户是否具备 database:container 权限（服务端仍会独立校验） */
  canControl: boolean
  /** 当前筛选值：哨兵值或受管类型名 */
  filter: string
  /** 被「只列受管类型」滤掉的未分类容器数 */
  hiddenUnknown: number
  /** 各类型的未登记数量（后端在类型过滤前统计） */
  countByType: Record<string, number>
}>()

const emit = defineEmits<{
  (e: 'update:includeProtected', value: boolean): void
  (e: 'update:filter', value: string): void
  (e: 'log', container: ContainerItem): void
  (e: 'action', container: ContainerItem, action: ContainerAction): void
}>()

const showProtected = computed({
  get: () => props.includeProtected,
  set: (value: boolean) => emit('update:includeProtected', value),
})

const filter = computed({
  get: () => props.filter,
  set: (value: string) => emit('update:filter', value),
})

/**
 * 计数可能整个缺席（父组件尚未铺好数据、HMR 换组件时也会短暂如此），
 * 直接写 `countByType[t]` 会在 undefined 上取属性抛错，所以统一走这个兜底。
 */
const typeCount = computed<Record<string, number>>(() => props.countByType || {})
</script>

<style scoped>
.unregistered {
  margin-top: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.hint {
  color: #909399;
  font-size: 12px;
}
.option-count {
  float: right;
  color: #909399;
  font-size: 12px;
}
</style>
