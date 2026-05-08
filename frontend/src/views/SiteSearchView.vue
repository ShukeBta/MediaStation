<template>
  <div class="p-6 max-w-7xl mx-auto space-y-5 animate-in">
    <!-- 页头 -->
    <div class="flex items-center justify-between flex-wrap gap-3">
      <div>
        <h1 class="text-2xl font-bold text-[var(--text-primary)]">资源搜索</h1>
        <p class="text-sm text-[var(--text-muted)] mt-0.5">在已配置的 PT/BT 站点中手动搜索资源，一键发送到下载器</p>
      </div>
      <router-link to="/sites" class="btn-secondary text-xs flex items-center gap-1.5">
        <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
        </svg>
        管理站点
      </router-link>
    </div>

    <!-- 搜索栏 -->
    <div class="card p-4 space-y-3">
      <div class="flex gap-2">
        <div class="relative flex-1">
          <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-faint)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
          <input
            v-model="keyword"
            @keyup.enter="doSearch"
            placeholder="输入影片名称、关键词、番号..."
            class="input !pl-9 text-base"
            autofocus
          />
        </div>
        <button @click="doSearch" :disabled="searching || !keyword.trim()" class="btn-primary min-w-[88px] flex items-center justify-center gap-1.5">
          <svg v-if="searching" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
          <svg v-else class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
          {{ searching ? '搜索中' : '搜 索' }}
        </button>
      </div>

      <!-- 过滤条件 -->
      <div class="flex flex-wrap gap-2 items-center">
        <!-- 站点过滤 -->
        <div class="flex items-center gap-1.5 text-sm text-[var(--text-muted)]">
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"/>
          </svg>
          <span>站点：</span>
        </div>
        <button
          @click="toggleSite(null)"
          :class="['text-xs px-2.5 py-1 rounded-full border transition-all', !selectedSiteIds.length ? 'border-brand-500 bg-brand-500/10 text-brand-400' : 'border-[var(--border-primary)] text-[var(--text-muted)] hover:border-brand-500/50']"
        >全部</button>
        <button
          v-for="site in enabledSites"
          :key="site.id"
          @click="toggleSite(site.id)"
          :class="['text-xs px-2.5 py-1 rounded-full border transition-all', selectedSiteIds.includes(site.id) ? 'border-brand-500 bg-brand-500/10 text-brand-400' : 'border-[var(--border-primary)] text-[var(--text-muted)] hover:border-brand-500/50']"
        >{{ site.name }}</button>

        <div class="flex-1"/>

        <!-- 排序 -->
        <div class="flex items-center gap-1.5">
          <span class="text-xs text-[var(--text-faint)]">排序：</span>
          <select v-model="sortMode" class="input !py-1 !text-xs !px-2" style="height:28px">
            <option value="default">默认</option>
            <option value="size_desc">大小↓</option>
            <option value="size_asc">大小↑</option>
            <option value="seeders_desc">做种↓</option>
            <option value="time_desc">时间↓</option>
          </select>
        </div>

        <!-- FREE 过滤 -->
        <button
          @click="freeOnly = !freeOnly"
          :class="['text-xs px-2.5 py-1 rounded-full border transition-all flex items-center gap-1',
            freeOnly ? 'border-green-500 bg-green-500/10 text-green-400' : 'border-[var(--border-primary)] text-[var(--text-muted)] hover:border-green-500/50']"
        >
          <span class="w-1.5 h-1.5 rounded-full" :class="freeOnly ? 'bg-green-400' : 'bg-[var(--text-faint)]'"></span>
          FREE 专区
        </button>
      </div>
    </div>

    <!-- 结果统计栏 -->
    <div v-if="hasSearched" class="flex items-center justify-between text-sm">
      <span class="text-[var(--text-muted)]">
        <template v-if="searching">搜索中...</template>
        <template v-else>
          找到 <b class="text-[var(--text-primary)]">{{ sortedResults.length }}</b> 个资源
          <span v-if="selectedSiteIds.length" class="ml-1 text-[var(--text-faint)]">（来自 {{ selectedSiteIds.length }} 个站点）</span>
        </template>
      </span>
      <button v-if="results.length" @click="clearResults" class="text-xs text-[var(--text-faint)] hover:text-[var(--text-muted)] transition-colors">清除结果</button>
    </div>

    <!-- 搜索结果 -->
    <div v-if="sortedResults.length > 0" class="space-y-2">
      <div
        v-for="(res, idx) in paginatedResults"
        :key="idx"
        class="card p-3.5 hover:border-[var(--border-secondary)] transition-all group"
      >
        <div class="flex items-start gap-3">
          <!-- 序号 -->
          <span class="text-xs text-[var(--text-faint)] w-5 shrink-0 pt-0.5 text-right select-none">{{ (currentPage - 1) * pageSize + idx + 1 }}</span>

          <!-- 标题区 -->
          <div class="flex-1 min-w-0">
            <div class="flex items-start gap-2 flex-wrap">
              <span class="font-medium text-[var(--text-primary)] leading-snug break-all">{{ res.title }}</span>
              <span v-if="res.free" class="shrink-0 text-xs px-1.5 py-0.5 rounded bg-green-500/15 text-green-400 font-medium">FREE</span>
              <span v-if="res.hr" class="shrink-0 text-xs px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400">HR</span>
            </div>
            <!-- 元数据行 -->
            <div class="flex items-center gap-3 mt-1.5 flex-wrap text-xs text-[var(--text-faint)]">
              <span class="px-1.5 py-0.5 rounded text-[var(--text-muted)]" style="background: var(--bg-input)">
                {{ res.site_name || '未知站点' }}
              </span>
              <span v-if="res.size" class="flex items-center gap-0.5">
                <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
                {{ formatFileSize(res.size) }}
              </span>
              <span v-if="res.seeders !== null && res.seeders !== undefined" class="flex items-center gap-0.5 text-green-500">
                <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 10l7-7m0 0l7 7m-7-7v18"/></svg>
                {{ res.seeders }}
              </span>
              <span v-if="res.leechers !== null && res.leechers !== undefined" class="flex items-center gap-0.5 text-red-400">
                <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3"/></svg>
                {{ res.leechers }}
              </span>
              <span v-if="res.completed_times" class="flex items-center gap-0.5">
                <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                {{ res.completed_times }}
              </span>
              <span v-if="res.publish_date" class="flex items-center gap-0.5">
                <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
                {{ formatDate(res.publish_date) }}
              </span>
              <span v-if="res.category" class="text-[var(--text-faint)]">{{ res.category }}</span>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="flex items-center gap-2 shrink-0 mt-0.5">
            <!-- 选择下载客户端下载 -->
            <div class="relative" v-if="downloaders.length > 1">
              <button
                @click="toggleDownloaderMenu(idx)"
                class="btn-primary text-xs flex items-center gap-1 !py-1.5"
              >
                <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
                下载
                <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
              </button>
              <!-- 下载器下拉菜单 -->
              <div v-if="downloaderMenuIdx === idx"
                class="absolute right-0 top-full mt-1 z-50 card !p-1 shadow-lg min-w-[140px]">
                <button
                  v-for="dl in downloaders" :key="dl.id"
                  @click="downloadTo(res, dl.id)"
                  class="w-full text-left text-xs px-3 py-2 rounded hover:bg-[var(--bg-hover)] transition-colors text-[var(--text-primary)] flex items-center gap-2"
                >
                  <span class="w-1.5 h-1.5 rounded-full bg-green-400"></span>
                  {{ dl.name }}
                </button>
              </div>
            </div>
            <button
              v-else
              @click="downloadResource(res)"
              :disabled="downloadingIdx === idx"
              class="btn-primary text-xs flex items-center gap-1 !py-1.5 disabled:opacity-60"
            >
              <svg v-if="downloadingIdx === idx" class="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
              <svg v-else class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
              {{ downloadingIdx === idx ? '...' : '下载' }}
            </button>
            <!-- 订阅按钮 -->
            <button
              @click="subscribeResource(res)"
              class="btn-secondary text-xs flex items-center gap-1 !py-1.5"
              title="添加到订阅"
            >
              <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/></svg>
              订阅
            </button>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="totalPages > 1" class="flex items-center justify-center gap-1 pt-2">
        <button @click="currentPage = 1" :disabled="currentPage === 1" class="btn-secondary text-xs !px-2 !py-1 disabled:opacity-40">«</button>
        <button @click="currentPage--" :disabled="currentPage === 1" class="btn-secondary text-xs !px-2 !py-1 disabled:opacity-40">‹</button>
        <span class="text-xs text-[var(--text-muted)] px-3">第 {{ currentPage }} / {{ totalPages }} 页</span>
        <button @click="currentPage++" :disabled="currentPage === totalPages" class="btn-secondary text-xs !px-2 !py-1 disabled:opacity-40">›</button>
        <button @click="currentPage = totalPages" :disabled="currentPage === totalPages" class="btn-secondary text-xs !px-2 !py-1 disabled:opacity-40">»</button>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="hasSearched && !searching" class="card p-12 flex flex-col items-center gap-3 text-center">
      <svg class="w-12 h-12 text-[var(--text-faint)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
      </svg>
      <div>
        <p class="font-medium text-[var(--text-secondary)]">未找到资源</p>
        <p class="text-sm text-[var(--text-faint)] mt-1">尝试其他关键词，或检查站点配置</p>
      </div>
    </div>

    <!-- 初始提示 -->
    <div v-else-if="!hasSearched" class="space-y-4">
      <!-- 快捷搜索标签 -->
      <div class="card p-4">
        <p class="text-sm text-[var(--text-muted)] mb-3">热门搜索：</p>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="tag in quickTags"
            :key="tag"
            @click="quickSearch(tag)"
            class="text-xs px-3 py-1.5 rounded-full border border-[var(--border-primary)] text-[var(--text-muted)] hover:border-brand-500/50 hover:text-brand-400 transition-all"
          >{{ tag }}</button>
        </div>
      </div>

      <!-- 站点状态 -->
      <div v-if="enabledSites.length === 0" class="card p-8 flex flex-col items-center gap-3 text-center">
        <svg class="w-10 h-10 text-[var(--text-faint)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/>
        </svg>
        <div>
          <p class="font-medium text-[var(--text-secondary)]">尚未配置站点</p>
          <p class="text-sm text-[var(--text-faint)] mt-1">需要先添加 PT/BT 站点才能搜索资源</p>
        </div>
        <router-link to="/sites" class="btn-primary text-sm">前往配置站点</router-link>
      </div>
      <div v-else class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        <div
          v-for="site in enabledSites"
          :key="site.id"
          class="card p-3 flex items-center gap-2.5 hover:border-[var(--border-secondary)] transition-all cursor-pointer"
          @click="searchWithSite(site)"
        >
          <div :class="['w-7 h-7 rounded-md flex items-center justify-center text-xs font-bold shrink-0', siteTypeBg(site.site_type)]">
            {{ site.name.slice(0, 2) }}
          </div>
          <div class="min-w-0">
            <div class="text-sm font-medium text-[var(--text-primary)] truncate">{{ site.name }}</div>
            <div class="flex items-center gap-1 mt-0.5">
              <span :class="['w-1.5 h-1.5 rounded-full', site.login_status === 'ok' ? 'bg-green-400' : site.login_status === 'failed' ? 'bg-red-400' : 'bg-[var(--text-faint)]']"></span>
              <span class="text-xs text-[var(--text-faint)]">{{ site.login_status === 'ok' ? '正常' : site.login_status === 'failed' ? '失败' : '未测试' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 下载客户端选择弹窗 -->
    <AppModal
      :show="subscribeModal.visible"
      title="添加订阅"
      max-width="460px"
      @close="subscribeModal.visible = false"
    >
      <div class="space-y-4">
        <div>
          <label class="form-label">影片名称 *</label>
          <input v-model="subscribeModal.title" class="input" placeholder="请输入影片名称" />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="form-label">媒体类型</label>
            <select v-model="subscribeModal.mediaType" class="input">
              <option value="movie">电影</option>
              <option value="tv">剧集</option>
              <option value="anime">动漫</option>
            </select>
          </div>
          <div>
            <label class="form-label">分辨率偏好</label>
            <select v-model="subscribeModal.quality" class="input">
              <option value="">不限</option>
              <option value="2160p">4K (2160p)</option>
              <option value="1080p">1080p</option>
              <option value="720p">720p</option>
            </select>
          </div>
        </div>
        <div class="flex gap-2 pt-2">
          <button @click="subscribeModal.visible = false" class="btn-secondary flex-1">取消</button>
          <button @click="confirmSubscribe" :disabled="!subscribeModal.title.trim() || subscribeModal.saving" class="btn-primary flex-1">
            {{ subscribeModal.saving ? '添加中...' : '确认订阅' }}
          </button>
        </div>
      </div>
    </AppModal>

    <!-- Toast -->
    <teleport to="body">
      <div class="fixed bottom-5 right-5 space-y-2 z-[9999]">
        <transition-group name="toast-slide">
          <div
            v-for="t in toasts"
            :key="t.id"
            :class="['flex items-center gap-2 px-4 py-2.5 rounded-lg shadow-lg text-sm font-medium',
              t.type === 'success' ? 'bg-green-600 text-white' :
              t.type === 'error' ? 'bg-red-600 text-white' : 'bg-[var(--bg-card)] border border-[var(--border-primary)] text-[var(--text-primary)]']"
          >
            <svg v-if="t.type === 'success'" class="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
            <svg v-else-if="t.type === 'error'" class="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
            {{ t.msg }}
          </div>
        </transition-group>
      </div>
    </teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppModal from '@/components/AppModal.vue'
import api from '@/api/client'

const route = useRoute()
const router = useRouter()

// ── State ──────────────────────────────────────────────────────────────────
const keyword = ref('')
const searching = ref(false)
const hasSearched = ref(false)
const results = ref<any[]>([])
const sites = ref<any[]>([])
const downloaders = ref<any[]>([])
const selectedSiteIds = ref<number[]>([])
const sortMode = ref('default')
const freeOnly = ref(false)
const currentPage = ref(1)
const pageSize = 30
const downloadingIdx = ref<number | null>(null)
const downloaderMenuIdx = ref<number | null>(null)

const subscribeModal = ref({
  visible: false,
  title: '',
  mediaType: 'movie' as 'movie' | 'tv' | 'anime',
  quality: '',
  siteId: null as number | null,
  saving: false,
})

const toasts = ref<Array<{ id: number; type: 'success' | 'error' | 'info'; msg: string }>>([])
let toastSeq = 0

const quickTags = [
  '2024 4K 电影', '日剧 2024', '韩剧 2024', '国剧 2024',
  '动漫 2024', 'HEVC 10bit', 'BD Remux', 'FLAC 高码',
]

// ── Computed ───────────────────────────────────────────────────────────────
const enabledSites = computed(() => sites.value.filter(s => s.enabled))

const filteredResults = computed(() => {
  let list = results.value
  if (selectedSiteIds.value.length) {
    list = list.filter(r => selectedSiteIds.value.includes(r.site_id))
  }
  if (freeOnly.value) {
    list = list.filter(r => r.free)
  }
  return list
})

const sortedResults = computed(() => {
  const list = [...filteredResults.value]
  switch (sortMode.value) {
    case 'size_desc': return list.sort((a, b) => (b.size || 0) - (a.size || 0))
    case 'size_asc': return list.sort((a, b) => (a.size || 0) - (b.size || 0))
    case 'seeders_desc': return list.sort((a, b) => (b.seeders || 0) - (a.seeders || 0))
    case 'time_desc': return list.sort((a, b) => (b.publish_date || '').localeCompare(a.publish_date || ''))
    default: return list
  }
})

const totalPages = computed(() => Math.ceil(sortedResults.value.length / pageSize))

const paginatedResults = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return sortedResults.value.slice(start, start + pageSize)
})

