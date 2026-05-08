<template>
  <div class="p-4 md:p-6 max-w-7xl mx-auto space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold">观看历史</h1>
      <button v-if="items.length > 0" @click="confirmClear" class="btn-secondary text-sm text-red-400 hover:bg-red-500/10 flex items-center gap-1.5">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
        清空全部
      </button>
    </div>

    <!-- 筛选 -->
    <div class="flex gap-2 flex-wrap">
      <button v-for="f in filters" :key="f.key" @click="activeFilter = f.key as 'all' | 'watching' | 'completed'"
        :class="['text-sm px-3 py-1.5 rounded-full border transition-colors', activeFilter === f.key
          ? 'border-brand-500 bg-brand-500/15 text-brand-400'
          : 'border-[var(--border-primary)] hover:border-brand-500/50']"
        :style="activeFilter !== f.key ? 'color: var(--text-muted)' : ''">
        {{ f.label }}
      </button>
    </div>

    <!-- 加载骨架 -->
    <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="i in 6" :key="i" class="card p-4 animate-pulse">
        <div class="flex gap-3">
          <div class="w-20 h-28 bg-[var(--bg-hover)] rounded shrink-0" />
          <div class="flex-1 space-y-2 pt-1">
            <div class="h-4 bg-[var(--bg-hover)] rounded w-3/4" />
            <div class="h-3 bg-[var(--bg-hover)] rounded w-1/2" />
            <div class="h-3 bg-[var(--bg-hover)] rounded w-full mt-4" />
          </div>
        </div>
      </div>
    </div>

    <!-- 历史记录列表 -->
    <div v-else-if="items.length > 0" class="space-y-3 stagger-in">
      <div v-for="(item, index) in items" :key="item.id"
        class="card p-4 hover:border-[var(--accent)]/50 transition-colors cursor-pointer group animate-in"
        :style="`--stagger: ${index * 30}`"
        @click="$router.push(`/media/${item.media_item_id}`)">
        <div class="flex items-start gap-3">
          <!-- 海报 -->
          <div class="w-20 h-28 rounded-lg overflow-hidden bg-[var(--bg-input)] shrink-0 shadow-md">
            <img v-if="item.poster_url" :src="item.poster_url" :alt="item.media_title"
              class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
              loading="lazy" referrerpolicy="no-referrer"
              @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />
            <div v-else class="w-full h-full flex items-center justify-center" style="color: var(--text-faint)">
              <svg class="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"/></svg>
            </div>
          </div>

          <!-- 信息 -->
          <div class="flex-1 min-w-0 pt-1">
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <div class="text-base font-semibold truncate group-hover:text-brand-400 transition-colors">{{ item.media_title }}</div>
                <div class="flex items-center gap-2 mt-1">
                  <span class="text-xs px-1.5 py-0.5 rounded"
                    :class="{
                      'bg-blue-500/15 text-blue-400': item.media_type === 'movie',
                      'bg-emerald-500/15 text-emerald-400': item.media_type === 'tv',
                      'bg-pink-500/15 text-pink-400': item.media_type === 'anime',
                    }">
                    {{ item.media_type === 'movie' ? '电影' : item.media_type === 'tv' ? '剧集' : '动漫' }}
                  </span>
                  <span v-if="item.completed" class="badge badge-success text-xs">已看完</span>
                  <span class="text-xs" style="color: var(--text-faint)">
                    {{ formatDate(item.last_watched) }}
                  </span>
                </div>
              </div>
              <!-- 删除按钮 -->
              <button @click.stop="deleteItem(item)" title="删除记录"
                class="shrink-0 w-7 h-7 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity text-[var(--text-muted)] hover:text-red-400 hover:bg-red-500/10">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
              </button>
            </div>

            <!-- 进度条 -->
            <div class="mt-3">
              <div class="flex items-center justify-between text-xs mb-1" style="color: var(--text-muted)">
                <span>{{ item.completed ? '已看完' : '观看进度' }}</span>
                <span>{{ formatTime(item.progress) }} / {{ formatTime(item.duration) }}</span>
              </div>
              <div class="progress-bar h-2">
                <div :style="{ width: watchPercent(item) + '%' }"
                  :class="item.completed ? 'bg-emerald-400' : 'bg-brand-400'" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="py-16 text-center">
      <AppEmpty message="还没有观看记录" subMessage="播放一部电影或剧集，记录会自动保存到这里" />
      <router-link to="/media" class="inline-flex items-center gap-2 mt-4 btn-primary text-sm px-4 py-2">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"/></svg>
        去浏览媒体库
      </router-link>
    </div>

    <!-- 分页 -->
    <div v-if="totalPages > 1" class="flex justify-center gap-2">
      <button @click="page > 1 && loadHistory(page - 1)" :disabled="page <= 1"
        class="btn-secondary text-sm disabled:opacity-30">上一页</button>
      <span class="text-sm self-center" style="color: var(--text-muted)">{{ page }} / {{ totalPages }}</span>
      <button @click="page < totalPages && loadHistory(page + 1)" :disabled="page >= totalPages"
        class="btn-secondary text-sm disabled:opacity-30">下一页</button>
    </div>

    <!-- 确认清空弹窗 -->
    <Transition name="fade">
      <div v-if="showClearConfirm" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" @click.self="showClearConfirm = false">
        <div class="card p-6 max-w-sm w-full mx-4 text-center space-y-4">
          <div class="text-lg font-semibold">确定清空全部观看历史？</div>
          <div class="text-sm" style="color: var(--text-muted)">此操作不可恢复，清空后所有观看记录将被永久删除。</div>
          <div class="flex gap-3 justify-center">
            <button @click="showClearConfirm = false" class="btn-secondary">取消</button>
            <button @click="clearAll" :disabled="clearing" class="btn-danger">
              {{ clearing ? '清空中...' : '确认清空' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import AppEmpty from '@/components/AppEmpty.vue'
import { useToast } from '@/composables/useToast'
import { watchHistoryApi } from '@/api/system'

const toast = useToast()

const items = ref<any[]>([])
const loading = ref(true)
const page = ref(1)
const pageSize = 20
const total = ref(0)
const activeFilter = ref<'all' | 'watching' | 'completed'>('all')
const showClearConfirm = ref(false)
const clearing = ref(false)

const totalPages = computed(() => Math.ceil(total.value / pageSize))

const filters = [
  { key: 'all', label: '全部' },
  { key: 'watching', label: '在追' },
  { key: 'completed', label: '已看完' },
]

watch(activeFilter, () => loadHistory(1))

function watchPercent(item: any): number {
  if (!item.duration || item.duration === 0) return item.completed ? 100 : 0
  return Math.min(100, (item.progress / item.duration) * 100)
}

function formatTime(seconds: number): string {
  if (!seconds) return '0:00'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  return `${m}:${s.toString().padStart(2, '0')}`
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '—'
  try {
    const d = new Date(dateStr)
    const now = new Date()
    const diff = now.getTime() - d.getTime()
    const days = Math.floor(diff / 86400000)
    if (days === 0) return '今天'
    if (days === 1) return '昨天'
    if (days < 7) return `${days}天前`
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
  } catch { return '—' }
}

async function loadHistory(p?: number) {
  if (p) page.value = p
  loading.value = true
  try {
    const params: any = { limit: pageSize, offset: (page.value - 1) * pageSize }
    if (activeFilter.value === 'completed') params.completed = true
    if (activeFilter.value === 'watching') params.completed = false

    const res = await watchHistoryApi.getList(params)
    const data = res.data
    items.value = Array.isArray(data) ? data : (data?.items || [])
    total.value = data?.total || items.value.length
  } catch (e) {
    console.error(e)
    items.value = []
  } finally {
    loading.value = false
  }
}

async function deleteItem(item: any) {
  try {
    await watchHistoryApi.deleteItem(item.id)
    items.value = items.value.filter(i => i.id !== item.id)
    toast.info('已删除该记录')
  } catch (e) {
    toast.error('删除失败')
  }
}

function confirmClear() {
  showClearConfirm.value = true
}

async function clearAll() {
  clearing.value = true
  try {
    await watchHistoryApi.clearAll()
    items.value = []
    showClearConfirm.value = false
    toast.info('已清空全部历史记录')
  } catch {
    toast.error('清空失败')
  } finally {
    clearing.value = false
  }
}

onMounted(() => loadHistory())
</script>
