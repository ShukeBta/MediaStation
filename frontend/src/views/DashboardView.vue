<template>
  <div class="p-4 md:p-6 max-w-7xl mx-auto space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold">Pulse 数据中心</h1>
      <button @click="refreshAll" class="btn-secondary text-sm flex items-center gap-2">
        <svg class="w-4 h-4" :class="{ 'animate-spin': loading }" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        刷新
      </button>
    </div>

    <!-- 统计概览卡片 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4 stagger-in">
      <template v-if="!stats.loaded">
        <div v-for="i in 4" :key="i" class="card p-5 animate-pulse">
          <div class="h-3 bg-[var(--bg-hover)] rounded w-16 mb-3" />
          <div class="h-8 bg-[var(--bg-hover)] rounded w-20" />
        </div>
      </template>
      <template v-else>
        <div class="card p-5 animate-in" style="--stagger: 0">
          <div class="flex items-center justify-between">
            <div class="text-sm" style="color: var(--text-muted)">媒体总数</div>
            <div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background: var(--accent-subtle)">
              <svg class="w-4 h-4" style="color: var(--accent)" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"/></svg>
            </div>
          </div>
          <div class="text-3xl font-bold mt-1">{{ stats.data.total_media || 0 }}</div>
          <div class="text-xs mt-1" style="color: var(--text-faint)">
            {{ stats.data.total_movies || 0 }} 电影 · {{ stats.data.total_tv || 0 }} 剧集
          </div>
        </div>
        <div class="card p-5 animate-in" style="--stagger: 50">
          <div class="flex items-center justify-between">
            <div class="text-sm" style="color: var(--text-muted)">今日播放</div>
            <div class="w-8 h-8 rounded-lg flex items-center justify-center bg-blue-500/10">
              <svg class="w-4 h-4 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            </div>
          </div>
          <div class="text-3xl font-bold mt-1 text-blue-400">{{ stats.data.today_plays || 0 }}</div>
          <div class="text-xs mt-1" style="color: var(--text-faint)">
            总播放 {{ stats.data.total_plays || 0 }}
          </div>
        </div>
        <div class="card p-5 animate-in" style="--stagger: 100">
          <div class="flex items-center justify-between">
            <div class="text-sm" style="color: var(--text-muted)">活跃用户</div>
            <div class="w-8 h-8 rounded-lg flex items-center justify-center bg-emerald-500/10">
              <svg class="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"/></svg>
            </div>
          </div>
          <div class="text-3xl font-bold mt-1 text-emerald-400">{{ stats.data.active_users || 0 }}</div>
          <div class="text-xs mt-1" style="color: var(--text-faint)">
            今日观看 {{ formatDuration(stats.data.today_watch_time || 0) }}
          </div>
        </div>
        <div class="card p-5 animate-in" style="--stagger: 150">
          <div class="flex items-center justify-between">
            <div class="text-sm" style="color: var(--text-muted)">总大小</div>
            <div class="w-8 h-8 rounded-lg flex items-center justify-center bg-violet-500/10">
              <svg class="w-4 h-4 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"/></svg>
            </div>
          </div>
          <div class="text-3xl font-bold mt-1 text-violet-400">{{ formatFileSize(stats.data.total_size || 0) }}</div>
          <div class="text-xs mt-1" style="color: var(--text-faint)">
            总观看 {{ formatDuration(stats.data.total_watch_time || 0) }}
          </div>
        </div>
      </template>
    </div>

    <!-- 系统监控 + 趋势图表 -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <!-- 系统监控 -->
      <div class="card p-5 animate-in" style="--stagger: 50">
        <h3 class="text-sm font-medium mb-4 flex items-center gap-2">
          <svg class="w-4 h-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"/></svg>
          系统监控
          <span v-if="monitor.data" class="text-xs px-2 py-0.5 rounded" style="background: var(--bg-hover)">
            {{ monitor.data.uptime }}
          </span>
        </h3>
        <div v-if="monitor.loading" class="space-y-3">
          <div v-for="i in 4" :key="i" class="animate-pulse">
            <div class="h-3 bg-[var(--bg-hover)] rounded w-16 mb-1" />
            <div class="h-4 bg-[var(--bg-hover)] rounded" />
          </div>
        </div>
        <div v-else-if="monitor.data" class="space-y-3">
          <!-- CPU -->
          <div>
            <div class="flex justify-between text-xs mb-1">
              <span style="color: var(--text-muted)">CPU</span>
              <span class="text-cyan-400">{{ (monitor.data.cpu_percent ?? 0).toFixed(1) }}%</span>
            </div>
            <div class="progress-bar h-2"><div :style="{ width: (monitor.data.cpu_percent ?? 0) + '%', background: 'var(--accent)' }" /></div>
          </div>
          <!-- 内存 -->
          <div>
            <div class="flex justify-between text-xs mb-1">
              <span style="color: var(--text-muted)">内存</span>
              <span class="text-emerald-400">{{ (monitor.data.memory_percent ?? 0).toFixed(1) }}%</span>
            </div>
            <div class="progress-bar h-2"><div :style="{ width: (monitor.data.memory_percent ?? 0) + '%', background: 'var(--accent)' }" /></div>
            <div class="text-xs mt-1" style="color: var(--text-faint)">
              {{ formatFileSize(monitor.data.memory_used) }} / {{ formatFileSize(monitor.data.memory_total) }}
            </div>
          </div>
          <!-- 磁盘 -->
          <div>
            <div class="flex justify-between text-xs mb-1">
              <span style="color: var(--text-muted)">磁盘</span>
              <span class="text-amber-400">{{ (monitor.data.disk_percent ?? 0).toFixed(1) }}%</span>
            </div>
            <div class="progress-bar h-2"><div :style="{ width: (monitor.data.disk_percent ?? 0) + '%', background: 'var(--accent)' }" /></div>
            <div class="text-xs mt-1" style="color: var(--text-faint)">
              {{ formatFileSize(monitor.data.disk_used) }} / {{ formatFileSize(monitor.data.disk_total) }}
            </div>
          </div>
          <!-- 网络 -->
          <div class="flex justify-between text-xs pt-2" style="border-top: 1px solid var(--border)">
            <span style="color: var(--text-muted)">↑ {{ formatFileSize(monitor.data.network_sent) }}</span>
            <span style="color: var(--text-muted)">↓ {{ formatFileSize(monitor.data.network_recv) }}</span>
          </div>
        </div>
        <div v-else class="text-sm" style="color: var(--text-faint)">加载失败</div>
      </div>

      <!-- 播放趋势图表 -->
      <div class="card p-5 lg:col-span-2 animate-in" style="--stagger: 100">
        <h3 class="text-sm font-medium mb-4 flex items-center gap-2">
          <svg class="w-4 h-4 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>
          播放趋势
        </h3>
        <!-- 时间范围选择 -->
        <div class="flex gap-2 mb-4">
          <button v-for="p in trendPeriodOptions" :key="p.value"
            @click="trendPeriod = p.value; fetchTrend()"
            class="text-xs px-3 py-1 rounded transition-colors"
            :class="trendPeriod === p.value ? 'btn-primary' : 'btn-secondary'">
            {{ p.label }}
          </button>
        </div>
        <!-- 图表 -->
        <div v-if="trend.data" class="min-h-[12rem]">
          <v-chart :option="trendChartOption" autoresize class="w-full h-48" />
        </div>
        <div v-else-if="trend.loading" class="h-48 flex items-center justify-center">
          <div class="animate-pulse w-full h-full bg-[var(--bg-hover)] rounded" />
        </div>
        <div v-else class="h-48 flex items-center justify-center" style="color: var(--text-faint)">
          暂无数据
        </div>
      </div>
    </div>

    <!-- 热门内容 + 用户活跃 -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <!-- 热门内容 -->
      <div class="card p-5 animate-in" style="--stagger: 150">
        <h3 class="text-sm font-medium mb-4 flex items-center gap-2">
          <svg class="w-4 h-4 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.879 16.121A3 3 0 1012.015 11L11 14H9c0 .768.293 1.536.879 2.121z"/></svg>
          热门内容
          <span class="text-xs px-2 py-0.5 rounded" style="background: var(--bg-hover)">
            {{ topContent.data?.period === '1d' ? '今日' : topContent.data?.period === '30d' ? '30天' : '7天' }}
          </span>
        </h3>
        <div v-if="topContent.loading" class="space-y-3">
          <div v-for="i in 5" :key="i" class="flex items-center gap-3 animate-pulse">
            <div class="w-6 h-6 bg-[var(--bg-hover)] rounded" />
            <div class="flex-1 h-10 bg-[var(--bg-hover)] rounded" />
          </div>
        </div>
        <div v-else-if="topContent.data?.items?.length" class="space-y-2">
          <div v-for="(item, index) in topContent.data.items.slice(0, 8)" :key="item.id"
            @click="$router.push(`/media/${item.id}`)"
            class="flex items-center gap-3 p-2 rounded-lg cursor-pointer hover:bg-[var(--bg-hover)] transition-colors group">
            <div class="w-6 text-center font-bold text-sm" :class="index < 3 ? 'text-amber-400' : ''" style="color: var(--text-muted)">
              {{ index + 1 }}
            </div>
            <div class="w-10 h-14 rounded overflow-hidden bg-[var(--bg-input)] shrink-0">
              <img v-if="item.poster_url" :src="item.poster_url" class="w-full h-full object-cover" />
            </div>
            <div class="flex-1 min-w-0">
              <div class="text-sm font-medium truncate group-hover:text-[var(--accent)]">{{ item.title }}</div>
              <div class="text-xs" style="color: var(--text-muted)">
                {{ item.play_count || 0 }} 次播放 · {{ formatDuration(item.watch_time || 0) }}
              </div>
            </div>
          </div>
        </div>
        <div v-else class="py-8 text-center" style="color: var(--text-faint)">暂无播放数据</div>
      </div>

      <!-- 活跃用户 -->
      <div class="card p-5 animate-in" style="--stagger: 200">
        <h3 class="text-sm font-medium mb-4 flex items-center gap-2">
          <svg class="w-4 h-4 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"/></svg>
          活跃用户
          <span class="text-xs px-2 py-0.5 rounded" style="background: var(--bg-hover)">
            {{ topUsers.data?.period === '1d' ? '今日' : topUsers.data?.period === '30d' ? '30天' : '7天' }}
          </span>
        </h3>
        <div v-if="topUsers.loading" class="space-y-3">
          <div v-for="i in 5" :key="i" class="flex items-center gap-3 animate-pulse">
            <div class="w-8 h-8 bg-[var(--bg-hover)] rounded-full" />
            <div class="flex-1 h-8 bg-[var(--bg-hover)] rounded" />
          </div>
        </div>
        <div v-else-if="topUsers.data?.items?.length" class="space-y-2">
          <div v-for="(item, index) in topUsers.data.items.slice(0, 8)" :key="item.id"
            class="flex items-center gap-3 p-2 rounded-lg hover:bg-[var(--bg-hover)] transition-colors">
            <div class="w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm"
              :class="index < 3 ? 'bg-amber-500/20 text-amber-400' : 'bg-[var(--bg-hover)]'"
              style="color: var(--text-muted)">
              {{ index + 1 }}
            </div>
            <div class="w-8 h-8 rounded-full overflow-hidden bg-[var(--bg-input)] shrink-0">
              <img v-if="item.avatar_url" :src="item.avatar_url" class="w-full h-full object-cover" referrerpolicy="no-referrer" />
              <div v-else class="w-full h-full flex items-center justify-center text-xs" style="color: var(--text-faint)">
                {{ (item.username || 'U')[0].toUpperCase() }}
              </div>
            </div>
            <div class="flex-1 min-w-0">
              <div class="text-sm font-medium truncate">{{ item.username || '未知用户' }}</div>
              <div class="text-xs" style="color: var(--text-muted)">
                {{ item.play_count || 0 }} 次播放
              </div>
            </div>
          </div>
        </div>
        <div v-else class="py-8 text-center" style="color: var(--text-faint)">暂无用户数据</div>
      </div>
    </div>

    <!-- 继续观看 + 最近添加 -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <!-- 继续观看 -->
      <div>
        <h2 class="text-lg font-semibold mb-3">继续观看</h2>
        <div v-if="!continueWatching.loaded" class="grid grid-cols-2 gap-3">
          <div v-for="i in 3" :key="i" class="card p-3 animate-pulse">
            <div class="h-24 bg-[var(--bg-hover)] rounded" />
          </div>
        </div>
        <div v-else-if="continueWatching.data.length > 0" class="grid grid-cols-2 gap-3 stagger-in">
          <div v-for="(item, index) in continueWatching.data" :key="item.id"
            @click="$router.push(`/media/${item.media_item_id}`)"
            class="card p-3 cursor-pointer group hover:border-[var(--accent)] transition-colors"
            :style="{ '--stagger': `${index * 40}ms` }">
            <div class="flex items-center gap-3">
              <div class="w-16 h-24 rounded overflow-hidden shrink-0 bg-[var(--bg-input)]">
                <img v-if="item.poster_url" :src="item.poster_url" :alt="item.media_title"
                  class="w-full h-full object-cover" loading="lazy" referrerpolicy="no-referrer"
                  @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />
                <div v-else class="w-full h-full flex items-center justify-center" style="color: var(--text-faint)">
                  <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/></svg>
                </div>
              </div>
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium truncate">{{ item.media_title }}</div>
                <div class="text-xs mt-1" style="color: var(--text-muted)">
                  {{ item.media_type === 'movie' ? '电影' : '剧集' }}
                </div>
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
        <div v-else>
          <AppEmpty message="暂无观看记录" />
        </div>
      </div>

      <!-- 最近添加 -->
      <div>
        <h2 class="text-lg font-semibold mb-3">最近添加</h2>
        <div v-if="!recent.loaded" class="flex gap-4 overflow-x-auto pb-2">
          <div v-for="i in 6" :key="i" class="shrink-0 w-36 animate-pulse">
            <div class="w-36 h-52 rounded-lg bg-[var(--bg-input)]" />
            <div class="h-4 bg-[var(--bg-input)] rounded mt-2 w-3/4" />
            <div class="h-3 bg-[var(--bg-input)] rounded mt-1 w-1/2" />
          </div>
        </div>
        <div v-else-if="recent.data.length > 0" class="flex gap-4 overflow-x-auto pb-2 stagger-in">
          <div v-for="(item, index) in recent.data" :key="item.id"
            @click="$router.push(`/media/${item.id}`)"
            class="shrink-0 w-36 cursor-pointer group"
            :style="{ '--stagger': `${index * 40}ms` }">
            <div class="w-36 h-52 rounded-lg bg-[var(--bg-input)] overflow-hidden mb-2 shadow-md group-hover:shadow-xl transition-shadow duration-300">
              <img v-if="item.poster_url" :src="item.poster_url" :alt="item.title"
                class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                loading="lazy" referrerpolicy="no-referrer"
                @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />
              <div v-else class="w-full h-full flex items-center justify-center" style="color: var(--text-faint)">
                <svg class="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"/></svg>
              </div>
            </div>
            <div class="text-sm font-medium truncate">{{ item.title }}</div>
            <div class="text-xs" style="color: var(--text-muted)">{{ item.year }} · {{ item.resolution || '未知' }}</div>
          </div>
        </div>
        <div v-else>
          <AppEmpty message="暂无媒体，请先添加媒体库并扫描" />
        </div>
      </div>
    </div>

    <!-- 定时任务 (仅管理员) -->
    <div v-if="isAdmin">
      <h2 class="text-lg font-semibold mb-3">定时任务</h2>
      <div v-if="!schedulerJobs.loaded" class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div v-for="i in 4" :key="i" class="card p-4 animate-pulse">
          <div class="h-4 bg-[var(--bg-hover)] rounded w-1/3" />
        </div>
      </div>
      <div v-else-if="schedulerJobs.data.length > 0" class="grid grid-cols-1 md:grid-cols-2 gap-3 stagger-in">
        <div v-for="(job, index) in schedulerJobs.data" :key="job.id"
          class="card p-4 flex items-center justify-between animate-in"
          :style="{ '--stagger': `${index * 50}ms` }">
          <div>
            <div class="text-sm font-medium">{{ job.name }}</div>
            <div class="text-xs mt-1" style="color: var(--text-muted)">
              {{ job.trigger }}
              <span v-if="job.next_run_time" class="ml-2">
                → {{ formatScheduleTime(job.next_run_time) }}
              </span>
            </div>
          </div>
          <button @click="triggerJob(job.id)"
            class="btn-secondary text-xs px-3 py-1.5"
            :disabled="triggeringJobs[job.id]">
            {{ triggeringJobs[job.id] ? '执行中...' : '立即执行' }}
          </button>
        </div>
      </div>
      <div v-else>
        <AppEmpty message="暂无定时任务" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { mediaApi } from '@/api/media'
