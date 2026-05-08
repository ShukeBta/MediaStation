<template>
  <div class="min-h-screen p-4 md:p-6 max-w-[1600px] mx-auto">
    <!-- 顶栏 -->
    <div class="flex flex-wrap items-center gap-3 mb-6">
      <h1 class="text-2xl font-bold flex items-center gap-2">
        <svg class="w-7 h-7 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/></svg>
        海报墙
      </h1>
      <div class="flex-1" />
      <!-- 视图切换 -->
      <div class="flex bg-[var(--bg-input)] rounded-lg p-0.5 gap-0.5">
        <button @click="viewMode = 'poster'" :class="['px-3 py-1.5 text-sm rounded-md transition-colors', viewMode === 'poster' ? 'bg-brand-600 text-white' : 'hover:bg-[var(--bg-hover)]']">海报</button>
        <button @click="viewMode = 'list'" :class="['px-3 py-1.5 text-sm rounded-md transition-colors', viewMode === 'list' ? 'bg-brand-600 text-white' : 'hover:bg-[var(--bg-hover)]']">列表</button>
      </div>
      <!-- 类型筛选 -->
      <div class="flex bg-[var(--bg-input)] rounded-lg p-0.5 gap-0.5">
        <button v-for="t in typeTabs" :key="t.value"
          @click="filters.media_type = t.value; loadItems()"
          :class="['px-3 py-1.5 text-sm rounded-md transition-all', filters.media_type === t.value ? 'bg-brand-600 text-white shadow-sm' : 'hover:bg-[var(--bg-hover)]']">
          {{ t.label }}
        </button>
      </div>
      <!-- 搜索 -->
      <input v-model="filters.search" @input="debounceSearch"
        class="input !w-full sm:!w-56" placeholder="搜索..." />
    </div>

    <!-- 统计条 -->
    <div class="flex items-center gap-4 mb-4 text-sm" style="color: var(--text-muted)">
      <span>共 {{ total }} 部作品</span>
      <span v-if="filters.search">搜索: "{{ filters.search }}"</span>
    </div>

    <!-- 海报视图 (瀑布流) -->
    <div v-if="!loading && items.length > 0 && viewMode === 'poster'"
      class="columns-2 sm:columns-3 md:columns-4 lg:columns-5 xl:columns-6 gap-3 md:gap-4 [column-fill:_balance] stagger-in">
      <div v-for="(item, index) in sortedItems" :key="item.id"
        @click="$router.push(`/media/${item.id}`)"
        class="cursor-pointer group break-inside-avoid mb-3 md:mb-4 poster-card"
        :style="{ '--stagger': `${index * 30}ms` }">
        <!-- 海报卡片 -->
        <div class="poster-inner rounded-xl overflow-hidden relative transition-all duration-300 group-hover:shadow-xl group-hover:shadow-brand-500/10"
          :class="[item.media_type === 'movie' ? 'aspect-[2/3]' : 'aspect-[3/4]']"
          :style="{ background: posterBg(item) }">

          <!-- 海报图 -->
          <img v-if="item.poster_url" :src="item.poster_url" :alt="item.title"
            class="w-full h-full object-cover"
            loading="lazy" referrerpolicy="no-referrer"
            @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />

          <!-- 无海报占位 -->
          <div v-else class="w-full h-full flex flex-col items-center justify-center gap-2 p-4">
            <svg class="w-16 h-16 opacity-20" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"/></svg>
            <span class="text-xs opacity-40 text-center line-clamp-2">{{ item.title }}</span>
          </div>

          <!-- 渐变遮罩（底部文字区） -->
          <div class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 via-black/50 to-transparent pt-16 pb-3 px-3">
          </div>

          <!-- 信息层 -->
          <div class="absolute inset-x-0 bottom-0 pt-12 pb-3 px-3 pointer-events-none">
            <!-- 类型标签 + 评分 -->
            <div class="flex items-center gap-1.5 mb-1">
              <span :class="['text-[10px] px-1.5 py-0.5 rounded font-medium uppercase tracking-wide', typeBadgeClass(item.media_type)]">
                {{ typeLabel(item.media_type) }}
              </span>
              <span v-if="item.rating" class="text-xs text-yellow-400 font-medium ml-auto">
                ★ {{ item.rating.toFixed(1) }}
              </span>
              <span v-else-if="item.douban_rating" class="text-xs text-green-400 font-medium ml-auto">
                豆 ★ {{ item.douban_rating.toFixed(1) }}
              </span>
            </div>

            <!-- 标题 -->
            <div class="text-sm font-semibold text-white truncate drop-shadow">{{ item.title }}</div>
            <div class="text-[11px] text-white/60 truncate">{{ item.year || '' }} {{ item.original_title ? `· ${item.original_title}` : '' }}</div>

            <!-- 标签 -->
            <div v-if="item.genres?.length" class="flex flex-wrap gap-1 mt-1.5">
              <span v-for="g in item.genres.slice(0, 3)" :key="g"
                class="text-[10px] px-1.5 py-0.5 rounded-full bg-white/15 text-white/80 backdrop-blur-sm">
                {{ g }}
              </span>
            </div>
          </div>

          <!-- 悬浮播放按钮 -->
          <div class="absolute inset-0 bg-black/0 group-hover:bg-black/25 transition-all duration-300 flex items-center justify-center pointer-events-none">
            <div class="w-14 h-14 bg-white/20 backdrop-blur-md rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 scale-75 group-hover:scale-100 transition-all duration-300 shadow-lg border border-white/30 pointer-events-auto cursor-pointer"
              @click.stop="$router.push(`/player/${item.id}`)">
              <svg class="w-7 h-7 text-white ml-1" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
            </div>
          </div>

          <!-- 进度条（如果有观看历史） -->
          <div v-if="watchProgress[item.id]" class="absolute left-0 right-0 bottom-0 h-0.5 bg-white/20">
            <div class="h-full bg-brand-500 transition-all" :style="{ width: watchProgress[item.id] + '%' }" />
          </div>
        </div>
      </div>
    </div>

    <!-- 列表视图 -->
    <div v-if="!loading && items.length > 0 && viewMode === 'list'" class="space-y-2 stagger-in">
      <div v-for="(item, index) in sortedItems" :key="item.id"
        @click="$router.push(`/media/${item.id}`)"
        class="flex items-center gap-4 p-3 rounded-xl cursor-pointer transition-all hover:bg-[var(--bg-hover)] card"
        :style="{ '--stagger': `${index * 30}ms` }">
        <!-- 缩略图 -->
        <div class="w-16 md:w-20 aspect-[2/3] rounded-lg overflow-hidden shrink-0 bg-[var(--bg-input)]">
          <img v-if="item.poster_url" :src="item.poster_url" :alt="item.title"
            class="w-full h-full object-cover" loading="lazy" referrerpolicy="no-referrer"
            @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />
        </div>
        <!-- 信息 -->
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <span class="font-medium truncate">{{ item.title }}</span>
            <span :class="['text-[10px] px-1.5 py-0.5 rounded', typeBadgeClass(item.media_type)]">{{ typeLabel(item.media_type) }}</span>
          </div>
          <div class="text-xs mt-0.5" style="color: var(--text-muted)">
            {{ item.original_title || '' }} · {{ item.year || '' }}
            <span v-if="item.rating" class="ml-2 text-yellow-400">★ {{ item.rating.toFixed(1) }}</span>
          </div>
          <p v-if="item.overview" class="text-xs mt-1 line-clamp-2" style="color: var(--text-faint)">{{ item.overview }}</p>
        </div>
        <!-- 操作 -->
        <svg class="w-5 h-5 shrink-0" style="color: var(--text-faint)" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
      </div>
    </div>

    <!-- 骨架屏 -->
    <div v-if="loading" :class="['grid gap-3 md:gap-4', viewMode === 'poster' ? 'columns-2 sm:columns-3 md:columns-4 lg:columns-5 xl:columns-6' : '']">
      <div v-for="i in 18" :key="i" class="animate-pulse">
        <div :class="['rounded-xl bg-[var(--bg-input)]', viewMode === 'poster' ? 'aspect-[2/3]' : 'h-20']" />
      </div>
    </div>

    <!-- 空状态 -->
    <AppEmpty v-else-if="items.length === 0 && !loading" message="暂无媒体内容" />

    <!-- 分页 -->
    <div v-if="totalPages > 1" class="flex justify-center items-center gap-4 mt-8">
      <button @click="page > 1 && loadItems(page - 1)" :disabled="page <= 1"
        class="btn-secondary text-sm disabled:opacity-30 flex items-center gap-1">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
        上一页
      </button>
      <span class="text-sm tabular-nums" style="color: var(--text-muted)">第 {{ page }} / {{ totalPages }} 页</span>
      <button @click="page < totalPages && loadItems(page + 1)" :disabled="page >= totalPages"
        class="btn-secondary text-sm disabled:opacity-30 flex items-center gap-1">
        下一页
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
      </button>
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
const pageSize = 36
const totalPages = computed(() => Math.ceil(total.value / pageSize))
const viewMode = ref<'poster' | 'list'>('poster')
const watchProgress = ref<Record<number, number>>({})

