<template>
  <div class="p-4 md:p-6 max-w-5xl mx-auto space-y-6">
    <!-- 页面标题 -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold">用户配置文件</h1>
        <p class="text-sm mt-1" style="color: var(--text-muted)">为用户创建不同场景的配置文件（儿童模式、影院模式等），控制内容分级和媒体库访问权限</p>
      </div>
      <button @click="openCreate" class="btn-primary flex items-center gap-2">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
        </svg>
        创建 Profile
      </button>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="space-y-3">
      <div v-for="i in 3" :key="i" class="card p-5 animate-pulse">
        <div class="flex items-center gap-4">
          <div class="w-12 h-12 rounded-full bg-[var(--bg-hover)]" />
          <div class="flex-1 space-y-2">
            <div class="h-4 bg-[var(--bg-hover)] rounded w-32" />
            <div class="h-3 bg-[var(--bg-hover)] rounded w-48" />
          </div>
        </div>
      </div>
    </div>

    <!-- Profile 列表 -->
    <div v-else-if="profiles.length > 0" class="space-y-3">
      <div
        v-for="profile in profiles" :key="profile.id"
        class="card p-5 rounded-2xl flex items-start gap-4 hover:border-brand-400/50 transition-colors"
      >
        <!-- 头像 -->
        <div class="w-12 h-12 rounded-full flex items-center justify-center text-lg font-bold shrink-0"
          :style="{ background: `hsl(${profile.id * 47 % 360}, 60%, 35%)` }"
        >
          {{ profile.name[0]?.toUpperCase() }}
        </div>

        <!-- 信息 -->
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="font-semibold">{{ profile.name }}</span>
            <span v-if="profile.is_default" class="badge badge-brand text-xs">默认</span>
            <span v-if="profile.allow_adult" class="badge text-xs" style="background: rgba(239,68,68,0.15); color: #ef4444">成人内容</span>
            <span v-if="profile.require_pin" class="badge text-xs" style="background: rgba(245,158,11,0.15); color: #f59e0b">
              🔒 PIN 保护
            </span>
          </div>
          <div class="text-sm mt-1 flex flex-wrap gap-3" style="color: var(--text-muted)">
            <span v-if="profile.content_rating_limit">分级限制: <strong>{{ profile.content_rating_limit }}</strong></span>
            <span>用户 ID: {{ profile.user_id }}</span>
            <span v-if="profile.allowed_library_ids?.length">
              媒体库: {{ profile.allowed_library_ids.join(', ') }}
            </span>
            <span v-else>媒体库: 全部</span>
          </div>
          <!-- 统计 -->
          <div class="flex gap-4 mt-2 text-xs" style="color: var(--text-muted)">
            <span>观看时长: {{ formatDuration(profile.total_watch_time) }}</span>
            <span v-if="profile.last_active">最近活跃: {{ formatDate(profile.last_active) }}</span>
          </div>
        </div>

        <!-- 操作 -->
        <div class="flex gap-2 shrink-0">
          <button @click="viewUsage(profile)" class="btn-ghost text-xs" title="使用统计">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
            </svg>
          </button>
          <button @click="editProfile(profile)" class="btn-ghost text-xs" title="编辑">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
            </svg>
          </button>
          <button @click="deleteProfile(profile.id)" class="btn-ghost text-xs text-red-400" title="删除">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="card p-10 text-center rounded-2xl">
      <div class="text-4xl mb-3">👤</div>
      <div class="font-semibold mb-1">暂无配置文件</div>
      <p class="text-sm" style="color: var(--text-muted)">为用户创建不同场景的 Profile，实现精细化权限控制</p>
      <button @click="openCreate" class="btn-primary mt-4">创建第一个 Profile</button>
    </div>

    <!-- 确认弹窗 -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showConfirm" class="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="showConfirm = false" />
          <div class="relative card rounded-2xl w-full max-w-sm p-6 space-y-4" style="background: var(--bg-card)">
            <div class="text-lg font-semibold">确认删除</div>
            <p class="text-sm" style="color: var(--text-muted)">{{ confirmMessage }}</p>
            <div class="flex gap-3 justify-end">
              <button @click="showConfirm = false" class="btn-ghost">取消</button>
              <button @click="executeConfirm" class="btn-primary bg-red-500 hover:bg-red-600">确认删除</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Toast -->
    <Teleport to="body">
      <Transition name="toast">
        <div v-if="toast.show" class="fixed top-4 right-4 z-50 card px-4 py-3 rounded-xl text-sm shadow-xl flex items-center gap-2"
          :class="toast.success ? 'border-green-500/40 text-green-400' : 'border-red-500/40 text-red-400'">
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path v-if="toast.success" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
            <path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
          {{ toast.msg }}
        </div>
      </Transition>
    </Teleport>

    <!-- 创建/编辑弹窗 -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showForm" class="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="showForm = false" />
          <div class="relative card rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto" style="background: var(--bg-card)">
            <div class="flex items-center justify-between px-6 py-4 border-b sticky top-0 z-10" style="border-color: var(--border-color); background: var(--bg-card)">
              <h3 class="font-semibold">{{ editingId ? '编辑 Profile' : '创建 Profile' }}</h3>
              <button @click="showForm = false" class="btn-ghost text-gray-400">
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                </svg>
              </button>
            </div>
            <div class="p-6 space-y-4">
              <!-- 用户 ID（创建时） -->
              <div v-if="!editingId">
                <label class="label">用户 ID *</label>
                <input v-model.number="form.user_id" type="number" class="input w-full" placeholder="输入用户 ID" />
              </div>
              <!-- 名称 -->
              <div>
                <label class="label">Profile 名称 *</label>
                <input v-model="form.name" class="input w-full" placeholder="如：儿童模式、影院模式" maxlength="50" />
              </div>
              <!-- 默认 Profile -->
              <div class="flex items-center justify-between">
                <div>
                  <div class="text-sm font-medium">设为默认 Profile</div>
                  <div class="text-xs mt-0.5" style="color: var(--text-muted)">用户登录后默认使用此 Profile</div>
                </div>
                <input type="checkbox" v-model="form.is_default" class="toggle" />
              </div>
              <!-- 内容分级 -->
              <div>
                <label class="label">内容分级限制</label>
                <select v-model="form.content_rating_limit" class="input w-full">
                  <option value="">不限制</option>
                  <option v-for="r in ratings" :key="r.value" :value="r.value">{{ r.label }}</option>
                </select>
              </div>
              <!-- 成人内容 -->
              <div class="flex items-center justify-between">
                <div>
                  <div class="text-sm font-medium">允许成人内容</div>
                  <div class="text-xs mt-0.5" style="color: var(--text-muted)">开启后可访问 R/NC-17 级别内容</div>
                </div>
                <input type="checkbox" v-model="form.allow_adult" class="toggle" />
              </div>
              <!-- PIN 保护 -->
              <div class="flex items-center justify-between">
                <div>
                  <div class="text-sm font-medium">切换时需要 PIN</div>
                  <div class="text-xs mt-0.5" style="color: var(--text-muted)">切换到此 Profile 需要输入 PIN 码</div>
                </div>
                <input type="checkbox" v-model="form.require_pin" class="toggle" />
              </div>
              <div v-if="form.require_pin">
                <label class="label">PIN 码（4-8位数字）</label>
                <input v-model="form.pin" type="password" class="input w-full" placeholder="设置 PIN 码" maxlength="8" />
              </div>
              <!-- 字幕/音频语言 -->
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="label">首选字幕语言</label>
                  <select v-model="form.preferred_subtitle_lang" class="input w-full">
                    <option value="">跟随系统</option>
                    <option value="zh">中文</option>
                    <option value="zh-CN">简体中文</option>
                    <option value="en">English</option>
                    <option value="ja">日语</option>
                  </select>
                </div>
                <div>
                  <label class="label">首选音频语言</label>
                  <select v-model="form.preferred_audio_lang" class="input w-full">
                    <option value="">跟随系统</option>
                    <option value="zh">中文</option>
                    <option value="ja">日语</option>
                    <option value="en">English</option>
                  </select>
                </div>
              </div>
              <!-- 播放选项 -->
              <div class="flex items-center justify-between">
                <div class="text-sm font-medium">自动播放下一集</div>
                <input type="checkbox" v-model="form.autoplay_next" class="toggle" />
              </div>
              <div class="flex items-center justify-between">
                <div class="text-sm font-medium">自动跳过片头</div>
                <input type="checkbox" v-model="form.skip_intro" class="toggle" />
              </div>
            </div>
            <div class="flex justify-end gap-3 px-6 py-4 border-t" style="border-color: var(--border-color)">
              <button @click="showForm = false" class="btn-ghost">取消</button>
              <button @click="saveProfile" :disabled="saving" class="btn-primary">
                {{ saving ? '保存中...' : (editingId ? '更新' : '创建') }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- 使用统计弹窗 -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showUsage" class="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="showUsage = false" />
          <div class="relative card rounded-2xl w-full max-w-md" style="background: var(--bg-card)">
            <div class="flex items-center justify-between px-6 py-4 border-b" style="border-color: var(--border-color)">
              <h3 class="font-semibold">{{ usageData?.profile_name }} - 使用统计</h3>
              <button @click="showUsage = false" class="btn-ghost text-gray-400">✕</button>
            </div>
            <div v-if="usageData" class="p-6 space-y-4">
              <!-- 统计数字 -->
              <div class="grid grid-cols-3 gap-3">
                <div class="card p-3 text-center rounded-xl">
                  <div class="text-xl font-bold text-brand-400">{{ usageData.statistics.total_watch_sessions }}</div>
                  <div class="text-xs mt-0.5" style="color: var(--text-muted)">播放次数</div>
                </div>
                <div class="card p-3 text-center rounded-xl">
                  <div class="text-xl font-bold text-green-400">{{ usageData.statistics.completed_count }}</div>
                  <div class="text-xs mt-0.5" style="color: var(--text-muted)">完整看完</div>
                </div>
                <div class="card p-3 text-center rounded-xl">
                  <div class="text-xl font-bold text-purple-400">{{ usageData.statistics.total_watch_formatted }}</div>
                  <div class="text-xs mt-0.5" style="color: var(--text-muted)">总时长</div>
                </div>
              </div>
              <!-- 完成率 -->
              <div>
                <div class="flex justify-between text-sm mb-1">
                  <span>完成率</span>
                  <span>{{ usageData.statistics.completion_rate }}%</span>
                </div>
                <div class="w-full bg-[var(--bg-hover)] rounded-full h-2">
                  <div class="bg-brand-500 h-2 rounded-full" :style="{ width: usageData.statistics.completion_rate + '%' }" />
                </div>
              </div>
              <!-- 最近观看 -->
              <div v-if="usageData.recent_watches?.length > 0">
                <div class="text-sm font-medium mb-2">最近观看</div>
                <div class="space-y-2">
                  <div v-for="w in usageData.recent_watches" :key="w.media_item_id" class="flex items-center gap-3 text-sm">
                    <div class="flex-1 truncate">{{ w.media_title || `媒体 #${w.media_item_id}` }}</div>
                    <div class="text-xs" style="color: var(--text-muted)">{{ w.progress_pct }}%</div>
                    <span v-if="w.completed" class="text-xs text-green-400">✓</span>
                  </div>
                </div>
              </div>
              <div v-else class="text-center text-sm py-2" style="color: var(--text-muted)">暂无观看记录</div>
            </div>
            <div v-else class="p-8 text-center">
              <div class="animate-spin w-8 h-8 rounded-full border-2 border-brand-400 border-t-transparent mx-auto" />
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api/client'

interface Profile {
  id: number
  user_id: number
  name: string
  avatar?: string
  is_default: boolean
  is_active: boolean
  content_rating_limit?: string
  allow_adult: boolean
  require_pin: boolean
  allowed_library_ids: number[]
  preferred_subtitle_lang?: string
  preferred_audio_lang?: string
  autoplay_next: boolean
  skip_intro: boolean
  total_watch_time: number
  last_active?: string
}

// 状态
const profiles = ref<Profile[]>([])
const loading = ref(false)
const saving = ref(false)
const showForm = ref(false)
const showUsage = ref(false)
const showConfirm = ref(false)
const confirmAction = ref<(() => void) | null>(null)
const confirmMessage = ref('')
const editingId = ref<number | null>(null)
const usageData = ref<any>(null)
const toast = ref({ show: false, msg: '', success: true })

const ratings = [
  { value: 'G', label: 'G - 适合所有年龄' },
  { value: 'PG', label: 'PG - 家长指导建议' },
  { value: 'PG-13', label: 'PG-13 - 13岁以下谨慎' },
  { value: 'R', label: 'R - 17岁以下家长陪同' },
  { value: 'NC-17', label: 'NC-17 - 仅限成人' },
]

const form = ref({
  user_id: 1,
  name: '',
  is_default: false,
  content_rating_limit: '',
  allow_adult: false,
  require_pin: false,
  pin: '',
  preferred_subtitle_lang: '',
  preferred_audio_lang: '',
  autoplay_next: true,
  skip_intro: false,
  allowed_library_ids: [] as number[],
})

function showToast(msg: string, success = true) {
  toast.value = { show: true, msg, success }
  setTimeout(() => { toast.value.show = false }, 3000)
}

function formatDuration(seconds: number): string {
  if (!seconds) return '0 分钟'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return h > 0 ? `${h} 小时 ${m} 分钟` : `${m} 分钟`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

async function loadProfiles() {
  loading.value = true
  try {
    const resp = await api.get('/api/admin/profiles')
    const data = (resp.data as any)?.data || resp.data
    profiles.value = Array.isArray(data) ? data : []
  } catch {
    showToast('加载配置文件失败', false)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.value = { user_id: 1, name: '', is_default: false, content_rating_limit: '', allow_adult: false, require_pin: false, pin: '', preferred_subtitle_lang: '', preferred_audio_lang: '', autoplay_next: true, skip_intro: false, allowed_library_ids: [] }
  showForm.value = true
}

function editProfile(p: Profile) {
  editingId.value = p.id
  form.value = {
    user_id: p.user_id,
    name: p.name,
    is_default: p.is_default,
    content_rating_limit: p.content_rating_limit || '',
    allow_adult: p.allow_adult,
    require_pin: p.require_pin,
    pin: '',
    preferred_subtitle_lang: p.preferred_subtitle_lang || '',
    preferred_audio_lang: p.preferred_audio_lang || '',
    autoplay_next: p.autoplay_next,
    skip_intro: p.skip_intro,
    allowed_library_ids: p.allowed_library_ids || [],
  }
  showForm.value = true
}

async function saveProfile() {
  if (!form.value.name) { showToast('名称不能为空', false); return }
  saving.value = true
  try {
    const payload = { ...form.value }
    if (!payload.content_rating_limit) delete (payload as any).content_rating_limit
    if (!payload.pin) delete (payload as any).pin
    if (!payload.preferred_subtitle_lang) delete (payload as any).preferred_subtitle_lang
    if (!payload.preferred_audio_lang) delete (payload as any).preferred_audio_lang

    if (editingId.value) {
      await api.put(`/api/admin/profiles/${editingId.value}`, payload)
      showToast('Profile 已更新')
    } else {
      await api.post('/api/admin/profiles', payload)
      showToast('Profile 创建成功')
    }
    showForm.value = false
    await loadProfiles()
  } catch (e: any) {
    showToast(e.response?.data?.detail || '保存失败', false)
  } finally {
    saving.value = false
  }
}

function deleteProfile(id: number) {
  confirmMessage.value = '确定删除此 Profile？此操作不可撤销。'
  confirmAction.value = async () => {
    try {
      await api.delete(`/api/admin/profiles/${id}`)
      showToast('Profile 已删除')
      await loadProfiles()
    } catch (e: any) {
      showToast(e.response?.data?.detail || '删除失败', false)
    }
  }
  showConfirm.value = true
}

async function executeConfirm() {
  showConfirm.value = false
  if (confirmAction.value) {
    await confirmAction.value()
  }
}

async function viewUsage(p: Profile) {
  showUsage.value = true
  usageData.value = null
  try {
    const resp = await api.get(`/api/admin/profiles/${p.id}/usage`)
    usageData.value = (resp.data as any)?.data || resp.data
  } catch {
    showToast('加载使用统计失败', false)
  }
}

onMounted(loadProfiles)
</script>

<style scoped>
.modal-enter-active, .modal-leave-active { transition: all 0.2s ease; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-from .card, .modal-leave-to .card { transform: scale(0.96); }
.toast-enter-active, .toast-leave-active { transition: all 0.3s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(-8px); }
.label { display: block; font-size: 0.8rem; font-weight: 500; margin-bottom: 0.25rem; color: var(--text-muted); }
.toggle { width: 2.5rem; height: 1.25rem; cursor: pointer; }
.badge { padding: 2px 8px; border-radius: 9999px; }
.badge-brand { background: rgba(99,102,241,0.15); color: #818cf8; }
</style>