import { systemApi, statsApi } from '@/api/system'
import { watchHistoryApi } from '@/api/system'
import { useFormat } from '@/composables/useFormat'
import AppEmpty from '@/components/AppEmpty.vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const { formatFileSize } = useFormat()

const loading = ref(false)
const trendPeriod = ref('7d')

// 趋势周期选项（与后端 API 参数一致：1d/7d/30d）
const trendPeriodOptions = [
  { value: '1d', label: '24小时' },
  { value: '7d', label: '7天' },
  { value: '30d', label: '30天' },
]

// 统计数据
const stats = reactive({ data: {} as any, loaded: false })
const monitor = reactive({ data: null as any, loading: false })
const trend = reactive({ data: null as any, loading: false })
const topContent = reactive({ data: null as any, loading: false })
const topUsers = reactive({ data: null as any, loading: false })
const recent = reactive({ data: [] as any[], loaded: false })
const continueWatching = reactive({ data: [] as any[], loaded: false })
const schedulerJobs = reactive({ data: [] as any[], loaded: false })
const triggeringJobs = ref<Record<string, boolean>>({})

const isAdmin = computed(() => {
  const user = JSON.parse(localStorage.getItem('ms-user') || '{}')
  return user.role === 'admin'
})

// 获取实际颜色值（用于 ECharts Canvas）
function getComputedColor(varName: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  const el = document.createElement('div')
  el.style.color = varName
  document.body.appendChild(el)
  const computed = getComputedStyle(el).color
  document.body.removeChild(el)
  return computed || fallback
}

