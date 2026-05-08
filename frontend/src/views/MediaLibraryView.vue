<template>
  <div class="p-4 md:p-6 max-w-7xl mx-auto space-y-6">
    <!-- 顶部栏：标题 + 全局搜索 -->
    <div class="flex flex-wrap items-center gap-3">
      <h1 class="text-2xl font-bold shrink-0">媒体库</h1>
      <!-- 独立搜索栏 -->
      <div class="flex-1 min-w-[200px] max-w-md">
        <div class="relative">
          <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none" style="color: var(--text-faint)" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
          <input v-model="filters.search" @input="debounceSearch"
            class="input w-full text-sm !pl-9 pr-4 py-2"
            placeholder="搜索电影、电视剧、动漫..." />
          <button v-if="filters.search" @click="clearSearch"
            class="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded-full hover:bg-[var(--bg-hover)] transition-colors"
            style="color: var(--text-faint)">
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
      </div>
      <div class="flex-1" />
      <!-- 筛选切换 -->
      <button @click="showFilters = !showFilters"
        :class="['text-sm px-3 py-2 rounded-lg border transition-colors flex items-center gap-1.5 shrink-0',
          showFilters ? 'border-brand-500/50 text-brand-400 bg-brand-500/10' : 'border-[var(--border-primary)] text-[var(--text-secondary)] hover:text-white']">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"/></svg>
        筛选
        <span v-if="activeFilterCount > 0" class="min-w-[18px] h-[18px] bg-brand-500 text-white text-[10px] rounded-full flex items-center justify-center font-medium">{{ activeFilterCount }}</span>
      </button>
    </div>

    <!-- 高级筛选面板（不含搜索） -->
    <Transition name="expand">
      <div v-if="showFilters" class="card p-4 space-y-4">
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <!-- 类型 -->
          <div>
            <label class="block text-xs mb-1" style="color: var(--text-muted)">类型</label>
            <select v-model="filters.media_type" @change="onFilterChange" class="input w-full text-sm">
              <option value="">全部</option>
              <option value="movie">电影</option>
              <option value="tv">电视剧</option>
              <option value="anime">动漫</option>
            </select>
          </div>
          <!-- 排序 -->
          <div>
            <label class="block text-xs mb-1" style="color: var(--text-muted)">排序</label>
            <select v-model="filters.sort_by" @change="onFilterChange" class="input w-full text-sm">
              <option value="date_added">最近添加</option>
              <option value="rating">评分最高</option>
              <option value="year">年份</option>
              <option value="title">标题 A-Z</option>
              <option value="size_bytes">文件大小</option>
            </select>
          </div>
          <!-- 年份范围 -->
          <div>
            <label class="block text-xs mb-1" style="color: var(--text-muted)">起始年份</label>
            <input v-model.number="filters.year_min" type="number" placeholder="如 2020"
              @change="onFilterChange" class="input w-full text-sm" min="1900" max="2030" />
          </div>
          <div>
            <label class="block text-xs mb-1" style="color: var(--text-muted)">结束年份</label>
            <input v-model.number="filters.year_max" type="number" placeholder="如 2026"
              @change="onFilterChange" class="input w-full text-sm" min="1900" max="2030" />
          </div>
          <!-- 最低评分 -->
          <div>
            <label class="block text-xs mb-1" style="color: var(--text-muted)">最低评分 ({{ filters.rating_min || '不限' }})</label>
            <input v-model.number="filters.rating_min" type="range" min="0" max="10" step="0.5"
              @input="onFilterChange" class="w-full accent-brand-500 cursor-pointer" />
          </div>
          <!-- 类型标签（可选） -->
          <div>
            <label class="block text-xs mb-1" style="color: var(--text-muted)">类型标签</label>
            <input v-model="filters.genre" placeholder="动作/科幻/爱情..."
              @input="debounceSearch" class="input w-full text-sm" />
          </div>
        </div>
        <!-- 筛选操作 -->
        <div class="flex items-center justify-between pt-2 border-t border-[var(--border-primary)]">
          <span class="text-xs" style="color: var(--text-faint)">
            共 {{ total }} 条结果
            <span v-if="activeFilterCount > 0"> · 已启用 {{ activeFilterCount }} 个筛选</span>
          </span>
          <button v-if="activeFilterCount > 0" @click="resetFilters" class="text-xs text-brand-400 hover:text-brand-300 transition-colors">
            重置全部
          </button>
        </div>
      </div>
    </Transition>

    <!-- 媒体网格 -->
    <div v-if="loading" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3 md:gap-4">
      <div v-for="i in 12" :key="i" class="animate-pulse">
        <div class="rounded-lg aspect-[2/3] bg-[var(--bg-input)]" />
        <div class="h-4 bg-[var(--bg-input)] rounded mt-2 w-3/4" />
        <div class="h-3 bg-[var(--bg-input)] rounded mt-1 w-1/2" />
      </div>
    </div>

    <div v-else-if="items.length > 0" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3 md:gap-4 stagger-in">
      <div v-for="(item, index) in items" :key="item.id"
        @click="$router.push(`/media/${item.id}`)"
        class="cursor-pointer group"
        :style="{ '--stagger': index * 30 }">
        <div class="aspect-[2/3] rounded-lg bg-[var(--bg-input)] overflow-hidden relative shadow-md group-hover:shadow-xl transition-all duration-300">
          <img v-if="item.poster_url" :src="item.poster_url" :alt="item.title"
            class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            loading="lazy" referrerpolicy="no-referrer"
            @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />
          <div v-else class="w-full h-full flex items-center justify-center" style="color: var(--text-faint)">
            <svg class="w-16 h-16" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"/></svg>
          </div>
          <div v-if="item.rating" class="absolute top-2 right-2 bg-black/70 text-xs px-1.5 py-0.5 rounded text-yellow-400 backdrop-blur-sm">
            ★ {{ item.rating.toFixed(1) }}
          </div>
          <!-- 类型角标 -->
          <div class="absolute top-2 left-2 text-[10px] font-medium uppercase px-1.5 py-0.5 rounded backdrop-blur-sm"
            :class="{
              'bg-blue-500/80 text-white': item.media_type === 'movie',
              'bg-emerald-500/80 text-white': item.media_type === 'tv',
              'bg-pink-500/80 text-white': item.media_type === 'anime',
            }">
            {{ item.media_type === 'movie' ? '电影' : item.media_type === 'tv' ? '剧' : '漫' }}
          </div>
          <!-- 悬浮播放图标 -->
          <div class="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors duration-300 flex items-center justify-center">
            <div class="w-12 h-12 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 scale-75 group-hover:scale-100 transition-all duration-300">
              <svg class="w-6 h-6 text-white ml-0.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
            </div>
          </div>
        </div>
        <div class="mt-2">
          <div class="text-sm font-medium truncate">{{ item.title }}</div>
          <div class="text-xs" style="color: var(--text-muted)">{{ item.year || '—' }} · {{ item.resolution || '未知' }}</div>
        </div>
      </div>
    </div>

    <div v-else-if="!loading">
      <AppEmpty message="暂无媒体内容，试试调整筛选条件或添加媒体库并扫描" />
    </div>

    <!-- 分页 -->
    <div v-if="totalPages > 1" class="flex justify-center items-center gap-3">
      <button @click="goPage(page - 1)" :disabled="page <= 1"
        class="btn-secondary text-sm disabled:opacity-30">上一页</button>
      <div class="flex items-center gap-1">
        <button v-for="p in visiblePages" :key="p"
          @click="goPage(p)" :disabled="p === page"
          :class="['w-8 h-8 rounded-lg text-sm transition-colors flex items-center justify-center',
            p === page ? 'bg-brand-600 text-white' : 'hover:bg-[var(--bg-hover)] text-[var(--text-secondary)]']">
          {{ p === -1 ? '...' : p }}
        </button>
      </div>
      <span class="text-sm self-center" style="color: var(--text-muted)">{{ page }} / {{ totalPages }}</span>
      <button @click="goPage(page + 1)" :disabled="page >= totalPages"
        class="btn-secondary text-sm disabled:opacity-30">下一页</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { mediaApi } from '@/api/media'
