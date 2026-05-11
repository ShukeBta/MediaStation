<template>
  <div class="p-4 md:p-6 max-w-6xl mx-auto space-y-6">
    <div class="flex items-center gap-3">
      <div class="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center">
        <svg class="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/>
        </svg>
      </div>
      <div>
        <h1 class="text-2xl font-bold">STRM 管理</h1>
        <p class="text-sm mt-0.5" style="color: var(--text-muted)">管理 STRM 文件引用，将外部存储以"文件"形式加入媒体库</p>
      </div>
    </div>

    <!-- STRM 配置卡片 -->
    <div class="card p-6 space-y-5">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">STRM 配置</h2>
        <div class="flex items-center gap-2">
          <span class="text-sm" style="color: var(--text-muted)">启用状态</span>
          <button @click="toggleEnabled"
            :class="['relative w-11 h-6 rounded-full transition-colors duration-200', config.enabled ? 'bg-brand-500' : 'bg-gray-500/30']">
            <span :class="['absolute top-0.5 w-5 h-5 rounded-full bg-white transition-transform duration-200 shadow', config.enabled ? 'left-5.5' : 'left-0.5']" />
          </button>
        </div>
      </div>

      <div v-if="configLoading" class="animate-pulse space-y-4">
        <div class="h-4 bg-[var(--bg-input)] rounded w-48" />
        <div class="h-10 bg-[var(--bg-input)] rounded" />
        <div class="h-10 bg-[var(--bg-input)] rounded" />
      </div>

      <template v-else>
        <!-- 允许协议 -->
        <div>
          <label class="block text-sm font-medium mb-2" style="color: var(--text-secondary)">允许的协议</label>
          <div class="flex flex-wrap gap-2">
            <button v-for="proto in ['http', 'https', 'webdav', 's3', 'alist']" :key="proto"
              @click="toggleProtocol(proto)"
              :class="['px-3 py-1.5 text-sm rounded-lg border transition-colors',
                config.allowed_protocols?.includes(proto)
                  ? 'bg-brand-500/10 border-brand-500/30 text-brand-400'
                  : 'bg-[var(--bg-input)] border-[var(--border-primary)] hover:border-[var(--border-secondary)]']">
              {{ proto.toUpperCase() }}
            </button>
          </div>
        </div>

        <!-- 最大文件大小 -->
        <div>
          <label class="block text-sm font-medium mb-2" style="color: var(--text-secondary)">
            最大文件大小
            <span class="text-xs ml-2" style="color: var(--text-faint)">(当前: {{ formatSize(config.max_file_size) }})</span>
          </label>
          <div class="flex items-center gap-3">
            <input v-model.number="config.max_file_size" type="number" min="1024" step="1024"
              class="flex-1 px-3 py-2 text-sm rounded-lg border bg-[var(--bg-input)] border-[var(--border-primary)] focus:border-brand-500 focus:outline-none"
              style="color: var(--text-primary)" />
            <select v-model="sizeUnit"
              class="px-3 py-2 text-sm rounded-lg border bg-[var(--bg-input)] border-[var(--border-primary)]"
              style="color: var(--text-primary)">
              <option value="1024">KB</option>
              <option value="1048576">MB</option>
              <option value="1073741824">GB</option>
            </select>
            <button @click="saveConfig" :disabled="saving"
              class="btn-primary text-sm px-4 py-2 disabled:opacity-50">
              <span v-if="saving" class="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-1.5" />
              保存配置
            </button>
          </div>
        </div>
      </template>
    </div>

    <!-- 媒体 STRM 设置 -->
    <div class="card p-6 space-y-4">
      <h2 class="text-lg font-semibold">媒体 STRM 设置</h2>

      <!-- 搜索媒体 -->
      <div class="flex gap-3">
        <div class="flex-1 relative">
          <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none" style="color: var(--text-muted)" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
          <input v-model="searchQuery" @input="onSearchInput" @keydown.enter="searchMedia"
            type="text" placeholder="搜索媒体以设置 STRM URL..."
            class="w-full pl-9 pr-3 py-2 text-sm rounded-lg border bg-[var(--bg-input)] border-[var(--border-primary)] focus:border-brand-500 focus:outline-none"
            style="color: var(--text-primary)" />
        </div>
        <button @click="searchMedia" :disabled="!searchQuery.trim()"
          class="btn-primary text-sm px-4 py-2 disabled:opacity-50">
          搜索
        </button>
      </div>

      <!-- 搜索结果 -->
      <div v-if="searchResults.length > 0" class="space-y-3">
        <div v-for="item in searchResults" :key="item.id"
          class="p-4 rounded-lg border bg-[var(--bg-secondary)] border-[var(--border-primary)] space-y-3">
          <div class="flex items-start gap-4">
            <div class="w-12 h-18 rounded overflow-hidden bg-[var(--bg-input)] shrink-0">
              <img v-if="item.poster_url" :src="item.poster_url" :alt="item.title" class="w-full h-full object-cover" referrerpolicy="no-referrer" @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />
            </div>
            <div class="flex-1 min-w-0">
              <div class="font-medium truncate">{{ item.title }}</div>
              <div class="text-xs mt-0.5" style="color: var(--text-muted)">
                {{ item.media_type === 'movie' ? '电影' : item.media_type === 'tv' ? '剧集' : '动漫' }} · {{ item.year || '—' }}
              </div>
              <div v-if="item.strm_url" class="mt-2 text-xs px-2 py-1 rounded bg-green-500/10 text-green-400 break-all">
                STRM: {{ item.strm_url }}
              </div>
            </div>
          </div>
          <!-- 设置 STRM URL -->
          <div class="flex gap-2">
            <input v-model="item.new_strm_url" type="url" :placeholder="item.strm_url || '输入 STRM URL (http://...)'"
              class="flex-1 px-3 py-2 text-sm rounded-lg border bg-[var(--bg-input)] border-[var(--border-primary)] focus:border-brand-500 focus:outline-none"
              style="color: var(--text-primary)" />
            <button v-if="!item.strm_url" @click="setStrmUrl(item)"
              :disabled="!item.new_strm_url?.trim()"
              class="btn-primary text-sm px-3 py-2 disabled:opacity-50 whitespace-nowrap">
              设置
            </button>
            <button v-else @click="clearStrmUrl(item)"
              class="btn-danger text-sm px-3 py-2 whitespace-nowrap">
              清除
            </button>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else-if="searched && searchResults.length === 0"
        class="text-center py-8" style="color: var(--text-muted)">
        <svg class="w-12 h-12 mx-auto mb-2 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
        </svg>
        <div class="text-sm">未找到匹配的媒体</div>
      </div>
    </div>

    <!-- 已设置 STRM 的媒体列表 -->
    <div class="card p-6 space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">已设置 STRM 的媒体</h2>
        <button @click="loadStrmMedia" :disabled="loadingList"
          class="text-sm hover:text-brand-400 transition-colors" style="color: var(--text-muted)">
          <span v-if="loadingList" class="inline-block w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin mr-1" />
          刷新
        </button>
      </div>

      <div v-if="loadingList" class="space-y-3">
        <div v-for="i in 3" :key="i" class="animate-pulse flex items-center gap-4 p-3">
          <div class="w-10 h-14 rounded bg-[var(--bg-input)]" />
          <div class="flex-1 space-y-2">
            <div class="h-4 bg-[var(--bg-input)] rounded w-48" />
            <div class="h-3 bg-[var(--bg-input)] rounded w-64" />
          </div>
        </div>
      </div>

      <div v-else-if="strmMediaList.length > 0" class="space-y-2">
        <div v-for="item in strmMediaList" :key="item.media_id"
          class="flex items-center gap-4 p-3 rounded-lg hover:bg-[var(--bg-hover)] transition-colors group">
          <div class="w-10 h-14 rounded overflow-hidden bg-[var(--bg-input)] shrink-0">
            <img v-if="item.poster_url" :src="item.poster_url" :alt="item.title" class="w-full h-full object-cover" referrerpolicy="no-referrer" @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />
          </div>
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium truncate">{{ item.title }}</div>
            <div class="text-xs truncate mt-0.5" style="color: var(--text-muted)">{{ item.strm_url }}</div>
          </div>
          <button @click="confirmClear(item)" title="清除 STRM URL"
            class="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-red-500/10 text-red-400 transition-all">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
            </svg>
          </button>
        </div>
      </div>

      <div v-else class="text-center py-8" style="color: var(--text-muted)">
        <div class="text-sm">暂无设置 STRM URL 的媒体</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { strmApi } from '@/api/strm'
