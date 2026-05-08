<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6 animate-in">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-[var(--text-primary)]">订阅管理</h1>
      <button @click="openCreateModal" class="btn-primary flex items-center gap-2 text-sm">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
        新建订阅
      </button>
    </div>

    <!-- 标签页切换 -->
    <div class="flex items-center gap-1 p-1 rounded-lg bg-[var(--bg-secondary)] w-fit">
      <button v-for="tab in tabs" :key="tab.value"
        @click="activeTab = tab.value"
        :class="[
          'px-4 py-1.5 rounded-md text-sm font-medium transition-all duration-200',
          activeTab === tab.value
            ? 'bg-brand-600 text-white shadow-sm'
            : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
        ]">
        {{ tab.label }}
        <span v-if="tab.count !== undefined" :class="['ml-1.5 text-xs', activeTab === tab.value ? 'text-brand-200' : '']">({{ tab.count }})</span>
      </button>
    </div>

    <!-- ========== 我的订阅 Tab ========== -->
    <template v-if="activeTab === 'mine'">
      <!-- 订阅统计 -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 stagger-in" :style="{ '--stagger': 60 }">
        <div class="card p-4">
          <div class="text-sm text-[var(--text-muted)]">总订阅</div>
          <div class="text-2xl font-bold mt-1 text-[var(--text-primary)]">{{ subscriptions.length }}</div>
        </div>
        <div class="card p-4">
          <div class="text-sm text-[var(--text-muted)]">进行中</div>
          <div class="text-2xl font-bold mt-1" style="color: var(--accent-hover)">{{ activeCount }}</div>
        </div>
        <div class="card p-4">
          <div class="text-sm text-[var(--text-muted)]">已完成</div>
          <div class="text-2xl font-bold mt-1" style="color: var(--success)">{{ completedCount }}</div>
        </div>
        <div class="card p-4">
          <div class="text-sm text-[var(--text-muted)]">异常</div>
          <div class="text-2xl font-bold mt-1" style="color: var(--error)">{{ errorCount }}</div>
        </div>
      </div>

      <!-- 状态筛选 -->
      <div class="flex items-center gap-3 flex-wrap">
        <button v-for="f in statusFilters" :key="f.value"
          @click="statusFilter = f.value"
          :class="[
            'px-3 py-1.5 rounded-lg text-sm transition-colors',
            statusFilter === f.value ? 'text-[var(--accent-hover)]' : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]',
          ]"
          :style="statusFilter === f.value ? { background: 'var(--accent-subtle)' } : {}">
          {{ f.label }}
        </button>
      </div>

      <!-- 订阅列表 -->
      <div class="space-y-2 stagger-in" :style="{ '--stagger': 30 }">
        <div v-for="sub in filteredSubscriptions" :key="sub.id" class="card p-4 transition-colors">
          <div class="flex items-start gap-4">
            <!-- 状态 -->
            <div class="mt-1">
              <div :class="[
                'w-2.5 h-2.5 rounded-full',
                sub.status === 'active' ? 'bg-[var(--success)]' : sub.status === 'completed' ? 'bg-[var(--text-faint)]' : 'bg-[var(--error)]',
              ]" />
            </div>

            <!-- 信息 -->
            <div class="flex-1 min-w-0 space-y-2">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="font-medium text-[var(--text-primary)]">{{ sub.name }}</span>
                <span class="text-xs px-2 py-0.5 rounded text-[var(--text-muted)]" style="background: var(--bg-input)">{{ sub.media_type || '未知' }}</span>
                <span v-if="sub.current_episode" class="text-xs text-[var(--text-muted)]">
                  已下载到 {{ sub.current_episode }}集
                </span>
              </div>

              <p v-if="sub.tmdb_id" class="text-xs text-[var(--text-muted)]">
                TMDb ID: {{ sub.tmdb_id }}
                <span v-if="sub.year"> · {{ sub.year }}</span>
              </p>

              <div class="flex flex-wrap gap-2 text-xs">
                <span v-if="sub.quality_filter" class="px-2 py-0.5 rounded" style="background: var(--accent-subtle); color: var(--accent-hover)">
                  质量: {{ sub.quality_filter }}
                </span>
                <span v-if="sub.min_size" class="px-2 py-0.5 rounded text-[var(--text-muted)]" style="background: var(--bg-input)">
                  最小: {{ (sub.min_size / 1024).toFixed(1) }} GB
                </span>
                <span v-if="sub.max_size" class="px-2 py-0.5 rounded text-[var(--text-muted)]" style="background: var(--bg-input)">
                  最大: {{ (sub.max_size / 1024).toFixed(1) }} GB
                </span>
                <span v-if="sub.include_keywords?.length" class="px-2 py-0.5 rounded text-[var(--text-muted)]" style="background: var(--bg-input)">
                  包含: {{ sub.include_keywords.join(', ') }}
                </span>
                <span v-if="sub.exclude_keywords?.length" class="px-2 py-0.5 rounded text-[var(--text-muted)]" style="background: var(--bg-input)">
                  排除: {{ sub.exclude_keywords.join(', ') }}
                </span>
              </div>

              <!-- 最近日志 -->
              <div v-if="sub.last_log" class="text-xs text-[var(--text-muted)]">
                <span :style="{ color: sub.last_log.success ? 'var(--success)' : 'var(--error)' }">
                  {{ sub.last_log.success ? '成功' : '失败' }}
                </span>
                · {{ formatDate(sub.last_log.created_at) }}
                <span v-if="sub.last_log.message"> - {{ sub.last_log.message }}</span>
              </div>
            </div>

            <!-- 操作 -->
            <div class="flex items-center gap-1 shrink-0">
              <button @click="triggerSearch(sub.id)" title="立即搜索"
                class="p-1.5 rounded-lg transition-colors text-[var(--text-muted)] hover:text-[var(--accent-hover)]" style="background: transparent" onmouseenter="this.style.background='var(--bg-hover)'" onmouseleave="this.style.background='transparent'">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
              </button>
              <button @click="openEditModal(sub)" title="编辑"
                class="p-1.5 rounded-lg transition-colors text-[var(--text-muted)] hover:text-[var(--text-secondary)]" style="background: transparent" onmouseenter="this.style.background='var(--bg-hover)'" onmouseleave="this.style.background='transparent'">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>
              </button>
              <button @click="handleDelete(sub)" title="删除"
                class="p-1.5 rounded-lg transition-colors text-[var(--text-muted)] hover:text-[var(--error)]" style="background: transparent" onmouseenter="this.style.background='var(--bg-hover)'" onmouseleave="this.style.background='transparent'">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
              </button>
            </div>
          </div>
        </div>

        <div v-if="filteredSubscriptions.length === 0 && !loading">
          <AppEmpty message="暂无订阅，点击右上角创建你的第一个订阅" />
        </div>
      </div>
    </template>

    <!-- ========== 热门订阅 Tab ========== -->
    <template v-else-if="activeTab === 'trending'">
      <div v-if="!trendingLoaded" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div v-for="i in 6" :key="i" class="card p-5 animate-pulse space-y-3">
          <div class="flex items-center gap-3">
            <div class="w-12 h-12 rounded-lg bg-[var(--bg-input)]" />
            <div class="flex-1 space-y-2">
              <div class="h-4 bg-[var(--bg-input)] rounded w-2/3" />
              <div class="h-3 bg-[var(--bg-input)] rounded w-1/2" />
            </div>
          </div>
          <div class="h-3 bg-[var(--bg-input)] rounded w-full" />
          <div class="h-8 bg-[var(--bg-input)] rounded w-20" />
        </div>
      </div>

      <div v-else-if="trendingItems.length > 0" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div v-for="(item, index) in trendingItems" :key="item.tmdb_id || item.name"
          class="card p-5 space-y-3 hover:border-[var(--brand-500)]/30 transition-colors stagger-in"
          :style="{ '--stagger': index * 50 }">
          <div class="flex items-start gap-3">
            <!-- 排名 / 海报 -->
            <div class="relative shrink-0">
              <div class="w-12 h-16 rounded-lg bg-[var(--bg-input)] overflow-hidden shadow">
                <img v-if="item.poster_url" :src="item.poster_url" :alt="item.name" class="w-full h-full object-cover" loading="lazy" referrerpolicy="no-referrer"
                  @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />
                <div v-else class="w-full h-full flex items-center justify-center text-xl font-bold" :style="{ color: 'var(--text-faint)' }">
                  {{ index + 1 }}
                </div>
              </div>
              <div v-if="index < 3"
                class="absolute -top-1 -left-1 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white"
                :class="index === 0 ? 'bg-yellow-500' : index === 1 ? 'bg-gray-400' : 'bg-amber-700'">
                {{ index + 1 }}
              </div>
            </div>
            <!-- 信息 -->
            <div class="flex-1 min-w-0 space-y-1.5">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="font-semibold text-sm text-[var(--text-primary)] truncate">{{ item.name || item.title }}</span>
                <span class="text-xs px-1.5 py-0.5 rounded" style="background: var(--bg-input); color: var(--text-muted)">
                  {{ item.media_type === 'movie' ? '电影' : item.media_type === 'tv' ? '剧' : '未知' }}
                </span>
              </div>
              <p v-if="item.overview" class="text-xs line-clamp-2" style="color: var(--text-muted)">{{ item.overview }}</p>
              <div class="flex items-center gap-3 text-xs" style="color: var(--text-faint)">
                <span v-if="item.rating" class="text-yellow-400">★ {{ item.rating?.toFixed(1) || item.vote_average?.toFixed(1) }}</span>
                <span v-if="item.year || item.first_air_date">{{ item.year || (item.first_air_date || '').substring(0, 4) }}</span>
                <span v-if="item.popularity">热度 {{ Math.round(item.popularity) }}</span>
              </div>
            </div>
          </div>
          <!-- 订阅操作 -->
          <div class="flex items-center gap-2 pt-1">
            <button
              v-if="!isSubscribed(item)"
              @click="subscribeTrending(item)"
              class="flex-1 btn-primary text-xs py-1.5 flex items-center justify-center gap-1">
              <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
              添加订阅
            </button>
            <div v-else class="flex-1 flex items-center justify-center gap-2 text-xs py-1.5 px-3 rounded-lg bg-emerald-500/10 text-emerald-400">
              <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
              已订阅
            </div>
            <button
              @click="$router.push(`/media/${item.media_item_id || ''}`)"
              class="btn-secondary text-xs py-1.5 px-3"
              :disabled="!item.media_item_id">
              详情
            </button>
          </div>
        </div>
      </div>

      <div v-else-if="trendingLoaded && trendingItems.length === 0">
        <AppEmpty message="暂无热门推荐内容" />
      </div>
    </template>

    <!-- ========== 资源搜索 Tab ========== -->
    <template v-else-if="activeTab === 'search'">
      <!-- 搜索框 -->
      <div class="flex gap-3">
        <div class="flex-1 max-w-md">
          <div class="relative">
            <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none" style="color: var(--text-faint)" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
            <input v-model="searchKeyword" @keyup.enter="doSiteSearch"
              class="input w-full !pl-9 pr-4"
              placeholder="输入关键词搜索站点资源..." />
          </div>
        </div>
        <button @click="doSiteSearch" :disabled="searchLoading || !searchKeyword.trim()"
          class="btn-primary">
          {{ searchLoading ? '搜索中...' : '搜索' }}
        </button>
      </div>

      <!-- 搜索结果 -->
      <div v-if="searchLoading" class="space-y-2">
        <div v-for="i in 5" :key="i" class="card p-4 animate-pulse">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded bg-[var(--bg-input)]" />
            <div class="flex-1 space-y-2">
              <div class="h-4 bg-[var(--bg-input)] rounded w-3/4" />
              <div class="h-3 bg-[var(--bg-input)] rounded w-1/2" />
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="searchResults.length > 0" class="space-y-2">
        <div v-for="item in searchResults" :key="item.download_url + item.title"
          class="card p-4 hover:border-[var(--accent)]/30 transition-colors">
          <div class="flex items-start gap-3">
            <!-- 免费标记 -->
            <div class="mt-1 shrink-0">
              <div v-if="item.free" class="px-2 py-0.5 rounded text-[10px] font-bold bg-red-500/20 text-red-400">
                FREE
              </div>
              <div v-else class="w-6 h-6 rounded flex items-center justify-center" style="background: var(--bg-input)">
                <svg class="w-4 h-4" style="color: var(--text-faint)" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/></svg>
              </div>
            </div>
            <!-- 信息 -->
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="font-medium text-sm text-[var(--text-primary)] truncate">{{ item.title }}</span>
                <span v-if="item.size" class="text-xs px-1.5 py-0.5 rounded" style="background: var(--bg-input); color: var(--text-muted)">
                  {{ formatSize(item.size) }}
                </span>
                <span v-if="item.seeders !== undefined" class="text-xs text-green-500">
                  ↑ {{ item.seeders }}
                </span>
                <span v-if="item.leechers !== undefined" class="text-xs text-red-400">
                  ↓ {{ item.leechers }}
                </span>
              </div>
              <div class="flex items-center gap-3 mt-1 text-xs" style="color: var(--text-muted)">
                <span>{{ item.site_name }}</span>
                <span v-if="item.upload_time">{{ item.upload_time }}</span>
                <span v-if="item.category" class="px-1.5 py-0.5 rounded" style="background: var(--bg-secondary)">{{ item.category }}</span>
              </div>
            </div>
            <!-- 操作 -->
            <button @click="downloadResource(item)"
              class="btn-primary text-xs py-1.5 shrink-0">
              下载
            </button>
          </div>
        </div>
      </div>

      <div v-else-if="searchKeyword && !searchLoading" class="py-12 text-center" style="color: var(--text-muted)">
        <svg class="w-16 h-16 mx-auto mb-4 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
        <p class="text-lg font-medium">未找到匹配的站点资源</p>
        <p class="text-sm mt-1">尝试其他关键词，或检查站点配置</p>
      </div>

      <div v-else class="py-12 text-center" style="color: var(--text-muted)">
        <svg class="w-16 h-16 mx-auto mb-4 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
        <p class="text-lg font-medium">输入关键词搜索站点资源</p>
        <p class="text-sm mt-1">搜索 PT 站点上的种子资源</p>
      </div>
    </template>

    <!-- 创建/编辑弹窗 -->
    <AppModal :show="showModal" :title="editingSub ? '编辑订阅' : '新建订阅'" max-width="max-w-lg" @close="closeModal">
      <div class="space-y-4">
        <div>
          <label class="block text-sm text-[var(--text-muted)] mb-1">订阅名称 *</label>
          <input v-model="form.name" placeholder="例如: 某某剧 S01" class="input" />
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-sm text-[var(--text-muted)] mb-1">媒体类型</label>
            <select v-model="form.media_type" class="input">
              <option value="tv">电视剧</option>
              <option value="movie">电影</option>
            </select>
          </div>
          <div>
            <label class="block text-sm text-[var(--text-muted)] mb-1">年份</label>
            <input v-model.number="form.year" placeholder="2024" class="input" type="number" />
          </div>
        </div>

        <div>
          <label class="block text-sm text-[var(--text-muted)] mb-1">TMDb ID（可选，用于精准匹配）</label>
          <input v-model.number="form.tmdb_id" placeholder="例如: 12345" class="input" type="number" />
        </div>

        <div>
          <label class="block text-sm text-[var(--text-muted)] mb-2">画质（可多选）</label>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="q in qualityOptions"
              :key="q.value"
              type="button"
              @click="toggleQuality(q.value)"
              :class="[
                'px-3 py-1 rounded-full text-sm border transition-colors',
                form.quality_filter.includes(q.value)
                  ? 'border-[var(--accent)] text-[var(--accent)] bg-[var(--accent)]/10'
                  : 'border-[var(--border)] text-[var(--text-muted)] hover:border-[var(--text-muted)]'
              ]"
            >
              {{ q.label }}
            </button>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-sm text-[var(--text-muted)] mb-1">最小大小 (GB)</label>
            <input v-model.number="form.min_size" placeholder="0" class="input" type="number" step="0.1" />
          </div>
          <div>
            <label class="block text-sm text-[var(--text-muted)] mb-1">最大大小 (GB)</label>
            <input v-model.number="form.max_size" placeholder="0" class="input" type="number" step="0.1" />
          </div>
        </div>

        <div>
          <label class="block text-sm text-[var(--text-muted)] mb-1">包含关键词（逗号分隔）</label>
          <input v-model="includeKeywordsStr" placeholder="简繁,国粤" class="input" />
        </div>

        <div>
          <label class="block text-sm text-[var(--text-muted)] mb-1">排除关键词（逗号分隔）</label>
          <input v-model="excludeKeywordsStr" placeholder="杜比,全景声" class="input" />
        </div>
      </div>
      <template #footer>
        <div class="flex justify-end gap-2 pt-2">
          <button @click="closeModal" class="btn-secondary text-sm">取消</button>
          <button @click="saveSubscription" :disabled="!form.name.trim()" class="btn-primary text-sm disabled:opacity-50">
            {{ editingSub ? '保存' : '创建' }}
          </button>
        </div>
      </template>
    </AppModal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { subscribeApi } from '@/api/subscribe'