import AppEmpty from '@/components/AppEmpty.vue'

const items = ref<any[]>([])
const loading = ref(true)
const page = ref(1)
const total = ref(0)
const pageSize = 24
const showFilters = ref(false)

const filters = ref({
  media_type: '',
  search: '',
  sort_by: 'date_added',
  sort_order: 'desc' as string,
  genre: '',
  year_min: null as number | null,
  year_max: null as number | null,
  rating_min: null as number | null,
})

const totalPages = computed(() => Math.ceil(total.value / pageSize))

// 计算激活的筛选条件数量（不含搜索）
const activeFilterCount = computed(() => {
  let count = 0
  if (filters.value.media_type) count++
  if (filters.value.genre) count++
  if (filters.value.year_min !== null && filters.value.year_min !== undefined) count++
  if (filters.value.year_max !== null && filters.value.year_max !== undefined) count++
  if (filters.value.rating_min !== null && filters.value.rating_min !== undefined && filters.value.rating_min > 0) count++
  return count
})

// 可见页码（带省略）
const visiblePages = computed(() => {
  const totalP = totalPages.value
  const current = page.value
  if (totalP <= 7) return Array.from({ length: totalP }, (_, i) => i + 1)
  const pages: number[] = []
  pages.push(1)
  if (current > 3) pages.push(-1)
  for (let i = Math.max(2, current - 1); i <= Math.min(totalP - 1, current + 1); i++) {
    pages.push(i)
  }
  if (current < totalP - 2) pages.push(-1)
  pages.push(totalP)
  return pages
})

let searchTimer: any

function debounceSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { page.value = 1; loadItems() }, 300)
}

function clearSearch() {
  filters.value.search = ''
  page.value = 1
  loadItems()
}

function onFilterChange() {
  page.value = 1
  loadItems()
}

function resetFilters() {
  filters.value = {
    media_type: '', search: '', sort_by: 'date_added', sort_order: 'desc',
    genre: '', year_min: null, year_max: null, rating_min: null,
  }
  page.value = 1
  loadItems()
}

function goPage(p: number) {
  if (p >= 1 && p <= totalPages.value) loadItems(p)
}

async function loadItems(p?: number) {
  if (p) page.value = p
  loading.value = true
  try {
    const params: Record<string, any> = {
      page: page.value, page_size: pageSize,
      sort_by: filters.value.sort_by, sort_order: filters.value.sort_order,
    }
    if (filters.value.media_type) params.media_type = filters.value.media_type
    if (filters.value.search) params.search = filters.value.search
    if (filters.value.genre) params.genre = filters.value.genre
    if (filters.value.year_min != null) params.year_min = filters.value.year_min
    if (filters.value.year_max != null) params.year_max = filters.value.year_max
    if (filters.value.rating_min != null) params.rating_min = filters.value.rating_min
    const { data } = await mediaApi.getItems(params)
    items.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(() => loadItems())
</script>

<style scoped>
.expand-enter-active, .expand-leave-active {
  transition: all 0.25s ease;
  overflow: hidden;
}
.expand-enter-from, .expand-leave-to {
  opacity: 0;
  max-height: 0;
}
.expand-enter-to, .expand-leave-from {
  opacity: 1;
  max-height: 250px;
}
</style>
