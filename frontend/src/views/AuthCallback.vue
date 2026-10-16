<template>
  <div class="callback">
    <p>{{ message }}</p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/core/auth/store'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const message = ref('正在完成登录…')

onMounted(async () => {
  const code = route.query.code as string | undefined
  if (!code) {
    message.value = '缺少授权码，登录失败'
    return
  }
  try {
    await auth.finishLogin(code)
    router.replace('/')
  } catch (e: unknown) {
    message.value = `登录失败：${(e as Error).message}`
  }
})
</script>

<style scoped>
.callback {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  color: #333;
}
</style>