import { mediaApi } from '@/api/media'
import { useFormat } from '@/composables/useFormat'
import { useToast } from '@/composables/useToast'
import AppModal from '@/components/AppModal.vue'
import AppEmpty from '@/components/AppEmpty.vue'

const route = useRoute()
const { formatDate } = useFormat()
const toast = useToast()

// 标签页状态
const activeTab = ref<'mine' | 'trending' | 'search'>('mine')
const tabs = computed(() => [
  { label: '我的订阅', value: 'mine' as const, count: subscriptions.value.length },
  { label: '热门订阅', value: 'trending' as const },
  { label: '资源搜索', value: 'search' as const },
])

// ====== 资源搜索 ======
const searchKeyword = ref('')
const searchResults = ref<any[]>([])
const searchLoading = ref(false)

async function doSiteSearch() {
  const keyword = searchKeyword.value.trim()
  if (!keyword) {
    searchResults.value = []
    return
  }
  searchLoading.value = true
  try {
    const res = await subscribeApi.searchSites(keyword)
    searchResults.value = res.data || []
    if (searchResults.value.length === 0) {
      toast.info('未找到匹配的站点资源')
    }
  } catch (e: any) {
    console.error('Site search error:', e)
    toast.error('搜索失败: ' + (e.response?.data?.detail || e.message))
    searchResults.value = []
  } finally {
    searchLoading.value = false
  }
}

