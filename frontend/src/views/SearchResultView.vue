<template>
  <div class="p-4 md:p-6 max-w-7xl mx-auto space-y-6 animate-in">
    <!-- 顶部栏 -->
    <div class="flex flex-wrap items-center gap-3">
      <button @click="$router.back()" class="p-2 rounded-lg hover:bg-[var(--bg-secondary)] transition-colors">
        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
      </button>
      <h1 class="text-2xl font-bold shrink-0">搜索结果</h1>
      <!-- 搜索栏 -->
      <div class="flex-1 min-w-[200px] max-w-md">
        <div class="relative">
          <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none" style="color: var(--text-faint)" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
          <input v-model="searchQuery" @input="handleSearch"
            class="input w-full text-sm !pl-9 pr-4 py-2"
            placeholder="搜索电影、电视剧..." />
        </div>
      </div>
      <span v-if="query" class="text-sm" style="color: var(--text-muted)">
        共找到 <span class="font-bold" style="color: var(--accent)">{{ totalResults }}</span> 个结果
      </span>
    </div>

    <!-- 媒体类型切换 -->
    <div class="flex items-center gap-2">
      <button v-for="type in mediaTypes" :key="type.value"
        @click="switchType(type.value)"
        :class="[
          'px-4 py-1.5 rounded-lg text-sm font-medium transition-all duration-200',
          activeType === type.value
            ? 'bg-brand-600 text-white shadow-sm'
            : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)]'
        ]">
        {{ type.label }}
      </button>
    </div>

    <!-- 高级搜索面板（可折叠） -->
    <div class="card overflow-hidden transition-all duration-300">
      <button
        @click="showAdvanced = !showAdvanced"
        class="w-full flex items-center justify-between px-4 py-3 text-sm font-medium hover:bg-[var(--bg-hover)] transition-colors"
      >
        <div class="flex items-center gap-2">
          <svg class="w-4 h-4" style="color: var(--accent)" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"/>
          </svg>
          <span>高级筛选</span>
          <span v-if="hasActiveFilters" class="text-xs px-2 py-0.5 rounded-full bg-brand-500/20 text-brand-400">已启用</span>
        </div>
        <svg class="w-4 h-4 transition-transform duration-200" :class="showAdvanced ? 'rotate-180' : ''" style="color: var(--text-muted)" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
        </svg>
      </button>

      <Transition name="collapse">
        <div v-if="showAdvanced" class="px-4 pb-4 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 border-t border-[var(--border-primary)]" style="padding-top: 12px">
          <!-- 来源切换 -->
          <div>
            <label class="text-xs mb-1 block" style="color: var(--text-muted)">搜索来源</label>
            <select v-model="searchSource" class="input w-full text-sm py-1.5">
              <option value="tmdb">TMDb（发现）</option>
              <option value="local">本地媒体库</option>
            </select>
          </div>

          <!-- 类型（本地搜索时用） -->
          <div v-if="searchSource === 'local'">
            <label class="text-xs mb-1 block" style="color: var(--text-muted)">类型标签</label>
            <input v-model="filters.genre" @input="debouncedLocalSearch" type="text" class="input w-full text-sm py-1.5" placeholder="如：科幻、动作" />
          </div>

          <!-- 年份范围 -->
          <div v-if="searchSource === 'local'">
            <label class="text-xs mb-1 block" style="color: var(--text-muted)">年份范围</label>
            <div class="flex gap-1">
              <input v-model.number="filters.year_min" @input="debouncedLocalSearch" type="number" class="input w-full text-sm py-1.5" placeholder="起" min="1900" max="2100" />
              <span class="self-center text-[var(--text-muted)]">-</span>
              <input v-model.number="filters.year_max" @input="debouncedLocalSearch" type="number" class="input w-full text-sm py-1.5" placeholder="止" min="1900" max="2100" />
            </div>
          </div>

          <!-- 最低评分 -->
          <div v-if="searchSource === 'local'">
            <label class="text-xs mb-1 block" style="color: var(--text-muted)">最低评分</label>
            <input v-model.number="filters.rating_min" @input="debouncedLocalSearch" type="number" class="input w-full text-sm py-1.5" placeholder="0-10" min="0" max="10" step="0.5" />
          </div>

          <!-- 分辨率 -->
          <div v-if="searchSource === 'local'">
            <label class="text-xs mb-1 block" style="color: var(--text-muted)">分辨率</label>
            <select v-model="filters.resolution" @change="debouncedLocalSearch" class="input w-full text-sm py-1.5">
              <option value="">不限</option>
              <option value="4K">4K/2160p</option>
              <option value="1080p">1080p</option>
              <option value="720p">720p</option>
            </select>
          </div>

          <!-- 排序 -->
          <div v-if="searchSource === 'local'">
            <label class="text-xs mb-1 block" style="color: var(--text-muted)">排序方式</label>
            <select v-model="filters.sort_by" @change="debouncedLocalSearch" class="input w-full text-sm py-1.5">
              <option value="date_added">添加时间</option>
              <option value="rating">评分</option>
              <option value="year">年份</option>
              <option value="title">标题</option>
            </select>
          </div>

          <!-- 重置 -->
          <div class="flex items-end">
            <button @click="resetFilters" class="btn-ghost w-full text-sm py-1.5">
              重置筛选
            </button>
          </div>
        </div>
      </Transition>
    </div>

    <!-- 本地搜索分页信息 -->
    <div v-if="searchSource === 'local' && localTotal > 0" class="flex items-center justify-between text-sm" style="color: var(--text-muted)">
      <span>本地库找到 <strong style="color: var(--text-primary)">{{ localTotal }}</strong> 个结果</span>
      <div class="flex gap-2" v-if="localPages > 1">
        <button @click="localPage--; doLocalSearch()" :disabled="localPage <= 1" class="btn-ghost text-xs px-2 py-1">上一页</button>
        <span class="self-center">{{ localPage }} / {{ localPages }}</span>
        <button @click="localPage++; doLocalSearch()" :disabled="localPage >= localPages" class="btn-ghost text-xs px-2 py-1">下一页</button>
      </div>
    </div>

    <!-- 本地搜索结果（高级搜索模式） -->
    <div v-if="searchSource === 'local'">
      <div v-if="localLoading" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
        <div v-for="i in 12" :key="i" class="animate-pulse">
          <div class="aspect-[2/3] rounded-lg bg-[var(--bg-input)]" />
          <div class="h-4 bg-[var(--bg-input)] rounded mt-2 w-3/4" />
        </div>
      </div>
      <div v-else-if="localResults.length > 0" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
        <div v-for="item in localResults" :key="item.id" class="cursor-pointer group" @click="$router.push(`/media/${item.id}`)">
          <div class="rounded-lg bg-[var(--bg-input)] overflow-hidden aspect-[2/3] relative shadow-md group-hover:shadow-xl transition-all duration-300">
            <img v-if="item.poster_url" :src="item.poster_url" :alt="item.title" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" loading="lazy" referrerpolicy="no-referrer" @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />
            <div v-else class="w-full h-full flex items-center justify-center" style="color: var(--text-faint)">
              <svg class="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"/></svg>
            </div>
            <div class="absolute top-1.5 left-1.5 bg-brand-600/90 text-[9px] px-1.5 py-0.5 rounded text-white">
              {{ item.media_type === 'movie' ? '电影' : item.media_type === 'tv' ? '剧集' : '动漫' }}
            </div>
            <div v-if="item.rating" class="absolute top-1.5 right-1.5 bg-black/70 text-[10px] px-1 py-0.5 rounded text-yellow-400">
              ★ {{ item.rating.toFixed(1) }}
            </div>
          </div>
          <div class="mt-2">
            <div class="font-medium text-sm truncate">{{ item.title }}</div>
            <div class="text-xs" style="color: var(--text-muted)">{{ item.year || '—' }}</div>
          </div>
        </div>
      </div>
      <div v-else-if="!localLoading && query" class="py-12 text-center" style="color: var(--text-muted)">
        <svg class="w-16 h-16 mx-auto mb-4 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
        <p class="text-lg font-medium">本地库无匹配结果</p>
        <p class="text-sm mt-1">尝试调整筛选条件</p>
      </div>
    </div>

    <!-- TMDb 搜索加载骨架 -->
    <div v-if="searchSource === 'tmdb' && loading" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
      <div v-for="i in 12" :key="i" class="animate-pulse">
        <div class="aspect-[2/3] rounded-lg bg-[var(--bg-input)]" />
        <div class="h-4 bg-[var(--bg-input)] rounded mt-2 w-3/4" />
        <div class="h-3 bg-[var(--bg-input)] rounded mt-1 w-1/2" />
      </div>
    </div>

    <!-- TMDb 搜索结果 -->
    <div v-else-if="searchSource === 'tmdb' && results.length > 0" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4 stagger-in" :style="{ '--stagger': 30 }">
      <div v-for="(item, index) in results" :key="item.id"
        class="cursor-pointer group"
        @click="showDetailModal(item)">
        <div class="rounded-lg bg-[var(--bg-input)] overflow-hidden aspect-[2/3] relative shadow-md group-hover:shadow-xl transition-all duration-300">
          <img v-if="item.poster_path" :src="`https://image.tmdb.org/t/p/w500${item.poster_path}`" :alt="item.title || item.name"
            class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" loading="lazy" referrerpolicy="no-referrer" />
          <div v-else class="w-full h-full flex items-center justify-center" style="color: var(--text-faint)">
            <svg class="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"/></svg>
          </div>
          <!-- 媒体类型标签 -->
          <div class="absolute top-1.5 left-1.5 bg-brand-600/90 text-[9px] px-1.5 py-0.5 rounded text-white backdrop-blur-sm">
            {{ item.media_type === 'movie' ? '电影' : '剧集' }}
          </div>
          <!-- 评分 -->
          <div v-if="item.vote_average" class="absolute top-1.5 right-1.5 bg-black/70 text-[10px] px-1 py-0.5 rounded text-yellow-400 backdrop-blur-sm">
            ★ {{ item.vote_average.toFixed(1) }}
          </div>
          <!-- Hover 操作按钮 -->
          <div class="absolute bottom-1.5 right-1.5 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-10">
            <button @click.stop="quickSubscribe(item)"
              class="w-7 h-7 rounded-full bg-black/60 hover:bg-emerald-600 backdrop-blur-sm flex items-center justify-center transition-colors"
              title="快速订阅">
              <svg class="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
            </button>
          </div>
        </div>
        <div class="mt-2 space-y-0.5">
          <div class="font-medium text-sm truncate">{{ item.title || item.name }}</div>
          <div class="text-xs" style="color: var(--text-muted)">{{ (item.release_date || item.first_air_date || '').substring(0, 4) || '—' }}</div>
        </div>
      </div>
    </div>

    <!-- 空状态（TMDb） -->
    <div v-else-if="searchSource === 'tmdb' && !loading && query" class="py-12 text-center" style="color: var(--text-muted)">
      <svg class="w-16 h-16 mx-auto mb-4 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
      <p class="text-lg font-medium">未找到相关结果</p>
      <p class="text-sm mt-1">换个关键词试试？</p>
    </div>

    <!-- 初始状态 -->
    <div v-else-if="!query" class="py-12 text-center" style="color: var(--text-muted)">
      <svg class="w-16 h-16 mx-auto mb-4 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
      <p class="text-lg font-medium">输入关键词搜索</p>
      <p class="text-sm mt-1">
        <span v-if="searchSource === 'tmdb'">搜索 TMDb 电影和剧集</span>
        <span v-else>搜索本地媒体库</span>
      </p>
    </div>

    <!-- 详情 + 订阅弹窗 -->
    <Teleport to="body">
      <div v-if="detailItem" class="fixed inset-0 z-50 flex items-center justify-center p-4" @click.self="closeDetail">
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" />
        <div class="relative bg-[var(--bg-card)] rounded-xl shadow-2xl w-full max-w-lg max-h-[85vh] flex flex-col animate-in overflow-hidden">
          <!-- 顶部背景条 -->
          <div v-if="detailItem.backdrop_url || detailItem.poster_url" class="h-36 relative shrink-0 overflow-hidden">
            <img :src="detailItem.backdrop_url || detailItem.poster_url" class="w-full h-full object-cover opacity-40" referrerpolicy="no-referrer"
              @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />
            <div class="absolute inset-0 bg-gradient-to-t from-[var(--bg-card)] via-transparent to-transparent" />
          </div>
          <!-- 关闭按钮 -->
          <button @click="closeDetail" class="absolute top-3 right-3 z-10 w-8 h-8 rounded-full bg-black/40 hover:bg-black/60 text-white flex items-center justify-center transition-colors">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
          <!-- 海报（悬浮） -->
          <div v-if="detailItem.poster_url" class="absolute top-20 left-5 z-10 w-28 rounded-lg overflow-hidden shadow-xl border-2 border-[var(--bg-card)]">
            <img :src="detailItem.poster_url" :alt="detailItem.title" class="w-full aspect-[2/3] object-cover" referrerpolicy="no-referrer"
              @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />
          </div>
          <!-- 内容区 -->
          <div class="flex-1 overflow-y-auto pt-14 px-5 pb-5">
            <div class="ml-32 space-y-1 mb-3">
              <h3 class="text-lg font-bold leading-tight">{{ detailItem.title }}</h3>
              <div v-if="detailItem.original_title && detailItem.original_title !== detailItem.title" class="text-xs" style="color: var(--text-muted)">{{ detailItem.original_title }}</div>
            </div>
            <div class="flex flex-wrap items-center gap-2 text-xs mb-3">
              <span v-if="detailItem.media_type" class="px-2 py-0.5 rounded uppercase font-medium"
                :class="{
                  'bg-blue-500/20 text-blue-400': detailItem.media_type === 'movie',
                  'bg-emerald-500/20 text-emerald-400': detailItem.media_type === 'tv',
                }">
                {{ detailItem.media_type === 'movie' ? '电影' : '剧集' }}
              </span>
              <span v-if="detailItem.year" class="px-2 py-0.5 rounded bg-[var(--bg-secondary)]" style="color: var(--text-muted)">{{ detailItem.year }}</span>
              <span v-if="detailItem.rating" class="text-yellow-400 font-medium">★ {{ typeof detailItem.rating === 'number' ? detailItem.rating.toFixed(1) : detailItem.rating }}</span>
            </div>
            <p v-if="detailItem.overview" class="text-sm leading-relaxed mb-4" style="color: var(--text-muted)">
              {{ detailItem.overview.length > 300 ? detailItem.overview.slice(0, 300) + '...' : detailItem.overview }}
            </p>
            <p v-else class="text-sm italic mb-4" style="color: var(--text-faint)">暂无简介</p>
            <!-- 操作按钮 -->
            <div class="flex flex-wrap gap-2 pt-2 border-t border-[var(--border)]">
              <button @click="doSubscribe"
                :disabled="subscribing"
                class="flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-50 transition-colors">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
                {{ subscribing ? '订阅中...' : '订阅下载' }}
              </button>
              <button v-if="detailItem.tmdb_id"
                @click="copyTmdbId"
                class="flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg bg-[var(--bg-secondary)] hover:bg-[var(--bg-hover)] border border-[var(--border)] transition-colors"
                style="color: var(--text-secondary)">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>
                {{ copiedTmdb ? '已复制!' : 'TMDb ID' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter, onBeforeRouteUpdate } from 'vue-router'
import { mediaApi } from '@/api/media'
import { subscribeApi } from '@/api/subscribe'
import { useToast } from '@/composables/useToast'
import api from '@/api/client'

const route = useRoute()
const router = useRouter()
const toast = useToast()

// 搜索状态
const query = ref(route.query.q as string || '')
const searchQuery = ref(query.value)
const activeType = ref<'all' | 'movie' | 'tv'>('all')
const results = ref<any[]>([])
const loading = ref(false)
const totalResults = computed(() => results.value.length)

// ── 高级搜索状态 ──
const showAdvanced = ref(false)
const searchSource = ref<'tmdb' | 'local'>('tmdb')
const localResults = ref<any[]>([])
const localLoading = ref(false)
const localTotal = ref(0)
const localPage = ref(1)
const localPages = ref(1)

const filters = ref({
  genre: '',
  year_min: null as number | null,
  year_max: null as number | null,
  rating_min: null as number | null,
  resolution: '',
  sort_by: 'date_added',
})

const hasActiveFilters = computed(() =>
  searchSource.value === 'local' || filters.value.genre || filters.value.year_min
  || filters.value.year_max || filters.value.rating_min || filters.value.resolution
)

function resetFilters() {
  filters.value = { genre: '', year_min: null, year_max: null, rating_min: null, resolution: '', sort_by: 'date_added' }
  if (searchSource.value === 'local') doLocalSearch()
}

// 防抖
let localSearchTimer: ReturnType<typeof setTimeout>
function debouncedLocalSearch() {
  clearTimeout(localSearchTimer)
  localSearchTimer = setTimeout(() => { localPage.value = 1; doLocalSearch() }, 400)
}

async function doLocalSearch() {
  const q = query.value.trim()
  localLoading.value = true
  try {
    const params: Record<string, any> = {
      page: localPage.value,
      page_size: 24,
      sort_by: filters.value.sort_by,
      sort_order: 'desc',
    }
    if (q) params.q = q
    if (filters.value.genre) params.genre = filters.value.genre
    if (filters.value.year_min) params.year_min = filters.value.year_min
    if (filters.value.year_max) params.year_max = filters.value.year_max
    if (filters.value.rating_min) params.rating_min = filters.value.rating_min
    if (filters.value.resolution) params.resolution = filters.value.resolution
    if (activeType.value !== 'all') params.media_type = activeType.value

    const res = await api.get('/api/search/advanced', { params })
    const data = (res.data as any)
    localResults.value = data.items || []
    localTotal.value = data.total || 0
    localPages.value = data.pages || 1
  } catch (e) {
    localResults.value = []
    localTotal.value = 0
  } finally {
    localLoading.value = false
  }
}

// 切换搜索来源
watch(searchSource, (src) => {
  if (src === 'local' && query.value) {
    localPage.value = 1
    doLocalSearch()
  }
})

const mediaTypes = [
  { label: '全部', value: 'all' as const },
  { label: '电影', value: 'movie' as const },
  { label: '剧集', value: 'tv' as const },
]

// 详情弹窗
const detailItem = ref<any>(null)
const subscribing = ref(false)
const copiedTmdb = ref(false)

// 搜索
async function performSearch() {
  const q = query.value.trim()
  if (!q) {
    results.value = []
    return
  }

  loading.value = true
  try {
    let movies: any[] = []
    let tvs: any[] = []

    if (activeType.value === 'all' || activeType.value === 'movie') {
      const movieRes = await mediaApi.searchTmdb(q, 'movie')
      movies = (movieRes.data.results || []).map((r: any) => ({ ...r, media_type: 'movie' }))
    }

    if (activeType.value === 'all' || activeType.value === 'tv') {
      const tvRes = await mediaApi.searchTmdb(q, 'tv')
      tvs = (tvRes.data.results || []).map((r: any) => ({ ...r, media_type: 'tv' }))
    }

    results.value = [...movies, ...tvs]
  } catch (e) {
    console.error('Search error:', e)
    results.value = []
    toast.error('搜索失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  const q = searchQuery.value.trim()
  if (q) {
    router.replace({ path: '/search', query: { q } })
  }
}

function switchType(type: 'all' | 'movie' | 'tv') {
  activeType.value = type
  if (query.value) {
    performSearch()
  }
}

// 详情弹窗
function showDetailModal(item: any) {
  detailItem.value = {
    ...item,
    tmdb_id: item.id,
    title: item.title || item.name,
    poster_url: item.poster_path ? `https://image.tmdb.org/t/p/w500${item.poster_path}` : null,
    backdrop_url: item.backdrop_path ? `https://image.tmdb.org/t/p/w780${item.backdrop_path}` : null,
    overview: item.overview,
    year: (item.release_date || item.first_air_date || '').substring(0, 4) || null,
    media_type: item.media_type === 'movie' ? 'movie' : 'tv',
    rating: item.vote_average,
    // 保存 TMDB 原始英文名称，用于站点搜索
    original_title: item.original_title || null,
    original_name: item.original_name || null,
    external: true,
    source: 'tmdb',
  }
  copiedTmdb.value = false
}

function closeDetail() {
  detailItem.value = null
}

async function quickSubscribe(item: any) {
  showDetailModal(item)
  await doSubscribe()
}

async function doSubscribe() {
  if (!detailItem.value) return
  const item = detailItem.value
  subscribing.value = true
  try {
    // 从 TMDB 搜索结果获取英文原名（用于站点搜索）
    // 电影使用 original_title，剧集使用 original_name
    const originalName = item.original_title || item.original_name || null
    await subscribeApi.createSubscription({
      name: item.title,
      original_name: originalName,
      tmdb_id: item.tmdb_id || null,
      media_type: item.media_type || 'movie',
      year: item.year || null,
      quality_filter: ['1080p', '720p'],
    })
    toast.success(`「${item.title}」已添加到订阅列表！`)
    closeDetail()
  } catch (e: any) {
    const msg = e.response?.data?.detail || e.message
    if (typeof msg === 'string' && msg.includes('already exists')) {
      toast.info('该订阅已存在')
    } else {
      toast.error(`订阅失败: ${msg}`)
    }
  } finally {
    subscribing.value = false
  }
}

async function copyTmdbId() {
  if (!detailItem.value?.tmdb_id) return
  try {
    await navigator.clipboard.writeText(String(detailItem.value.tmdb_id))
    copiedTmdb.value = true
    setTimeout(() => { copiedTmdb.value = false }, 2000)
  } catch { /* ignore */ }
}

// 路由更新时重新搜索（仅当组件复用时触发）
onBeforeRouteUpdate((to, from) => {
  if (to.query.q !== from.query.q) {
    query.value = to.query.q as string || ''
    searchQuery.value = query.value
    if (query.value) {
      performSearch()
    } else {
      results.value = []
    }
  }
})

onMounted(() => {
  if (query.value) {
    performSearch()
  }
})
</script>

<style scoped>
/* 折叠动画 */
.collapse-enter-active, .collapse-leave-active {
  transition: max-height 0.3s ease, opacity 0.3s ease;
  overflow: hidden;
}
.collapse-enter-from, .collapse-leave-to {
  max-height: 0;
  opacity: 0;
}
.collapse-enter-to, .collapse-leave-from {
  max-height: 400px;
  opacity: 1;
}

.stagger-in > * {
  animation: staggerIn 0.4s ease-out both;
}
.stagger-in > *:nth-child(1) { animation-delay: 0ms; }
.stagger-in > *:nth-child(2) { animation-delay: 30ms; }
.stagger-in > *:nth-child(3) { animation-delay: 60ms; }
.stagger-in > *:nth-child(4) { animation-delay: 90ms; }
.stagger-in > *:nth-child(5) { animation-delay: 120ms; }
.stagger-in > *:nth-child(6) { animation-delay: 150ms; }
.stagger-in > *:nth-child(7) { animation-delay: 180ms; }
.stagger-in > *:nth-child(8) { animation-delay: 210ms; }
.stagger-in > *:nth-child(9) { animation-delay: 240ms; }
.stagger-in > *:nth-child(10) { animation-delay: 270ms; }
.stagger-in > *:nth-child(11) { animation-delay: 300ms; }
.stagger-in > *:nth-child(12) { animation-delay: 330ms; }

@keyframes staggerIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-in {
  animation: modalIn 0.2s ease-out;
}
@keyframes modalIn {
  from { opacity: 0; transform: scale(0.96); }
  to   { opacity: 1; transform: scale(1); }
}
</style>
