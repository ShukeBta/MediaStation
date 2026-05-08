<template>
  <div class="p-4 md:p-6 max-w-5xl mx-auto space-y-6">
    <!-- 页面标题 -->
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold">个人中心</h1>
      <router-link to="/settings" class="btn-secondary text-sm flex items-center gap-1.5">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-1.756.426-1.756 2.924 0 3.35a1.724 1.724 0 001.066 2.573c-1.543-.94-3.31.826-2.37 2.37-.996.608-2.296.07-2.572-1.065a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996-.608 2.296-.07 2.572 1.065a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
        编辑资料
      </router-link>
    </div>

    <!-- 加载骨架 -->
    <div v-if="loading" class="space-y-6">
      <div class="card p-6 animate-pulse">
        <div class="flex items-center gap-5">
          <div class="w-20 h-20 rounded-full bg-[var(--bg-hover)] shrink-0" />
          <div class="flex-1 space-y-3">
            <div class="h-5 bg-[var(--bg-hover)] rounded w-32" />
            <div class="h-4 bg-[var(--bg-hover)] rounded w-48" />
          </div>
        </div>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div v-for="i in 4" :key="i" class="card p-5 animate-pulse">
          <div class="h-3 bg-[var(--bg-hover)] rounded w-16 mb-3" />
          <div class="h-8 bg-[var(--bg-hover)] rounded w-12" />
        </div>
      </div>
    </div>

    <template v-else>
      <!-- 用户卡片 -->
      <div class="card p-6">
        <div class="flex items-center gap-5">
          <!-- 头像 -->
          <div class="w-20 h-20 rounded-full bg-brand-500/20 text-brand-400 flex items-center justify-center text-3xl font-bold shrink-0 select-none">
            {{ userInitials }}
          </div>
          <div class="flex-1 min-w-0">
            <div class="text-xl font-bold">{{ user?.username }}</div>
            <div class="text-sm mt-1" style="color: var(--text-muted)">{{ user?.email || '未设置邮箱' }}</div>
            <div class="flex items-center gap-2 mt-2">
              <span class="badge" :class="user?.role === 'admin' ? 'badge-warning' : 'badge-info'">
                {{ user?.role === 'admin' ? '管理员' : '普通用户' }}
              </span>
              <span class="text-xs" style="color: var(--text-faint)">
                加入于 {{ formatDate(user?.created_at) }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 统计卡片 -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4 stagger-in">
        <div class="card p-5 cursor-pointer hover:border-brand-500/50 transition-colors animate-in"
          style="--stagger: 0" @click="$router.push('/history')">
          <div class="flex items-center justify-between mb-2">
            <div class="text-sm" style="color: var(--text-muted)">观看历史</div>
            <div class="w-8 h-8 rounded-lg flex items-center justify-center bg-blue-500/10">
              <svg class="w-4 h-4 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            </div>
          </div>
          <div class="text-3xl font-bold text-blue-400">{{ stats.watch_history || 0 }}</div>
          <div class="text-xs mt-1" style="color: var(--text-faint)">条记录</div>
        </div>

        <div class="card p-5 cursor-pointer hover:border-brand-500/50 transition-colors animate-in"
          style="--stagger: 50" @click="$router.push('/favorites')">
          <div class="flex items-center justify-between mb-2">
            <div class="text-sm" style="color: var(--text-muted)">我的收藏</div>
            <div class="w-8 h-8 rounded-lg flex items-center justify-center bg-yellow-500/10">
              <svg class="w-4 h-4 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/></svg>
            </div>
          </div>
          <div class="text-3xl font-bold text-yellow-400">{{ stats.favorites || 0 }}</div>
          <div class="text-xs mt-1" style="color: var(--text-faint)">部收藏</div>
        </div>

        <div class="card p-5 cursor-pointer hover:border-brand-500/50 transition-colors animate-in"
          style="--stagger: 100" @click="$router.push('/subscriptions')">
          <div class="flex items-center justify-between mb-2">
            <div class="text-sm" style="color: var(--text-muted)">订阅数</div>
            <div class="w-8 h-8 rounded-lg flex items-center justify-center bg-violet-500/10">
              <svg class="w-4 h-4 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/></svg>
            </div>
          </div>
          <div class="text-3xl font-bold text-violet-400">{{ stats.subscriptions || 0 }}</div>
          <div class="text-xs mt-1" style="color: var(--text-faint)">个订阅</div>
        </div>

        <div class="card p-5 animate-in" style="--stagger: 150">
          <div class="flex items-center justify-between mb-2">
            <div class="text-sm" style="color: var(--text-muted)">媒体总数</div>
            <div class="w-8 h-8 rounded-lg flex items-center justify-center bg-emerald-500/10">
              <svg class="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"/></svg>
            </div>
          </div>
          <div class="text-3xl font-bold text-emerald-400">{{ stats.media_total || 0 }}</div>
          <div class="text-xs mt-1" style="color: var(--text-faint)">部媒体</div>
        </div>
      </div>

      <!-- 快捷入口 -->
      <div>
        <h2 class="text-lg font-semibold mb-3">快捷入口</h2>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
          <router-link v-for="item in quickLinks" :key="item.path" :to="item.path"
            class="card p-4 flex items-center gap-3 hover:border-brand-500/50 transition-colors cursor-pointer">
            <div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" :style="{ background: item.color + '15' }">
              <component :is="item.icon" class="w-5 h-5" :style="{ color: item.color }" />
            </div>
            <div>
              <div class="text-sm font-medium">{{ item.label }}</div>
              <div class="text-xs" style="color: var(--text-muted)">{{ item.sub }}</div>
            </div>
          </router-link>
        </div>
      </div>

      <!-- 最近观看（最新3条） -->
      <div>
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-lg font-semibold">最近观看</h2>
          <router-link to="/history" class="text-sm hover:text-brand-400 transition-colors" style="color: var(--text-muted)">
            查看全部 →
          </router-link>
        </div>
        <div v-if="recentHistory.length > 0" class="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div v-for="item in recentHistory" :key="item.id"
            @click="$router.push(`/media/${item.media_item_id}`)"
            class="card p-3 cursor-pointer group hover:border-brand-500/50 transition-colors">
            <div class="flex items-center gap-3">
              <div class="w-12 h-18 rounded overflow-hidden bg-[var(--bg-input)] shrink-0">
                <img v-if="item.poster_url" :src="item.poster_url" :alt="item.media_title"
                  class="w-full h-full object-cover" loading="lazy" referrerpolicy="no-referrer"
                  @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />
                <div v-else class="w-full h-full flex items-center justify-center" style="color: var(--text-faint)">
                  <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"/></svg>
                </div>
              </div>
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium truncate">{{ item.media_title }}</div>
                <div class="text-xs mt-1" style="color: var(--text-muted)">{{ item.media_type === 'movie' ? '电影' : item.media_type === 'tv' ? '剧集' : '动漫' }}</div>
                <div class="mt-2">
                  <div class="progress-bar h-1"><div :style="{ width: watchPercent(item) + '%' }" /></div>
                  <div class="text-xs mt-1" style="color: var(--text-faint)">
                    {{ formatTime(item.progress) }} / {{ formatTime(item.duration) }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="card p-8 text-center" style="color: var(--text-muted)">
          <svg class="w-12 h-12 mx-auto mb-2 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          <div class="text-sm">还没有观看记录</div>
          <router-link to="/media" class="text-sm text-brand-400 hover:text-brand-300 mt-2 inline-block">去浏览媒体库</router-link>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h } from 'vue'
import { mediaApi } from '@/api/media'
import { authApi } from '@/api/auth'
import { subscribeApi } from '@/api/subscribe'
import { watchHistoryApi } from '@/api/system'

const loading = ref(true)
const user = ref<any>(null)
const stats = ref<any>({})
const recentHistory = ref<any[]>([])

const userInitials = computed(() => {
  const name = user.value?.username || '?'
  return name.slice(0, 2).toUpperCase()
})

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '—'
  try {
    return new Date(dateStr).toLocaleDateString('zh-CN')
  } catch { return '—' }
}