// 趋势图表配置
const trendChartOption = computed(() => {
  if (!trend.data) return {}
  
  let chartData: { timestamp: string; value: number }[] = []

  // 根据后端返回的数据选择对应的时间粒度
  if (trendPeriod.value === '1d' && trend.data.hourly) {
    chartData = trend.data.hourly
  } else if (trend.data.daily) {
    chartData = trend.data.daily
  }
  
  // 获取实际颜色
  const accentColor = getComputedColor('var(--accent)', '#6366f1')
  const accentSoft = getComputedColor('var(--accent-soft)', 'rgba(99, 102, 241, 0.2)')
  const borderColor = getComputedColor('var(--border)', '#374151')
  const textMuted = getComputedColor('var(--text-muted)', '#9ca3af')
  
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const p = params[0]
        return `${p.name}<br/>播放: ${p.value}`
      }
    },
    grid: {
      left: 40,
      right: 20,
      top: 20,
      bottom: 30
    },
      xAxis: {
      type: 'category',
      data: chartData.map(d => {
        const t = new Date(d.timestamp)
        if (trendPeriod.value === '1d') {
          return `${t.getHours()}:00`
        }
        return `${t.getMonth() + 1}/${t.getDate()}`
      }),
      axisLine: { lineStyle: { color: borderColor } },
      axisLabel: { color: textMuted, fontSize: 10 }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: borderColor, type: 'dashed' } },
      axisLine: { show: false },
      axisLabel: { color: textMuted, fontSize: 10 }
    },
    series: [{
      data: chartData.map(d => d.value),
      type: 'line',
      smooth: true,
      lineStyle: { color: accentColor, width: 2 },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: accentSoft },
            { offset: 1, color: 'transparent' }
          ]
        }
      },
      symbol: 'circle',
      symbolSize: 6,
      itemStyle: { color: accentColor }
    }]
  }
})