// ====== 我的订阅 ======
const subscriptions = ref<any[]>([])
const statusFilter = ref('all')
const loading = ref(true)

const statusFilters = [
  { label: '全部', value: 'all' },
  { label: '进行中', value: 'active' },
  { label: '已完成', value: 'completed' },
  { label: '异常', value: 'error' },
]

const activeCount = computed(() => subscriptions.value.filter(s => s.status === 'active').length)
const completedCount = computed(() => subscriptions.value.filter(s => s.status === 'completed').length)
// 错误订阅：从最近日志判断（有日志且 success=false 表示失败）
const errorCount = computed(() => subscriptions.value.filter(s => s.last_log && s.last_log.success === false).length)

const filteredSubscriptions = computed(() => {
  if (statusFilter.value === 'all') return subscriptions.value
  if (statusFilter.value === 'error') {
    // 错误：最近日志失败
    return subscriptions.value.filter(s => s.last_log && s.last_log.success === false)
  }
  return subscriptions.value.filter(s => s.status === statusFilter.value)
})

// ====== 热门订阅 ======
const trendingItems = ref<any[]>([])
const trendingLoaded = ref(false)

function isSubscribed(item: any): boolean {
  // 通过 tmdb_id 判断是否已经订阅
  const tmdbId = item.tmdb_id
  if (!tmdbId) return false
  return subscriptions.value.some((s: any) => s.tmdb_id === tmdbId)
}

