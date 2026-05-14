<template>
  <!-- 登录页：独立全屏渲染，不包含侧边栏布局 -->
  <router-view v-if="isGuestPage" v-slot="{ Component }">
    <Transition name="page" mode="out-in">
      <component :is="Component" />
    </Transition>
  </router-view>

  <!-- 主应用布局：侧边栏 + 内容区 -->
  <div v-else class="flex h-screen overflow-hidden">
    <!-- 移动端遮罩 -->
    <Transition name="fade">
      <div v-if="sidebarOpen" class="fixed inset-0 z-40 bg-black/50 md:hidden" @click="sidebarOpen = false" />
    </Transition>

    <!-- 侧边栏 -->
    <aside :class="[
      'fixed md:static inset-y-0 left-0 z-50 flex flex-col shrink-0 w-64 border-r transition-transform duration-300 ease-out',
      'bg-[var(--bg-sidebar)] border-[var(--border-primary)]',
      sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0',
    ]">
      <!-- Logo -->
      <div class="p-5 border-b border-[var(--border-primary)] flex items-center justify-between">
        <router-link to="/" @click="sidebarOpen = false" class="flex items-center gap-2 text-xl font-bold">
          <span class="text-brand-500">▶</span>
          <span class="text-gradient">MediaStation</span>
        </router-link>
        <!-- 移动端关闭按钮 -->
        <button @click="sidebarOpen = false" class="md:hidden text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors">
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
      </div>

      <!-- 全局搜索框 -->
      <div class="px-3 py-3 border-b border-[var(--border-primary)]">
        <div class="relative">
          <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none" style="color: var(--text-muted)" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
          <input
            ref="searchInputRef"
            v-model="searchQuery"
            @input="onSearchInput"
            @focus="showResults = true"
            @keydown.escape="closeSearch"
            @keydown.enter="goToFirstResult"
            @keydown.up.prevent="navigateResults(-1)"
            @keydown.down.prevent="navigateResults(1)"
            type="text"
            placeholder="搜索媒体... ⌘K"
            class="w-full !pl-9 !pr-3 !py-2 text-sm rounded-lg border border-[var(--border-primary)] bg-[var(--bg-input)] focus:border-brand-500/60 focus:outline-none transition-colors"
            :style="{ color: 'var(--text-primary)' }"
          />
          <!-- 搜索结果下拉 -->
          <Transition name="dropdown">
            <div v-if="showResults && (searchResults.length > 0 || searchLoading)"
              class="absolute top-full left-0 right-0 mt-1 z-50 border rounded-lg shadow-xl overflow-hidden"
              style="background: var(--bg-secondary); border-color: var(--border-primary); max-height: 400px; overflow-y: auto;">
              <!-- 加载中 -->
              <div v-if="searchLoading" class="p-4 text-center" style="color: var(--text-muted)">
                <div class="inline-block w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
                <div class="text-xs mt-2">搜索中...</div>
              </div>
              <!-- 结果列表 -->
              <template v-else>
                <div v-if="searchResults.length === 0 && searchQuery.length > 0"
                  class="p-4 text-center text-sm" style="color: var(--text-muted)">
                  未找到「{{ searchQuery }}」
                </div>
                <div v-for="(item, idx) in searchResults" :key="item.id"
                  @click="goToMedia(item)"
                  :class="['flex items-center gap-3 px-3 py-2.5 cursor-pointer transition-colors', highlightedIdx === idx ? 'bg-brand-500/10' : 'hover:bg-[var(--bg-hover)]']">
                  <div class="w-10 h-14 rounded overflow-hidden bg-[var(--bg-input)] shrink-0">
                    <img v-if="item.poster_url" :src="item.poster_url" :alt="item.title" class="w-full h-full object-cover" referrerpolicy="no-referrer" @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />
                    <div v-else class="w-full h-full flex items-center justify-center" style="color: var(--text-faint)">
                      <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"/></svg>
                    </div>
                  </div>
                  <div class="flex-1 min-w-0">
                    <div class="text-sm font-medium truncate" style="color: var(--text-primary)">{{ item.title }}</div>
                    <div class="flex items-center gap-1.5 mt-0.5">
                      <span class="text-[10px] px-1 py-0.5 rounded"
                        :class="{
                          'bg-blue-500/15 text-blue-400': item.media_type === 'movie',
                          'bg-emerald-500/15 text-emerald-400': item.media_type === 'tv',
                          'bg-pink-500/15 text-pink-400': item.media_type === 'anime',
                        }">
                        {{ item.media_type === 'movie' ? '电影' : item.media_type === 'tv' ? '剧集' : '动漫' }}
                      </span>
                      <span class="text-xs" style="color: var(--text-muted)">{{ item.year || '—' }}</span>
                    </div>
                  </div>
                </div>
                <div v-if="searchResults.length > 0" class="px-3 py-2 text-xs text-center border-t" style="color: var(--text-faint); border-color: var(--border-primary)">
                  共 {{ searchResults.length }} 条结果 · 按 Enter 跳转
                </div>
              </template>
            </div>
          </Transition>
        </div>
      </div>

      <!-- 导航 -->
      <nav class="flex-1 overflow-y-auto p-3 space-y-1">
        <router-link v-for="item in navItems" :key="item.path"
          :to="item.path"
          @click="sidebarOpen = false"
          :class="['nav-item', { active: isActiveRoute(item.path) }]">
          <component :is="item.icon" class="w-5 h-5" />
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <!-- 底部：主题切换 + 用户信息 -->
      <div class="p-4 border-t border-[var(--border-primary)] space-y-3">
        <!-- 主题切换 -->
        <button @click="toggleDark()"
          class="flex items-center gap-2 w-full text-sm px-3 py-2 rounded-lg transition-colors"
          :class="isDark ? 'text-amber-400 hover:bg-amber-400/10' : 'text-indigo-500 hover:bg-indigo-500/10'">
          <!-- Sun icon (light mode) -->
          <svg v-if="isDark" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>
          </svg>
          <!-- Moon icon (dark mode) -->
          <svg v-else class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/>
          </svg>
          <span>{{ isDark ? '浅色模式' : '深色模式' }}</span>
        </button>

        <!-- 用户信息 -->
        <div class="flex items-center justify-between">
          <router-link to="/profile" @click="sidebarOpen = false"
            class="flex items-center gap-2 text-sm flex-1 min-w-0 hover:text-brand-400 transition-colors">
            <div class="w-8 h-8 rounded-full bg-brand-500/20 text-brand-400 flex items-center justify-center text-sm font-bold shrink-0">
              {{ userInitials }}
            </div>
            <div class="text-sm min-w-0">
              <div class="font-medium truncate" style="color: var(--text-primary)">{{ auth.user?.username || '用户' }}</div>
              <div class="text-xs truncate" style="color: var(--text-muted)">{{ auth.user?.role === 'admin' ? '管理员' : '用户' }}</div>
            </div>
          </router-link>
          <button @click="auth.logout()" class="hover:text-red-400 transition-colors ml-2" style="color: var(--text-muted)" title="退出登录">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg>
          </button>
        </div>
      </div>
    </aside>

    <!-- 主内容区域 -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- 移动端顶栏 -->
      <header class="md:hidden flex items-center gap-3 px-4 py-3 border-b border-[var(--border-primary)] bg-[var(--bg-secondary)]">
        <button @click="sidebarOpen = true" style="color: var(--text-muted)" class="hover:text-[var(--text-primary)] transition-colors">
          <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/></svg>
        </button>
        <router-link to="/" class="flex items-center gap-2 text-lg font-bold">
          <span class="text-brand-500">▶</span>
          <span class="text-gradient">MediaStation</span>
        </router-link>
      </header>

      <!-- 页面内容 -->
      <main class="flex-1 overflow-y-auto">
        <router-view v-slot="{ Component }">
          <Transition name="page" mode="out-in">
            <component :is="Component" />
          </Transition>
        </router-view>
      </main>
    </div>

    <!-- 全局 Toast + 确认弹窗 + 后端状态 -->
    <AppToast />
    <BackendStatus />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppToast from '@/components/AppToast.vue'