const filters = ref({ media_type: '', search: '' })

const typeTabs = [
  { label: '全部', value: '' },
  { label: '电影', value: 'movie' },
  { label: '电视剧', value: 'tv' },
  { label: '动漫', value: 'anime' },
]

// 排序：有海报的优先，按评分降序
const sortedItems = computed(() => {
  return [...items.value].sort((a, b) => {
    // 有海报的排前面
    const aPoster = a.poster_url ? 1 : 0
    const bPoster = b.poster_url ? 1 : 0
    if (aPoster !== bPoster) return bPoster - aPoster
    // 按评分降序
    return (b.rating || 0) - (a.rating || 0)
  })
})

function typeLabel(type: string): string {
  return { movie: '电影', tv: '剧', anime: '动漫' }[type] || type
}

function typeBadgeClass(type: string): string {
  return {
    movie: 'bg-blue-500/80 text-white',
    tv: 'bg-emerald-500/80 text-white',
    anime: 'bg-pink-500/80 text-white',
  }[type] || 'bg-gray-500/80 text-white'
}

function posterBg(item: any): string {
  // 根据类型生成微妙的背景色
  const colors: Record<string, string> = {
    movie: 'linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%)',
    tv: 'linear-gradient(135deg, #1a3c34 0%, #0d1f1a 100%)',
    anime: 'linear-gradient(135deg, #4a1942 0%, #1a0a1e 100%)',
  }
  return colors[item.media_type] || colors.movie
}