async function subscribeTrending(item: any) {
  // 预填充弹窗表单
  form.value = {
    name: item.name || item.title || '',
    media_type: item.media_type || 'tv',
    year: item.year || (item.first_air_date || '').substring(0, 4) ? parseInt((item.first_air_date || '').substring(0, 4)) : null,
    tmdb_id: item.tmdb_id || null,
    quality_filter: ['1080p', '720p'],
    min_size: null,
    max_size: null,
  }
  includeKeywordsStr.value = ''
  excludeKeywordsStr.value = ''
  editingSub.value = null
  showModal.value = true
  // 自动切换到我的订阅 tab 以便查看结果
  activeTab.value = 'mine'
}

// 画质选项
const qualityOptions = [
  { label: '4K', value: '4k' },
  { label: '1080p', value: '1080p' },
  { label: '720p', value: '720p' },
  { label: '576p', value: '576p' },
  { label: '480p', value: '480p' },
]

function toggleQuality(value: string) {
  const arr = form.value.quality_filter as string[]
  const idx = arr.indexOf(value)
  if (idx >= 0) {
    arr.splice(idx, 1)
  } else {
    arr.push(value)
  }
}

// ====== 弹窗 ======
const showModal = ref(false)
const editingSub = ref<any>(null)
const form = ref({
  name: '',
  media_type: 'tv',
  year: null as number | null,
  tmdb_id: null as number | null,
  quality_filter: ['1080p', '720p'] as string[],  // 默认选中 1080p 和 720p
  min_size: null as number | null,
  max_size: null as number | null,
})
const includeKeywordsStr = ref('')
const excludeKeywordsStr = ref('')

