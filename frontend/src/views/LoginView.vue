<template>
  <div class="min-h-screen flex items-center justify-center p-4">
    <div class="card p-8 w-full max-w-sm animate-in">
      <div class="text-center mb-8">
        <span class="text-3xl font-bold text-brand-500">▶</span>
        <h1 class="text-2xl font-bold mt-2 text-gradient">MediaStation</h1>
        <p class="text-sm mt-1" style="color: var(--text-muted)">轻量级家庭媒体服务器</p>
      </div>

      <form @submit.prevent="handleLogin" class="space-y-4">
        <div>
          <label class="block text-sm font-medium mb-1.5" style="color: var(--text-muted)">用户名</label>
          <input v-model="username" type="text" class="input" placeholder="请输入用户名" required />
        </div>
        <div>
          <label class="block text-sm font-medium mb-1.5" style="color: var(--text-muted)">密码</label>
          <input v-model="password" type="password" class="input" placeholder="请输入密码" required />
        </div>

        <div v-if="error" class="text-red-400 text-sm text-center">{{ error }}</div>

        <button type="submit" :disabled="loading"
          class="btn-primary w-full py-2.5 disabled:opacity-50 disabled:cursor-not-allowed">
          {{ loading ? '登录中...' : '登 录' }}
        </button>
      </form>

      <p class="text-center text-xs mt-6" style="color: var(--text-faint)">默认账号: admin / admin123</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const username = ref('admin')
const password = ref('admin123')
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  loading.value = true
  error.value = ''
  try {
    await auth.login(username.value, password.value)
    router.push('/')
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.response?.data?.message || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>
