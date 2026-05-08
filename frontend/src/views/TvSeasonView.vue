<template>
  <div class="min-h-screen p-4 md:p-6 max-w-6xl mx-auto">
    <!-- 返回 + 标题 -->
    <div v-if="item" class="space-y-8">
      <!-- 头部信息 -->
      <div class="flex flex-col md:flex-row gap-6">
        <!-- 海报 -->
        <div class="shrink-0 self-center md:self-start">
          <div class="w-44 md:w-52 rounded-xl overflow-hidden shadow-2xl ring-1 ring-white/10">
            <img v-if="item.poster_url" :src="item.poster_url" :alt="item.title"
              class="w-full object-cover" referrerpolicy="no-referrer"
              @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />
            <div v-else class="w-full aspect-[2/3] bg-[var(--bg-input)] flex items-center justify-center" style="color: var(--text-faint)">
              无海报
            </div>
          </div>
        </div>

        <!-- 基本信息 -->
        <div class="flex-1 space-y-3">
          <div>
            <h1 class="text-2xl md:text-3xl font-bold">{{ item.title }}</h1>
            <p class="mt-1" style="color: var(--text-muted)">{{ item.original_title }}</p>
          </div>

          <!-- 标签行 -->
          <div class="flex flex-wrap items-center gap-2 text-sm">
            <span v-if="item.year" class="bg-[var(--bg-input)] px-2.5 py-1 rounded-lg border border-[var(--border-primary)]">{{ item.year }}</span>
            <span v-if="item.rating" class="text-yellow-400 font-medium">★ {{ item.rating.toFixed(1) }}</span>
            <span v-if="item.douban_rating" class="text-green-400 font-medium text-xs">豆瓣 ★ {{ item.douban_rating.toFixed(1) }}</span>
            <span v-if="item.bangumi_rating" class="text-pink-400 font-medium text-xs">Bangumi ★ {{ item.bangumi_rating.toFixed(1) }}</span>
          </div>

          <!-- 类型标签 -->
          <div v-if="item.genres?.length" class="flex flex-wrap gap-1.5">
            <span v-for="g in item.genres" :key="g"
              class="text-xs px-2 py-0.5 rounded-md bg-brand-500/10 text-brand-400 border border-brand-500/20">
              {{ g }}
            </span>
          </div>

          <!-- 简介 -->
          <p v-if="item.overview" class="text-sm leading-relaxed line-clamp-4" style="color: var(--text-muted)">{{ item.overview }}</p>

          <!-- 操作按钮 -->
          <div class="flex flex-wrap gap-3 pt-2">
            <button @click="playFirst()" class="btn-primary flex items-center gap-2">
              <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
              开始播放
            </button>
            <button @click="$router.back()" class="btn-secondary">返回</button>
          </div>
        </div>
      </div>

      <!-- 季视图 -->
      <section v-if="item.seasons?.length">
        <h2 class="text-xl font-bold mb-4 flex items-center gap-2">
          <svg class="w-5 h-5 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/></svg>
          剧集列表 · 共 {{ totalEpisodes }} 集
        </h2>

        <!-- 季选择标签 (多季时显示) -->
        <div v-if="item.seasons.length > 1" class="flex gap-2 mb-6 overflow-x-auto pb-2 -mx-4 px-4 md:mx-0 md:px-0">
          <button v-for="season in item.seasons" :key="season.id"
            @click="selectedSeason = season.season_number"
            :class="['px-4 py-2 rounded-xl text-sm font-medium whitespace-nowrap transition-all',
              selectedSeason === season.season_number
                ? 'bg-brand-600 text-white shadow-lg shadow-brand-500/25'
                : 'bg-[var(--bg-card-solid)] border border-[var(--border-primary)] hover:border-brand-500/50']">
            第 {{ season.season_number }} 季
            <span class="ml-1.5 opacity-60 text-xs">({{ season.episodes?.length || 0 }}集)</span>
          </button>
        </div>

        <!-- 季内容 -->
        <div v-for="season in currentSeasons" :key="season.id" class="space-y-3">
          <!-- 季标题（仅单季或选中季） -->
          <h3 class="text-base font-semibold sticky top-0 z-10 py-2 -mx-4 px-4 md:-mx-0 md:px-0"
            :style="{ background: 'var(--bg-primary)' }">
            {{ season.name || `第 ${season.season_number} 季` }}
            <span class="ml-2 font-normal text-sm" style="color: var(--text-muted)">
              {{ season.episodes?.length || 0 }} 集
            </span>
          </h3>

          <!-- 集数列表 -->
          <div class="grid gap-2">
            <div v-for="ep in sortedEpisodes(season)" :key="ep.id"
              @click="play(item.id, ep.id)"
              class="group flex items-center gap-3 sm:gap-4 p-3 rounded-xl cursor-pointer transition-all hover:bg-[var(--bg-hover)] border border-transparent hover:border-brand-500/20 card"
              :class="{ 'opacity-50': !ep.file_path }">
              <!-- 集号 -->
              <div class="relative shrink-0 w-10 h-10 rounded-lg bg-[var(--bg-input)] flex items-center justify-center text-sm font-bold group-hover:bg-brand-600 group-hover:text-white transition-colors"
                style="color: var(--text-secondary)">
                {{ String(ep.episode_number).padStart(2, '0') }}
                <!-- 已看标记 -->
                <div v-if="epWatched[ep.id]" class="absolute -top-1 -right-1 w-3 h-3 bg-green-500 rounded-full ring-2 ring-[var(--bg-card-solid)]" />
              </div>

              <!-- 信息 -->
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium truncate group-hover:text-brand-400 transition-colors">
                  {{ ep.title || `第 ${ep.episode_number} 集` }}
                </div>
                <div class="text-xs mt-0.5 flex items-center gap-2" style="color: var(--text-faint)">
                  <span v-if="ep.air_date">{{ ep.air_date }}</span>
                  <span v-if="ep.duration">{{ formatDuration(ep.duration) }}</span>
                  <span v-if="!ep.file_path" class="text-red-400/70">暂无资源</span>
                  <span v-else class="text-green-500/70">可用</span>
                </div>
                <!-- 观看进度条 -->
                <div v-if="epProgress[ep.id]" class="mt-1.5 h-1 bg-[var(--bg-input)] rounded-full overflow-hidden">
                  <div class="h-full bg-brand-500 rounded-full transition-all" :style="{ width: epProgress[ep.id] + '%' }" />
                </div>
              </div>

              <!-- 播放图标 -->
              <div class="shrink-0 w-9 h-9 rounded-full bg-[var(--bg-hover)] flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all group-hover:bg-brand-600">
                <svg class="w-4 h-4 text-white ml-0.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
              </div>
            </div>
          </div>
        </div>

        <!-- 空季提示 -->
        <div v-if="currentSeasons.length === 0" class="text-center py-12" style="color: var(--text-muted)">
          <svg class="w-16 h-16 mx-auto mb-3 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>
          <p>暂无剧集数据</p>
          <p class="text-sm mt-1">请先扫描媒体库或手动添加</p>
        </div>
      </section>

      <!-- 无季数据的电影 -->
      <section v-else-if="item.media_type === 'movie'" class="text-center py-8" style="color: var(--text-muted)">
        <p>这是一部电影，可直接播放。</p>
      </section>
    </div>

    <!-- 加载状态 -->
    <div v-else-if="loading" class="flex items-center justify-center min-h-screen">
      <div class="animate-spin text-4xl text-brand-500">▶</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { mediaApi } from '@/api/media'