function openCreateModal() {
  editingSub.value = null
  form.value = { name: '', media_type: 'tv', year: null, tmdb_id: null, quality_filter: ['1080p', '720p'], min_size: null, max_size: null }
  includeKeywordsStr.value = ''
  excludeKeywordsStr.value = ''
  showModal.value = true
}

function openEditModal(sub: any) {
  editingSub.value = sub
  form.value = {
    name: sub.name,
    media_type: sub.media_type || 'tv',
    year: sub.year,
    tmdb_id: sub.tmdb_id,
    quality_filter: Array.isArray(sub.quality_filter) ? [...sub.quality_filter] : [],
    min_size: sub.min_size ? sub.min_size / 1024 : null,
    max_size: sub.max_size ? sub.max_size / 1024 : null,
  }
  includeKeywordsStr.value = (sub.include_keywords || []).join(', ')
  excludeKeywordsStr.value = (sub.exclude_keywords || []).join(', ')
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  editingSub.value = null
}

async function saveSubscription() {
  // 将 GB 转为 MB（后端以 MB 存储）
  const minSizeMb = form.value.min_size ? Math.round(form.value.min_size * 1024) : 0
  const maxSizeMb = form.value.max_size ? Math.round(form.value.max_size * 1024) : 0
  const payload: any = {
    name: form.value.name,
    media_type: form.value.media_type,
    year: form.value.year || null,
    tmdb_id: form.value.tmdb_id || null,
    quality_filter: form.value.quality_filter,
    min_size: minSizeMb,
    max_size: maxSizeMb,
    include_keywords: includeKeywordsStr.value ? includeKeywordsStr.value.split(',').map(s => s.trim()).filter(Boolean) : [],
    exclude_keywords: excludeKeywordsStr.value ? excludeKeywordsStr.value.split(',').map(s => s.trim()).filter(Boolean) : [],
  }
  try {
    if (editingSub.value) {
      await subscribeApi.updateSubscription(editingSub.value.id, payload)
      toast.success('订阅已更新')
    } else {
      await subscribeApi.createSubscription(payload)
      toast.success('订阅已创建')
    }
    closeModal()
    await Promise.all([loadSubscriptions(), loadTrending()])
  } catch (e) {
    toast.error('保存订阅失败')
  }
}

