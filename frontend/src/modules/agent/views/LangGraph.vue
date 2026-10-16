<template>
  <!--
    与「接口监控」共用同一张端点表（后端用 service_type 区分），因此复用同一个视图组件。
    fixed-service-type 会隐藏类型筛选/列、多显示「图名」列，并把表单里的类型锁死。
  -->
  <Endpoints fixed-service-type="langgraph" />
</template>

<script setup lang="ts">
import Endpoints from '@/modules/agent/views/Endpoints.vue'
</script>