let searchTimer: any

function debounceSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { page.value = 1; loadItems() }, 350)
}

async function loadItems(p?: number) {
  if (p) page.value = p
  loading.value = true
  try {
    const params: any = {
      page: page.value,
      page_size: pageSize,
      sort_by: 'rating',
      sort_order: 'desc',
    }
    if (filters.value.media_type) params.media_type = filters.value.media_type
    if (filters.value.search) params.search = filters.value.search

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
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 修复 CSS columns 瀑布流布局中的 overflow hidden 问题 */
:deep(.break-inside-avoid) {
  /* 强制每个海报卡片创建新的层叠上下文，防止 transform 溢出 */
  transform: translateZ(0);
  isolation: isolate;
}

/* 海报卡片的图片容器 - 确保 hover 缩放不会溢出 */
:deep(.poster-card) {
  overflow: hidden;
  transform: translateZ(0);
  isolation: isolate;
  border-radius: 0.75rem;
}

/* 海报图片 - 使用 transform 而非直接缩放图片 */
:deep(.poster-card img) {
  max-width: 100%;
  max-height: 100%;
  transform: scale(1);
  transition: transform 0.5s cubic-bezier(0.4, 0, 0.2, 1);
  will-change: transform;
}

/* hover 时图片缩放（通过 transform 而非改变尺寸） */
:deep(.poster-card:hover img),
:deep(.poster-card:hover .poster-inner) {
  transform: scale(1.05);
}
</style>