import BackendStatus from '@/components/BackendStatus.vue'
import { mediaApi } from '@/api/media'
import { startAutoRefresh, stopAutoRefresh } from '@/api/client'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const sidebarOpen = ref(false)

/** 登录页等 guest 页面独立渲染，不显示侧边栏布局 */
const isGuestPage = computed(() => route.meta.guest === true)

/* ====== 全局搜索 ====== */
const searchInputRef = ref<HTMLInputElement | null>(null)
const searchQuery = ref('')
const searchResults = ref<any[]>([])
const searchLoading = ref(false)
const showResults = ref(false)
const highlightedIdx = ref(-1)
let searchTimer: ReturnType<typeof setTimeout> | null = null

const userInitials = computed(() => {
  const name = auth.user?.username || '?'
  return name.slice(0, 2).toUpperCase()
})

async function onSearchInput() {
  highlightedIdx.value = -1
  if (searchTimer) clearTimeout(searchTimer)
  if (searchQuery.value.trim().length < 1) {
    searchResults.value = []
    showResults.value = false
    return
  }
  searchTimer = setTimeout(async () => {
    searchLoading.value = true
    showResults.value = true
    try {
      const res = await mediaApi.search(searchQuery.value.trim(), 8)
      searchResults.value = res.data || []
    } catch {
      searchResults.value = []
    } finally {
      searchLoading.value = false
    }
  }, 250)
}

