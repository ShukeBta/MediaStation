<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <p class="text-sm" style="color: var(--text-muted)">管理所有用户账号</p>
      <button @click="openModal()" class="btn-primary text-sm flex items-center gap-1">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
        </svg>
        创建用户
      </button>
    </div>

    <!-- 用户列表 -->
    <div class="space-y-3">
      <div v-for="u in users" :key="u.id" class="card p-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3 min-w-0">
            <!-- 头像 -->
            <div class="w-10 h-10 rounded-full overflow-hidden bg-[var(--bg-input)] shrink-0 flex items-center justify-center">
              <img v-if="u.avatar" :src="u.avatar" class="w-full h-full object-cover" :alt="u.username" />
              <svg v-else class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" style="color: var(--text-faint)">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
              </svg>
            </div>
            <div class="min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="font-medium">{{ u.username }}</span>
                <span :class="['text-xs px-1.5 py-0.5 rounded', u.role === 'admin' ? 'bg-brand-500/15 text-brand-400' : 'bg-[var(--bg-input)]']"
                  :style="u.role !== 'admin' ? 'color: var(--text-muted)' : ''">
                  {{ u.role === 'admin' ? '管理员' : '普通用户' }}
                </span>
                <span v-if="u.tier === 'plus'" class="text-xs px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400">
                  Plus
                </span>
                <span v-if="!u.is_active" class="text-xs px-1.5 py-0.5 rounded bg-red-500/10 text-red-400">已禁用</span>
              </div>
              <div class="text-xs mt-0.5" style="color: var(--text-muted)">
                创建于 {{ formatDate(u.created_at) }}
                <span v-if="u.last_login"> · 最后登录 {{ formatDate(u.last_login) }}</span>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-1 shrink-0 ml-2">
            <button @click="openModal(u)"
              class="p-1.5 rounded-lg transition-colors hover:bg-[var(--bg-hover)]" style="color: var(--text-muted)" title="编辑">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
              </svg>
            </button>
            <button @click="toggleActive(u)"
              :class="['p-1.5 rounded-lg transition-colors', u.is_active ? 'hover:bg-yellow-500/10 hover:text-yellow-400' : 'hover:bg-green-500/10 hover:text-green-400']"
              style="color: var(--text-muted)" :title="u.is_active ? '禁用用户' : '启用用户'">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path v-if="u.is_active" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"/>
                <path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </button>
            <button @click="confirmDelete(u)"
              :class="['p-1.5 rounded-lg transition-colors hover:bg-red-500/10 hover:text-red-400', currentUserId === u.id ? 'opacity-30 cursor-not-allowed' : '']"
              style="color: var(--text-muted)" title="删除用户" :disabled="currentUserId === u.id">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <AppEmpty v-if="users.length === 0" message="暂无用户" />

    <!-- 创建/编辑弹窗 -->
    <AppModal v-model:show="modal.show" :title="modal.editing ? '编辑用户' : '创建用户'">
      <div class="space-y-4">
        <div>
          <label class="block text-sm mb-1" style="color: var(--text-muted)">用户名</label>
          <input v-model="modal.username" :disabled="!!modal.editing" class="input disabled:opacity-50" placeholder="至少 2 位字符" />
        </div>
        <div>
          <label class="block text-sm mb-1" style="color: var(--text-muted)">
            {{ modal.editing ? '新密码（留空则不修改）' : '密码' }}
          </label>
          <div class="relative">
            <input v-model="modal.password" :type="modal.showPw ? 'text' : 'password'" class="input pr-10"
              :placeholder="modal.editing ? '留空不修改，至少 6 位' : '至少 6 位'" />
            <button type="button" @click="modal.showPw = !modal.showPw" class="absolute right-3 top-1/2 -translate-y-1/2" style="color: var(--text-muted)">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
              </svg>
            </button>
          </div>
        </div>
        <div>
          <label class="block text-sm mb-1" style="color: var(--text-muted)">角色</label>
          <select v-model="modal.role" class="input">
            <option value="user">普通用户</option>
            <option value="admin">管理员</option>
          </select>
        </div>
      </div>
      <template #footer>
        <button @click="modal.show = false" class="btn-secondary text-sm">取消</button>
        <button @click="save" class="btn-primary text-sm">保存</button>
      </template>
    </AppModal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { authApi, userApi } from '@/api/auth'
import { useToast } from '@/composables/useToast'
import AppModal from '@/components/AppModal.vue'
import AppEmpty from '@/components/AppEmpty.vue'

const toast = useToast()
const users = ref<any[]>([])
const currentUserId = ref<number | null>(null)

const modal = ref({
  show: false, editing: null as any,
  username: '', password: '', role: 'user', showPw: false,
})

function formatDate(d: string) {
  if (!d) return ''
  const dt = new Date(d)
  return dt.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function openModal(u?: any) {
  modal.value = u
    ? { show: true, editing: u, username: u.username, password: '', role: u.role, showPw: false }
    : { show: true, editing: null, username: '', password: '', role: 'user', showPw: false }
}

async function save() {
  try {
    if (modal.value.editing) {
      const payload: any = { role: modal.value.role }
      if (modal.value.password) payload.password = modal.value.password
      await userApi.updateUser(modal.value.editing.id, payload)
    } else {
      if (!modal.value.username || modal.value.password.length < 6) {
        toast.error('请填写用户名和至少 6 位的密码')
        return
      }
      await userApi.createUser({
        username: modal.value.username,
        password: modal.value.password,
        role: modal.value.role,
      })
    }
    modal.value.show = false
    toast.success('保存成功')
    await loadUsers()
  } catch (e: any) {
    toast.error(`保存失败: ${e.response?.data?.detail || e.message}`)
  }
}

async function toggleActive(u: any) {
  if (u.id === currentUserId.value) {
    toast.error('不能禁用自己的账号')
    return
  }
  try {
    await userApi.updateUser(u.id, { is_active: !u.is_active })
    toast.success(u.is_active ? '已禁用该用户' : '已启用该用户')
    await loadUsers()
  } catch (e: any) {
    toast.error(`操作失败: ${e.response?.data?.detail || e.message}`)
  }
}

async function confirmDelete(u: any) {
  if (u.id === currentUserId.value) return
  const ok = await toast.confirm({
    title: '删除用户',
    message: `确定要删除用户「${u.username}」吗？此操作不可撤销。`,
    confirmText: '删除',
    danger: true,
  })
  if (!ok) return
  try {
    await userApi.deleteUser(u.id)
    toast.success('已删除')
    await loadUsers()
  } catch (e: any) {
    toast.error(`删除失败: ${e.response?.data?.detail || e.message}`)
  }
}

async function loadUsers() {
  try {
    const { data } = await userApi.listUsers()
    users.value = Array.isArray(data) ? data : data.items || []
  } catch (e) {
    console.error('加载用户列表失败:', e)
  }
}

onMounted(async () => {
  try {
    const { data } = await authApi.getMe()
    currentUserId.value = data.id
  } catch {}
  await loadUsers()
})
</script>