import { mediaApi } from '@/api/media'
import { useToast } from '@/composables/useToast'

const toast = useToast()

// ── 配置状态 ──
const config = ref<{ enabled: boolean; allowed_protocols: string[]; max_file_size: number }>({
  enabled: false,
  allowed_protocols: ['http', 'https'],
  max_file_size: 1048576,
})
const configLoading = ref(true)
const saving = ref(false)
const sizeUnit = ref('1048576')

// ── 搜索状态 ──
const searchQuery = ref('')
const searchResults = ref<any[]>([])
const searched = ref(false)

// ── 列表状态 ──
const strmMediaList = ref<any[]>([])
const loadingList = ref(false)

// 格式化大小
function formatSize(bytes: number): string {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let idx = 0
  while (size >= 1024 && idx < units.length - 1) {
    size /= 1024
    idx++
  }
  return `${size.toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`
}

// 切换启用状态
async function toggleEnabled() {
  config.value.enabled = !config.value.enabled
  await saveConfig()
}

// 切换协议
function toggleProtocol(proto: string) {
  const protocols = config.value.allowed_protocols || []
  const idx = protocols.indexOf(proto)
  if (idx >= 0) {
    protocols.splice(idx, 1)
  } else {
    protocols.push(proto)
  }
}

// 保存配置
async function saveConfig() {
  saving.value = true
  try {
    const { data } = await strmApi.updateConfig({
      enabled: config.value.enabled,
      allowed_protocols: config.value.allowed_protocols,
      max_file_size: config.value.max_file_size,
    })
    toast.success(data.message || '配置已保存')
  } catch (e: any) {
    toast.error(`保存失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    saving.value = false
  }
}

// 搜索媒体
let searchTimer: ReturnType<typeof setTimeout> | null = null
function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    if (searchQuery.value.trim().length >= 2) {
      searchMedia()
    }
  }, 300)
}

async function searchMedia() {
  if (!searchQuery.value.trim()) return
  searched.value = true
  try {
    const { data } = await mediaApi.getItems({ q: searchQuery.value.trim(), page_size: 10 })
    searchResults.value = (data.items || []).map((item: any) => ({
      ...item,
      new_strm_url: '',
    }))
  } catch (e) {
    searchResults.value = []
  }
}

// 设置 STRM URL
async function setStrmUrl(item: any) {
  if (!item.new_strm_url?.trim()) return
  try {
    const { data } = await strmApi.setMediaStrm(item.id, item.new_strm_url.trim())
    item.strm_url = data.strm_url
    item.new_strm_url = ''
    toast.success(`已设置「${item.title}」的 STRM URL`)
    loadStrmMedia()
  } catch (e: any) {
    toast.error(`设置失败: ${e.response?.data?.detail || e.message}`)
  }
}

// 清除 STRM URL
async function clearStrmUrl(item: any) {
  try {
    const { data } = await strmApi.clearMediaStrm(item.id)
    item.strm_url = null
    toast.success(data.message || '已清除 STRM URL')
    loadStrmMedia()
  } catch (e: any) {
    toast.error(`清除失败: ${e.response?.data?.detail || e.message}`)
  }
}

// 确认清除（列表中的）
async function confirmClear(item: any) {
  if (!confirm(`确定要清除「${item.title}」的 STRM URL 吗？`)) return
  try {
    await strmApi.clearMediaStrm(item.media_id)
    toast.success('已清除 STRM URL')
    loadStrmMedia()
  } catch (e: any) {
    toast.error(`清除失败: ${e.response?.data?.detail || e.message}`)
  }
}

// 加载已设置 STRM 的媒体
async function loadStrmMedia() {
  loadingList.value = true
  try {
    const { data } = await mediaApi.getItems({ page_size: 100 })
    strmMediaList.value = (data.items || []).filter((item: any) => item.strm_url)
  } catch (e) {
    strmMediaList.value = []
  } finally {
    loadingList.value = false
  }
}

// 加载配置
onMounted(async () => {
  try {
    const { data: configData } = await strmApi.getConfig()
    config.value = configData
  } catch (e: any) {
    toast.error(`加载配置失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    configLoading.value = false
  }
  loadStrmMedia()
})
</script>