function closeSearch() {
  showResults.value = false
  searchQuery.value = ''
  searchResults.value = []
  highlightedIdx.value = -1
  searchInputRef.value?.blur()
}

function navigateResults(dir: number) {
  if (searchResults.value.length === 0) return
  highlightedIdx.value = Math.max(0, Math.min(searchResults.value.length - 1, highlightedIdx.value + dir))
}

function goToFirstResult() {
  if (highlightedIdx.value >= 0 && searchResults.value[highlightedIdx.value]) {
    goToMedia(searchResults.value[highlightedIdx.value])
  } else if (searchResults.value.length > 0) {
    goToMedia(searchResults.value[0])
  }
}

function goToMedia(item: any) {
  closeSearch()
  router.push(`/media/${item.id}`)
}

/* ====== 键盘快捷键 Ctrl+K / Cmd+K ====== */
function handleKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault()
    searchInputRef.value?.focus()
    showResults.value = true
  }
  // 点击外部关闭搜索结果
  if (!showResults.value) return
  const target = e.target as HTMLElement
  if (!target.closest('.relative')) {
    showResults.value = false
  }
}

/* ====== 主题管理 ====== */
const isDark = ref(true)

function toggleDark() {
  isDark.value = !isDark.value
  document.documentElement.classList.toggle('dark', isDark.value)
  localStorage.setItem('ms-theme', isDark.value ? 'dark' : 'light')
}

onMounted(() => {
  // 初始化用户信息
  if (auth.isAuthenticated && !auth.user) {
    auth.fetchMe()
  }
  // 启动 token 主动续期
  startAutoRefresh()
  // 读取主题偏好
  const saved = localStorage.getItem('ms-theme')
  if (saved) {
    isDark.value = saved === 'dark'
    document.documentElement.classList.toggle('dark', isDark.value)
  } else {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    isDark.value = prefersDark
    document.documentElement.classList.toggle('dark', prefersDark)
  }
  // 键盘快捷键
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
  stopAutoRefresh()
})

/* ====== 路由激活判断 ====== */
function isActiveRoute(path: string): boolean {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}