async function loadSubscriptions() {
  try {
    const status = statusFilter.value !== 'all' ? statusFilter.value : undefined
    const { data } = await subscribeApi.getSubscriptions(status)
    subscriptions.value = Array.isArray(data) ? data : data.items || []
  } catch (e) {
    toast.error('加载订阅失败')
  } finally {
    loading.value = false
  }
}

async function loadTrending() {
  try {
    // 尝试获取热门/高评分的媒体作为热门订阅推荐
    const { data } = await mediaApi.getItems({
      page: 1, page_size: 18, sort_by: 'rating', sort_order: 'desc',
    })
    trendingItems.value = data.items || []
  } catch {
    trendingItems.value = []
  } finally {
    trendingLoaded.value = true
  }
}

async function triggerSearch(id: number) {
  try {
    await subscribeApi.triggerSearch(id)
    toast.success('已触发搜索')
    await loadSubscriptions()
  } catch {
    toast.error('触发搜索失败')
  }
}

async function handleDelete(sub: any) {
  const confirmed = await toast.confirm({
    title: '确认删除',
    message: `确定要删除订阅「${sub.name}」吗？此操作不可撤销。`,
    confirmText: '删除',
    danger: true,
  })
  if (!confirmed) return
  try {
    await subscribeApi.deleteSubscription(sub.id)
    toast.success('订阅已删除')
    await Promise.all([loadSubscriptions(), loadTrending()])
  } catch {
    toast.error('删除订阅失败')
  }
}