// ── Helpers ─────────────────────────────────────────────────────────────────
function formatFileSize(bytes: number | null | undefined): string {
  if (!bytes) return ''
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let val = bytes
  let idx = 0
  while (val >= 1024 && idx < units.length - 1) { val /= 1024; idx++ }
  return `${val.toFixed(idx > 1 ? 1 : 0)} ${units[idx]}`
}

function formatDate(dt: string | null | undefined): string {
  if (!dt) return ''
  const d = new Date(dt)
  if (isNaN(d.getTime())) return dt
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function siteTypeBg(type: string): string {
  const map: Record<string, string> = {
    mteam: 'bg-amber-500/20 text-amber-400',
    nexusphp: 'bg-blue-500/20 text-blue-400',
    unit3d: 'bg-purple-500/20 text-purple-400',
    gazelle: 'bg-green-500/20 text-green-400',
  }
  return map[type] || 'bg-[var(--bg-input)] text-[var(--text-muted)]'
}

function showToast(type: 'success' | 'error' | 'info', msg: string) {
  const id = ++toastSeq
  toasts.value.push({ id, type, msg })
  setTimeout(() => { toasts.value = toasts.value.filter(t => t.id !== id) }, 3500)
}

// ── Data Loading ────────────────────────────────────────────────────────────
async function loadSites() {
  try {
    const { data } = await api.get('/sites')
    sites.value = Array.isArray(data) ? data : (data.items || [])
  } catch {}
}

async function loadDownloaders() {
  try {
    const { data } = await api.get('/download/configs')
    downloaders.value = Array.isArray(data) ? data : (data.items || data.configs || [])
  } catch {
    downloaders.value = []
  }
}

// ── Search ──────────────────────────────────────────────────────────────────
async function doSearch() {
  if (!keyword.value.trim()) return
  searching.value = true
  hasSearched.value = true
  results.value = []
  currentPage.value = 1

  try {
    const params: Record<string, any> = { keyword: keyword.value.trim() }
    if (selectedSiteIds.value.length) {
      params.site_ids = selectedSiteIds.value.join(',')
    }
    const { data } = await api.get('/search/sites', { params })
    results.value = Array.isArray(data) ? data : (data.results || data.items || [])
  } catch (e: any) {
    showToast('error', `搜索失败：${e.response?.data?.detail || e.message || '请检查站点配置'}`)
  } finally {
    searching.value = false
  }
}

function quickSearch(tag: string) {
  keyword.value = tag
  doSearch()
}

function searchWithSite(site: any) {
  selectedSiteIds.value = [site.id]
  if (!keyword.value.trim()) {
    keyword.value = ''
  } else {
    doSearch()
  }
}

function clearResults() {
  results.value = []
  hasSearched.value = false
  keyword.value = ''
}

// ── Filters ──────────────────────────────────────────────────────────────────
function toggleSite(id: number | null) {
  if (id === null) {
    selectedSiteIds.value = []
    return
  }
  const idx = selectedSiteIds.value.indexOf(id)
  if (idx >= 0) selectedSiteIds.value.splice(idx, 1)
  else selectedSiteIds.value.push(id)
  currentPage.value = 1
}

// ── Download ─────────────────────────────────────────────────────────────────
function toggleDownloaderMenu(idx: number) {
  downloaderMenuIdx.value = downloaderMenuIdx.value === idx ? null : idx
}

async function downloadResource(res: any, downloaderId?: string) {
  const pIdx = paginatedResults.value.indexOf(res)
  downloadingIdx.value = pIdx
  downloaderMenuIdx.value = null
  try {
    await api.post('/download/tasks', {
      torrent_url: res.download_url || res.torrent_url || res.magnet_link,
      site_id: res.site_id,
      title: res.title,
      downloader_id: downloaderId,
    })
    showToast('success', `「${res.title.slice(0, 30)}」已添加到下载队列`)
  } catch (e: any) {
    showToast('error', `下载失败：${e.response?.data?.detail || e.message}`)
  } finally {
    downloadingIdx.value = null
  }
}

function downloadTo(res: any, downloaderId: string) {
  downloadResource(res, downloaderId)
}

// ── Subscribe ────────────────────────────────────────────────────────────────
function subscribeResource(res: any) {
  subscribeModal.value = {
    visible: true,
    title: res.title || '',
    mediaType: 'movie',
    quality: '',
    siteId: res.site_id || null,
    saving: false,
  }
}

async function confirmSubscribe() {
  if (!subscribeModal.value.title.trim()) return
  subscribeModal.value.saving = true
  try {
    await api.post('/subscriptions', {
      title: subscribeModal.value.title.trim(),
      media_type: subscribeModal.value.mediaType,
      quality: subscribeModal.value.quality || null,
      preferred_site_ids: subscribeModal.value.siteId ? [subscribeModal.value.siteId] : [],
    })
    showToast('success', `「${subscribeModal.value.title}」订阅已添加`)
    subscribeModal.value.visible = false
  } catch (e: any) {
    showToast('error', `订阅失败：${e.response?.data?.detail || e.message}`)
  } finally {
    subscribeModal.value.saving = false
  }
}

// ── Lifecycle ────────────────────────────────────────────────────────────────
function handleClickOutside(e: MouseEvent) {
  if (downloaderMenuIdx.value !== null) {
    downloaderMenuIdx.value = null
  }
}

onMounted(async () => {
  await Promise.all([loadSites(), loadDownloaders()])

  // URL 参数：?q=keyword
  const q = route.query.q as string
  if (q) {
    keyword.value = q
    await doSearch()
    router.replace({ path: '/site-search' })
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.form-label {
  @apply block text-sm text-[var(--text-muted)] mb-1.5 font-medium;
}
.toast-slide-enter-active,
.toast-slide-leave-active {
  transition: all 0.25s ease;
}
.toast-slide-enter-from {
  opacity: 0;
  transform: translateX(20px);
}
.toast-slide-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>
