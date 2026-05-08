<template>
  <div class="space-y-6">
    <!-- 当前账号信息 -->
    <div class="card p-5">
      <h3 class="font-semibold mb-4">账号信息</h3>
      <div class="flex items-center gap-5">
        <!-- 头像 -->
        <div class="relative shrink-0">
          <div class="w-20 h-20 rounded-full overflow-hidden bg-[var(--bg-input)] flex items-center justify-center ring-2 ring-[var(--border-primary)]">
            <img v-if="currentUser?.avatar" :src="currentUser.avatar" :alt="currentUser.username"
              class="w-full h-full object-cover" />
            <span v-else class="text-2xl font-bold text-brand-500">{{ (currentUser?.username || '?').charAt(0).toUpperCase() }}</span>
          </div>
          <button @click="avatarInput?.click()" title="更换头像"
            class="absolute bottom-0 right-0 w-6 h-6 bg-brand-500 rounded-full flex items-center justify-center hover:bg-brand-400 transition-colors shadow-lg">
            <svg class="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M15.232 5.232l3.536 3.536M9 11l6-6 3 3-6 6H9v-3z"/>
            </svg>
          </button>
          <input ref="avatarInput" type="file" accept="image/*" class="hidden" @change="onAvatarChange" />
        </div>
        <div class="space-y-1 flex-1 min-w-0">
          <!-- 昵称（可编辑） -->
          <div class="flex items-center gap-2">
            <input v-if="editingNickname" ref="nicknameInput" v-model="nicknameDraft"
              @blur="saveNickname" @keyup.enter="saveNickname"
              class="font-semibold text-lg bg-transparent border-b border-brand-500 outline-none px-1 py-0.5 max-w-xs truncate"
              maxlength="20" placeholder="输入昵称" />
            <span v-else @click="startEditNickname" class="font-semibold text-lg cursor-pointer hover:text-brand-400 transition-colors truncate max-w-xs inline-block">
              {{ currentUser?.nickname || currentUser?.username }}
              <svg class="w-3.5 h-3.5 ml-1 inline opacity-40 hover:opacity-100" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.432-9.864L12 7l-6.336 1.096 8.464 2.432L12 17l2.304-5.472z"/></svg>
            </span>
          </div>
          <div class="text-sm" style="color: var(--text-muted)">@{{ currentUser?.username }}</div>
          <div class="text-sm mt-1">
            <span :class="['px-2 py-0.5 rounded text-xs', currentUser?.role === 'admin' ? 'bg-brand-500/15 text-brand-400' : 'bg-[var(--bg-input)] text-[var(--text-muted)]']">
              {{ currentUser?.role === 'admin' ? '管理员' : '普通用户' }}
            </span>
            <span class="ml-2 text-xs" style="color: var(--text-faint)">
              注册于 {{ currentUser?.created_at ? formatDate(currentUser.created_at, 'date') : '—' }}
            </span>
          </div>
          <div class="text-xs mt-1" style="color: var(--text-faint)">
            最后登录：{{ currentUser?.last_login ? formatDate(currentUser.last_login) : '—' }}
          </div>
        </div>
    </div>
    <p v-if="avatarSaving || nicknameSaving" class="mt-3 text-sm text-brand-400 animate-pulse">
      {{ avatarSaving ? '正在保存头像...' : '正在更新昵称...' }}
    </p>
  </div>

  <!-- 授权状态 -->
  <div class="card p-5" v-if="licenseStatus !== null">
    <div class="flex items-center justify-between mb-3">
      <h3 class="font-semibold flex items-center gap-2">
        <span :class="licenseStatus?.is_plus ? 'text-emerald-400' : 'text-amber-400'">
          {{ licenseStatus?.is_plus ? '✦' : '○' }}
        </span>
        授权状态
      </h3>
      <span v-if="licenseStatus?.is_plus" 
        class="text-xs px-2.5 py-1 rounded-full"
        :class="licenseStatus.license_type === 'permanent' ? 'bg-brand-500/10 text-brand-400' : 'bg-amber-500/10 text-amber-400'">
        {{ licenseStatus.license_type === 'permanent' ? '永久授权' : '订阅授权' }}
      </span>
    </div>
    <div v-if="licenseStatus?.is_plus" class="grid grid-cols-2 gap-4 text-sm">
      <div v-if="licenseStatus.expiry_date">
        <div class="text-xs mb-0.5" style="color: var(--text-faint)">到期时间</div>
        <div>{{ formatDate(licenseStatus.expiry_date, 'full') }}</div>
      </div>
      <div v-if="licenseStatus.days_remaining != null">
        <div class="text-xs mb-0.5" style="color: var(--text-faint)">剩余天数</div>
        <div :style="{ color: licenseStatus.days_remaining < 30 ? '#f87171' : '' }">
          {{ licenseStatus.days_remaining }} 天
        </div>
      </div>
      <div>
        <div class="text-xs mb-0.5" style="color: var(--text-faint)">绑定设备</div>
        <div>{{ licenseStatus.device_name || '未知设备' }}</div>
      </div>
    </div>
    <div v-else class="text-sm" style="color: var(--text-muted)">
      当前为免费版。购买 Plus 版可解锁所有功能并无限制创建用户。
    </div>
  </div>

  <!-- 观看统计 -->
    <div class="card p-5" v-if="statsLoaded">
      <h3 class="font-semibold mb-4">观看统计</h3>
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div class="text-center p-3 rounded-lg bg-[var(--bg-hover)]">
          <div class="text-2xl font-bold text-brand-400">{{ stats.total_watched }}</div>
          <div class="text-xs mt-1" style="color: var(--text-muted)">观看过</div>
        </div>
        <div class="text-center p-3 rounded-lg bg-[var(--bg-hover)]">
          <div class="text-2xl font-bold text-emerald-400">{{ stats.total_duration_str }}</div>
          <div class="text-xs mt-1" style="color: var(--text-muted)">观看时长</div>
        </div>
        <div class="text-center p-3 rounded-lg bg-[var(--bg-hover)]">
          <div class="text-2xl font-bold text-yellow-400">{{ stats.favorite_count }}</div>
          <div class="text-xs mt-1" style="color: var(--text-muted)">收藏数</div>
        </div>
        <div class="text-center p-3 rounded-lg bg-[var(--bg-hover)]">
          <div class="text-2xl font-bold text-violet-400">{{ stats.streak_days }}</div>
          <div class="text-xs mt-1" style="color: var(--text-muted)">连续天数</div>
        </div>
      </div>
    </div>

    <!-- 修改密码 -->
    <div class="card p-5">
      <h3 class="font-semibold mb-4">修改密码</h3>
      <div class="space-y-3 max-w-sm">
        <div>
          <label class="block text-sm mb-1" style="color: var(--text-muted)">当前密码</label>
          <div class="relative">
            <input v-model="pw.old" :type="pw.showOld ? 'text' : 'password'" class="input pr-10" placeholder="••••••••" />
            <button type="button" @click="pw.showOld = !pw.showOld" class="absolute right-3 top-1/2 -translate-y-1/2" style="color: var(--text-muted)">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path v-if="pw.showOld" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"/><path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>
            </button>
          </div>
        </div>
        <div>
          <label class="block text-sm mb-1" style="color: var(--text-muted)">新密码</label>
          <div class="relative">
            <input v-model="pw.new1" :type="pw.showNew ? 'text' : 'password'" class="input pr-10" placeholder="至少 6 位" />
            <button type="button" @click="pw.showNew = !pw.showNew" class="absolute right-3 top-1/2 -translate-y-1/2" style="color: var(--text-muted)">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path v-if="pw.showNew" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"/><path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>
            </button>
          </div>
        </div>
        <div>
          <label class="block text-sm mb-1" style="color: var(--text-muted)">确认新密码</label>
          <input v-model="pw.new2" type="password" class="input" placeholder="再次输入新密码" @keyup.enter="changePassword" />
          <p v-if="pw.new1 && pw.new2 && pw.new1 !== pw.new2" class="mt-1 text-xs text-red-400">两次密码不一致</p>
        </div>
        <div class="flex items-center gap-3 pt-1">
          <button @click="changePassword" :disabled="pwSaving || !pw.old || !pw.new1 || !pw.new2 || pw.new1 !== pw.new2"
            class="btn-primary text-sm disabled:opacity-50">
            {{ pwSaving ? '保存中...' : '修改密码' }}
          </button>
          <span v-if="pwResult" :class="['text-sm transition-opacity', pwResult.ok ? 'text-green-400' : 'text-red-400']">
            {{ pwResult.msg }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { authApi } from '@/api/auth'
import { mediaApi } from '@/api/media'
import { licenseApi } from '@/api/license'
import { useToast } from '@/composables/useToast'

const toast = useToast()

const currentUser = ref<any>(null)
const avatarInput = ref<HTMLInputElement>()
const avatarSaving = ref(false)
const nicknameSaving = ref(false)
const editingNickname = ref(false)
const nicknameDraft = ref('')
const nicknameInput = ref<HTMLInputElement>()

// 授权状态
const licenseStatus = ref<any>(null)

// 观看统计
const statsLoaded = ref(false)
const stats = ref<any>({
  total_watched: 0,
  total_duration: 0,
  total_duration_str: '0h',
  favorite_count: 0,
  streak_days: 0,
})

const pw = ref({ old: '', new1: '', new2: '', showOld: false, showNew: false })
const pwSaving = ref(false)
const pwResult = ref<{ ok: boolean; msg: string } | null>(null)

function formatDate(d: string, mode: string = 'full') {
  const dt = new Date(d)
  if (mode === 'date') return dt.toLocaleDateString('zh-CN')
  return dt.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function formatDuration(seconds: number): string {
  if (!seconds) return '0h'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

async function loadMe() {
  try {
    const { data } = await authApi.getMe()
    currentUser.value = data
    // 加载统计和授权状态
    loadStats()
    loadLicenseStatus()
  } catch (e) {
    console.error('Failed to load user', e)
  }
}

async function loadStats() {
  try {
    const api = (await import('@/api/client')).default
    // 并行获取收藏数和历史记录数
    const [favRes, histRes] = await Promise.allSettled([
      mediaApi.getFavorites({ page: 1, page_size: 1 }).catch(() => ({ data: { total: 0 } })),
      api.get('/api/watch-history?limit=1000').catch(() => ({ data: [] })),
    ])
    let favCount = 0
    let watchedCount = new Set<number>()
    let totalDuration = 0

    if (favRes.status === 'fulfilled') {
      favCount = (favRes.value as any).data?.total || 0
    }
    if (histRes.status === 'fulfilled') {
      const items = (histRes.value as any).data || []
      for (const item of items) {
        if (item.media_item_id && item.duration > 0) watchedCount.add(item.media_item_id)
        if (item.progress > 0) totalDuration += Math.min(item.progress, item.duration || item.progress)
      }
    }

    stats.value = {
      total_watched: watchedCount.size,
      total_duration: totalDuration,
      total_duration_str: formatDuration(totalDuration),
      favorite_count: favCount,
      streak_days: '-',  // TODO: 实际计算连续观看天数
    }
    statsLoaded.value = true
  } catch (e) {
    console.error('Failed to load stats', e)
  }
}

async function loadLicenseStatus() {
  try {
    const { data } = await licenseApi.getStatus()
    licenseStatus.value = data
  } catch (e) {
    console.error('Failed to load license status', e)
  }
}

async function onAvatarChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  if (file.size > 2 * 1024 * 1024) {
    toast.error('头像文件不能超过 2MB')
    return
  }
  avatarSaving.value = true
  try {
    const reader = new FileReader()
    reader.readAsDataURL(file)
    reader.onload = async () => {
      const b64 = reader.result as string
      const { data } = await authApi.updateProfile({ avatar: b64 })
      currentUser.value = data
      toast.success('头像已更新')
      avatarSaving.value = false
    }
  } catch (e: any) {
    toast.error(`上传失败: ${e.response?.data?.detail || e.message}`)
    avatarSaving.value = false
  }
}

// ── 昵称编辑 ──
function startEditNickname() {
  nicknameDraft.value = currentUser.value?.nickname || ''
  editingNickname.value = true
  nextTick(() => nicknameInput.value?.focus())
}

async function saveNickname() {
  if (!editingNickname.value) return
  const newName = nicknameDraft.value.trim()
  if (!newName || newName === (currentUser.value?.nickname || '')) {
    editingNickname.value = false
    return
  }
  nicknameSaving.value = true
  try {
    const { data } = await authApi.updateProfile({ nickname: newName })
    currentUser.value = data
    toast.success('昵称已更新')
  } catch (e: any) {
    toast.error(`更新失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    editingNickname.value = false
    nicknameSaving.value = false
  }
}

async function changePassword() {
  if (!pw.value.old || !pw.value.new1 || pw.value.new1 !== pw.value.new2) return
  pwSaving.value = true
  pwResult.value = null
  try {
    await authApi.changePassword(pw.value.old, pw.value.new1)
    pw.value = { old: '', new1: '', new2: '', showOld: false, showNew: false }
    pwResult.value = { ok: true, msg: '密码已修改' }
    setTimeout(() => { pwResult.value = null }, 4000)
  } catch (e: any) {
    pwResult.value = { ok: false, msg: e.response?.data?.detail || e.message || '修改失败' }
  } finally {
    pwSaving.value = false
  }
}

onMounted(loadMe)
</script>