onMounted(async () => {
  await Promise.all([loadSubscriptions(), loadTrending()])
  // 处理 URL 参数中的 search（从发现页跳转过来）
  const searchParam = route.query.search as string
  if (searchParam) {
    searchKeyword.value = searchParam
    activeTab.value = 'search'
    doSiteSearch()
  }
})

/** 格式化文件大小 */
function formatSize(bytes: number): string {
  if (!bytes || bytes === 0) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let unitIdx = 0
  let size = bytes
  while (size >= 1024 && unitIdx < units.length - 1) {
    size /= 1024
    unitIdx++
  }
  return `${size.toFixed(1)} ${units[unitIdx]}`
}

/** 下载资源 */
async function downloadResource(item: any) {
  try {
    // 调用后端下载接口
    const res = await fetch('/api/downloads', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('access_token') || ''}`,
      },
      body: JSON.stringify({
        url: item.download_url,
        title: item.title,
        site_id: item.site_id,
      }),
    })
    if (res.ok) {
      toast.success(`「${item.title}」已开始下载`)
    } else {
      const err = await res.json()
      toast.error('下载失败: ' + (err.detail || err.message || '未知错误'))
    }
  } catch (e: any) {
    toast.error('下载失败: ' + (e.message || '网络错误'))
  }
}
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