function watchPercent(item: any): number {
  if (!item.duration || item.duration === 0) return 0
  return Math.min(100, (item.progress / item.duration) * 100)
}

function formatTime(seconds: number): string {
  if (!seconds) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

// SVG 图标组件
const HistoryIcon = () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
  h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' })
])
const HeartIcon = () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
  h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z' })
])
const BellIcon = () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
  h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9' })
])
const FilmIcon = () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
  h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z' })
])

const quickLinks = [
  { path: '/history', label: '观看历史', sub: '回顾观影足迹', icon: HistoryIcon, color: '#60a5fa' },
  { path: '/favorites', label: '我的收藏', sub: '收藏的佳片', icon: HeartIcon, color: '#fbbf24' },
  { path: '/subscriptions', label: '订阅管理', sub: '追更的剧集', icon: BellIcon, color: '#a78bfa' },
  { path: '/media', label: '媒体库', sub: '浏览全部媒体', icon: FilmIcon, color: '#34d399' },
]

onMounted(async () => {
  try {
    // 并行加载用户信息、收藏数、订阅数
    const [userRes, favRes, subRes, mediaRes, histStatsRes, histRes] = await Promise.allSettled([
      authApi.getMe(),
      mediaApi.getFavorites({ page: 1, page_size: 1 }),
      subscribeApi.getSubscriptions(),
      mediaApi.getStats(),
      watchHistoryApi.getStats(),
      watchHistoryApi.getList({ limit: 3 }),
    ])

    if (userRes.status === 'fulfilled') user.value = userRes.value.data
    if (favRes.status === 'fulfilled') stats.value.favorites = favRes.value.data?.total || 0
    if (subRes.status === 'fulfilled') {
      const subData = subRes.value?.data
      stats.value.subscriptions = Array.isArray(subData) ? subData.length : (subData?.total || subData?.length || 0)
    }
    if (mediaRes.status === 'fulfilled') {
      stats.value.media_total = mediaRes.value.data?.total_items || 0
    }
    if (histStatsRes.status === 'fulfilled') {
      stats.value.watch_history = histStatsRes.value?.data?.total || 0
    }
    if (histRes.status === 'fulfilled') {
      const histData = histRes.value?.data
      recentHistory.value = Array.isArray(histData) ? histData : (histData?.items || [])
      // 如果 stats 未能获取，回退到列表长度
      if (!stats.value.watch_history) {
        stats.value.watch_history = recentHistory.value.length
      }
    }
  } catch (e) {
    console.error('Profile load error:', e)
  } finally {
    loading.value = false
  }
})
</script>