/* ====== 导航配置 ====== */
const allNavItems = [
  {
    path: '/',
    label: '仪表盘',
    adminOnly: false,
    requiredPermission: 'can_view_dashboard' as const,
    icon: () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' })
    ]),
  },
  {
    path: '/discover',
    label: '发现',
    adminOnly: false,
    requiredPermission: 'can_view_discover' as const,
    icon: () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z' }),
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1' })
    ]),
  },
  {
    path: '/media',
    label: '媒体库',
    adminOnly: false,
    requiredPermission: 'can_play_media' as const,
    icon: () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z' })
    ]),
  },
  {
    path: '/poster-wall',
    label: '海报墙',
    adminOnly: false,
    requiredPermission: 'can_play_media' as const,
    icon: () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z' })
    ]),
  },
  {
    path: '/favorites',
    label: '我的收藏',
    adminOnly: false,
    requiredPermission: 'can_favorite' as const,
    icon: () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z' })
    ]),
  },
  {
    path: '/history',
    label: '观看历史',
    adminOnly: false,
    requiredPermission: 'can_view_history' as const,
    icon: () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' })
    ]),
  },
  {
    path: '/downloads',
    label: '下载管理',
    adminOnly: false,
    requiredPermission: 'can_manage_downloads' as const,
    icon: () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4' })
    ]),
  },
  {
    path: '/subscriptions',
    label: '订阅管理',
    adminOnly: false,
    requiredPermission: 'can_manage_subscriptions' as const,
    icon: () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9' })
    ]),
  },
  {
    path: '/sites',
    label: '站点管理',
    adminOnly: false,
    requiredPermission: 'can_manage_sites' as const,
    icon: () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9' })
    ]),
  },
  {
    path: '/ai-assistant',
    label: 'AI 助手',
    adminOnly: true,
    requiredPermission: 'can_use_ai_assistant' as const,
    icon: () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z' })
    ]),
  },
  {
    path: '/profiles-management',
    label: '权限配置文件',
    adminOnly: true,
    icon: () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z' })
    ]),
  },
  {
    path: '/storage',
    label: '外部存储',
    adminOnly: true,
    icon: () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4' })
    ]),
  },
  {
    path: '/files',
    label: '文件管理',
    adminOnly: true,
    requiredPermission: 'can_manage_files' as const,
    icon: () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z' })
    ]),
  },
  {
    path: '/strm',
    label: 'STRM 管理',
    adminOnly: true,
    requiredPermission: 'can_manage_strm' as const,
    icon: () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1' })
    ]),
  },
  {
    path: '/dlna',
    label: 'DLNA 投屏',
    adminOnly: false,
    requiredPermission: 'can_cast' as const,
    icon: () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z' })
    ]),
  },
  {
    path: '/profile',
    label: '个人中心',
    adminOnly: false,
    icon: () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' })
    ]),
  },
  {
    path: '/settings',
    label: '设置',
    adminOnly: false,
    requiredPermission: 'can_access_settings' as const,
    icon: () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-1.756.426-1.756 2.924 0 3.35a1.724 1.724 0 001.066 2.573c-1.543-.94-3.31.826-2.37 2.37-.996.608-2.296.07-2.572-1.065a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996-.608 2.296-.07 2.572 1.065a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37M15 12a3 3 0 11-6 0 3 3 0 016 0z' })
    ]),
  },
]

const isAdmin = computed(() => auth.user?.role === 'admin')
const navItems = computed(() => allNavItems.filter(item => {
  if (item.adminOnly && !isAdmin.value) return false
  if (item.requiredPermission && !auth.hasPermission(item.requiredPermission)) return false
  return true
}))
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.page-enter-active, .page-leave-active { transition: opacity 0.15s ease, transform 0.15s ease; }
.page-enter-from { opacity: 0; transform: translateY(6px); }
.page-leave-to { opacity: 0; transform: translateY(-6px); }

.dropdown-enter-active { transition: opacity 0.15s ease, transform 0.15s ease; }
.dropdown-enter-from { opacity: 0; transform: translateY(-4px); }
</style>