const route = useRoute()
const router = useRouter()

const item = ref<any>(null)
const loading = ref(true)
const selectedSeason = ref(1)

// 观看状态（模拟，实际从 API 获取）
const epWatched = ref<Record<number, boolean>>({})
const epProgress = ref<Record<number, number>>({})

// 当前选中的季（支持多季切换）
const currentSeasons = computed(() => {
  if (!item.value?.seasons) return []
  return item.value.seasons.filter((s: any) => s.season_number === selectedSeason.value)
})

// 总集数
const totalEpisodes = computed(() => {
  if (!item.value?.seasons) return 0
  return item.value.seasons.reduce((sum: number, s: any) => sum + (s.episodes?.length || 0), 0)
})

function sortedEpisodes(season: any): any[] {
  if (!season.episodes) return []
  return [...season.episodes].sort((a: any, b: any) => a.episode_number - b.episode_number)
}

function formatDuration(seconds: number): string {
  if (!seconds) return ''
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  if (m > 0 && s > 0) return `${m}分${s}秒`
  if (m > 0) return `${m}分钟`
  return `${s}秒`
}

function play(mediaId: number, episodeId?: number) {
  router.push({ path: `/player/${mediaId}`, query: episodeId ? { episode: String(episodeId) } : {} })
}

function playFirstEpisode() {
  // 找第一个有文件的集
  if (!item.value?.seasons) { play(item.value.id); return }
  for (const season of item.value.seasons) {
    for (const ep of season.episodes || []) {
      if (ep.file_path) { play(item.value.id, ep.id); return }
    }
  }
  // 没有文件也跳到播放页
  play(item.value.id)
}

function playFirst() {
  if (item.value.media_type === 'movie') {
    play(item.value.id)
  } else {
    playFirstEpisode()
  }
}

async function loadItem() {
  loading.value = true
  try {
    const { data } = await mediaApi.getDetail(Number(route.params.id))
    item.value = data

    // 默认选中第一季
    if (data.seasons?.length) {
      const firstSeasonNum = Math.min(...data.seasons.map((s: any) => s.season_number))
      selectedSeason.value = firstSeasonNum
    }

    // 加载观看进度（如果有）
    try {
      import('@/api/system').then(({ watchHistoryApi }) => {
        watchHistoryApi.getContinueWatching().then(({ data }: any) => {
          if (Array.isArray(data)) {
            data.forEach((h: any) => {
              if (h.episode_id) {
                epWatched.value[h.episode_id] = h.completed || false
                if (h.progress && h.duration) {
                  epProgress.value[h.episode_id] = Math.round((h.progress / h.duration) * 100)
                }
              }
            })
          }
        }).catch(() => {})
      })
    } catch {}
  } catch (e) {
    console.error(e)
    router.push('/media')
  } finally {
    loading.value = false
  }
}

onMounted(loadItem)
</script>

<style scoped>
.line-clamp-4 {
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