function watchPercent(item: any): number {
  if (!item.duration || item.duration === 0) return 0
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

function formatDuration(seconds: number): string {
  if (!seconds) return '0分钟'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return `${h}小时${m}分钟`
  return `${m}分钟`
}

function formatScheduleTime(timeStr: string): string {
  try {
    const d = new Date(timeStr)
    const now = new Date()
    const diff = d.getTime() - now.getTime()
    if (diff < 0) return '即将执行'
    const minutes = Math.floor(diff / 60000)
    if (minutes < 60) return `${minutes}分钟后`
    const hours = Math.floor(minutes / 60)
    if (hours < 24) return `${hours}小时后`
    return d.toLocaleDateString('zh-CN')
  } catch {
    return timeStr
  }
}

async function triggerJob(jobId: string) {
  triggeringJobs.value[jobId] = true
  try {
    await systemApi.triggerJob(jobId)
  } catch (e) {
    console.error('Trigger job failed:', e)
  } finally {
    setTimeout(() => {
      triggeringJobs.value[jobId] = false
    }, 3000)
  }
}

async function fetchTrend() {
  trend.loading = true
  try {
    const res = await statsApi.getTrend({ period: trendPeriod.value })
    trend.data = res.data.data || res.data
  } catch (e) {
    console.error('Fetch trend failed:', e)
  } finally {
    trend.loading = false
  }
}

async function refreshAll() {
  loading.value = true
  try {
    await Promise.all([
      fetchStats(),
      fetchMonitor(),
      fetchTrend(),
      fetchTopContent(),
      fetchTopUsers(),
      fetchRecent(),
      fetchContinueWatching(),
      fetchSchedulerJobs(),
    ])
  } finally {
    loading.value = false
  }
}

async function fetchStats() {
  try {
    const res = await statsApi.getOverview()
    stats.data = res.data.data || res.data
  } catch (e) {
    console.error('Fetch stats failed:', e)
  } finally {
    stats.loaded = true
  }
}

async function fetchMonitor() {
  monitor.loading = true
  try {
    const res = await statsApi.getMonitor()
    monitor.data = res.data.data || res.data
  } catch (e) {
    console.error('Fetch monitor failed:', e)
  } finally {
    monitor.loading = false
  }
}

async function fetchTopContent() {
  topContent.loading = true
  try {
    const res = await statsApi.getTopContent({ period: '7d', limit: 10 })
    topContent.data = res.data.data || res.data
  } catch (e) {
    console.error('Fetch top content failed:', e)
  } finally {
    topContent.loading = false
  }
}

async function fetchTopUsers() {
  topUsers.loading = true
  try {
    const res = await statsApi.getTopUsers({ period: '7d', limit: 10 })
    topUsers.data = res.data.data || res.data
  } catch (e) {
    console.error('Fetch top users failed:', e)
  } finally {
    topUsers.loading = false
  }
}

async function fetchRecent() {
  try {
    const res = await mediaApi.getRecent(10)
    const data = res.data.data || res.data
    recent.data = data.items || (Array.isArray(data) ? data : [])
  } catch (e) {
    console.error('Fetch recent failed:', e)
  } finally {
    recent.loaded = true
  }
}

async function fetchContinueWatching() {
  try {
    const api = (await import('@/api/client')).default
    const res = await api.get('/api/watch-history/continue', { params: { limit: 6 } })
    const data = res.data.data || res.data
    const raw = Array.isArray(data) ? data : (data.items || [])
    continueWatching.data = raw.filter((item: any) => {
      if (!item.duration || item.duration === 0) return false
      if (!item.progress || item.progress <= 0) return false
      const pct = item.progress / item.duration
      return pct < 0.9
    })
  } catch {
    continueWatching.data = []
  } finally {
    continueWatching.loaded = true
  }
}

async function fetchSchedulerJobs() {
  if (!isAdmin.value) {
    schedulerJobs.loaded = true
    return
  }
  try {
    const res = await systemApi.getScheduledJobs()
    const data = res.data.data || res.data
    schedulerJobs.data = data.jobs || (Array.isArray(data) ? data : [])
  } catch (e) {
    console.error('Fetch scheduler jobs failed:', e)
  } finally {
    schedulerJobs.loaded = true
  }
}

onMounted(async () => {
  await refreshAll()
})
</script>
