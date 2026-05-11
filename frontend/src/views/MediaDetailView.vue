<template>
  <div class="min-h-screen">
    <!-- 背景图 -->
    <div v-if="item?.backdrop_url" class="fixed inset-0 -z-10">
      <img :src="item.backdrop_url" class="w-full h-full object-cover opacity-20 blur-sm"
        referrerpolicy="no-referrer"
        @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />
      <div class="absolute inset-0 bg-gradient-to-t from-[var(--bg-primary)] via-[var(--bg-primary)]/80 to-transparent" />
    </div>

    <div v-if="loading" class="flex items-center justify-center min-h-screen">
      <div class="animate-spin text-4xl text-brand-500">▶</div>
    </div>

    <div v-else-if="item" class="p-4 md:p-6 max-w-5xl mx-auto pt-16 md:pt-24">
      <button @click="$router.back()" class="inline-flex items-center gap-1 text-sm mb-4 transition-colors hover:text-[var(--text-primary)]" style="color: var(--text-muted)">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
        返回
      </button>

      <div class="flex flex-col md:flex-row gap-4 md:gap-6">
        <!-- 海报 -->
        <div class="shrink-0 self-center md:self-start">
          <div class="w-44 md:w-56 rounded-xl overflow-hidden shadow-2xl">
            <img v-if="item.poster_url" :src="item.poster_url" :alt="item.title"
              class="w-full object-cover" referrerpolicy="no-referrer"
              @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />
            <div v-else class="w-full aspect-[2/3] bg-[var(--bg-input)] flex items-center justify-center" style="color: var(--text-faint)">无海报</div>
          </div>
        </div>

        <!-- 信息 -->
        <div class="flex-1 space-y-4">
          <div>
            <h1 class="text-2xl md:text-3xl font-bold">{{ item.title }}</h1>
            <div class="mt-1" style="color: var(--text-muted)">{{ item.original_title }}</div>
          </div>

          <div class="flex flex-wrap items-center gap-3 text-sm">
            <span v-if="item.year" class="bg-[var(--bg-input)] px-2 py-0.5 rounded border border-[var(--border-primary)]">{{ item.year }}</span>
            <span v-if="item.rating" class="text-yellow-400">★ {{ item.rating.toFixed(1) }}</span>
            <span v-if="item.douban_rating" class="text-green-400">豆瓣 ★ {{ item.douban_rating.toFixed(1) }}</span>
            <span v-if="item.bangumi_rating" class="text-sky-400">Bangumi ★ {{ item.bangumi_rating.toFixed(1) }}</span>
            <span v-if="item.duration" style="color: var(--text-muted)">{{ formatDuration(item.duration) }}</span>
            <span v-if="item.resolution" class="bg-brand-600/20 text-brand-400 px-2 py-0.5 rounded">{{ item.resolution }}</span>
            <span v-if="item.video_codec" class="text-xs" style="color: var(--text-faint)">{{ item.video_codec.toUpperCase() }}</span>
          </div>

          <p v-if="item.genres?.length" class="flex flex-wrap gap-2">
            <span v-for="g in item.genres" :key="g" class="text-xs bg-[var(--bg-hover)] px-2 py-1 rounded border border-[var(--border-primary)]" style="color: var(--text-secondary)">{{ g }}</span>
          </p>

          <p v-if="item.overview" class="text-sm leading-relaxed" style="color: var(--text-muted)">{{ item.overview }}</p>

          <!-- 操作按钮 -->
          <div class="flex flex-wrap gap-3 pt-2">
            <button @click="play(item.id)" class="btn-primary flex items-center gap-2">
              <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
              播放
            </button>
            <!-- DLNA 投屏 -->
            <div class="relative" ref="dlnaMenuRef">
              <button @click="toggleDlnaMenu" class="btn-secondary flex items-center gap-2">
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>
                DLNA 投屏
              </button>
              <Transition name="scale">
                <div v-if="dlnaMenuVisible" class="absolute top-full right-0 mt-2 w-72 bg-[var(--bg-card-solid)] border border-[var(--border-primary)] rounded-xl shadow-xl z-50 overflow-hidden">
                  <div class="p-3 border-b border-[var(--border-primary)]">
                    <div class="flex items-center justify-between">
                      <span class="text-sm font-medium">DLNA 设备</span>
                      <button @click="discoverDlna" :disabled="dlnaLoading"
                        class="text-xs px-2 py-1 rounded bg-brand-500/10 text-brand-400 hover:bg-brand-500/20 disabled:opacity-50">
                        {{ dlnaLoading ? '搜索中...' : '刷新' }}
                      </button>
                    </div>
                  </div>
                  <div v-if="dlnaDevices.length === 0 && !dlnaLoading" class="p-4 text-center text-sm" style="color: var(--text-muted)">
                    未发现设备
                  </div>
                  <div v-else class="max-h-64 overflow-y-auto p-2 space-y-1">
                    <button v-for="dev in dlnaDevices" :key="dev.uuid"
                      @click="castToDlna(dev)"
                      class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors hover:bg-[var(--bg-hover)]"
                      style="color: var(--text-secondary)">
                      <span class="w-8 h-8 rounded-lg bg-purple-500/10 text-purple-400 flex items-center justify-center shrink-0 text-xs font-bold">TV</span>
                      <div class="flex-1 min-w-0 text-left">
                        <div class="truncate font-medium">{{ dev.name }}</div>
                        <div class="text-xs truncate" style="color: var(--text-faint)">{{ dev.manufacturer }} {{ dev.model_name }} · {{ dev.ip }}</div>
                      </div>
                      <svg class="w-4 h-4 shrink-0 opacity-40" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                    </button>
                  </div>
                </div>
              </Transition>
            </div>

            <!-- 外部播放器下拉 -->
            <div class="relative" ref="externalMenuRef">
              <button @click="toggleExternalMenu" class="btn-secondary flex items-center gap-2">
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
                外部播放器
              </button>
              <Transition name="scale">
                <div v-if="externalMenuVisible" class="absolute top-full left-0 mt-2 w-56 bg-[var(--bg-card-solid)] border border-[var(--border-primary)] rounded-xl shadow-xl z-50 overflow-hidden">
                  <div class="p-2 text-xs border-b border-[var(--border-primary)]" style="color: var(--text-muted)">选择外部播放器</div>
                  <button v-for="player in externalPlayers" :key="player.name"
                    @click="openExternalPlayer(player)"
                    class="w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors hover:bg-[var(--bg-hover)]"
                    style="color: var(--text-secondary)">
                    <span class="text-base">{{ player.icon }}</span>
                    <span>{{ player.name }}</span>
                  </button>
                  <div class="border-t border-[var(--border-primary)]">
                    <button @click="copyExternalUrl" class="w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors hover:bg-[var(--bg-hover)]" style="color: var(--text-secondary)">
                      <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"/></svg>
                      <span>{{ copySuccess ? '已复制!' : '复制直链地址' }}</span>
                    </button>
                  </div>
                </div>
              </Transition>
            </div>
            <!-- 编辑元数据按钮（管理员可见） -->
            <button v-if="isAdmin" @click="openEditModal"
              class="btn-secondary flex items-center gap-2 border-amber-500/30 text-amber-400 hover:bg-amber-500/10">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>
              编辑
            </button>
            <!-- 获取元数据（未刮削时显示） -->
            <button v-if="!item.scraped && isAdmin" @click="scrape" :disabled="scraping"
              class="btn-secondary flex items-center gap-2 disabled:opacity-50">
              {{ scraping ? '刮削中...' : '获取元数据' }}
            </button>
            <!-- 重新刮削（已刮削时显示） -->
            <button v-if="item.scraped && isAdmin" @click="rescrapeConfirm" :disabled="scraping"
              class="btn-secondary flex items-center gap-2 disabled:opacity-50 border-orange-500/30 text-orange-400 hover:bg-orange-500/10">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
              重新刮削
            </button>
            <button v-if="item.scraped && isAdmin" @click="aiScrape" :disabled="aiScraping"
              class="btn-secondary flex items-center gap-2 disabled:opacity-50 border-purple-500/30 text-purple-400 hover:bg-purple-500/10">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-9.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386a5 5 0 010-7.072z"/></svg>
              {{ aiScraping ? 'AI 处理中...' : 'AI 优化' }}
            </button>
            <!-- 收藏按钮 -->
            <button @click="toggleFavorite"
              :class="['btn-secondary flex items-center gap-2 disabled:opacity-50', isFavorited ? 'border-yellow-500/30 text-yellow-400 hover:bg-yellow-500/10' : '']"
              :disabled="favLoading">
              <svg v-if="isFavorited" class="w-5 h-5 fill-current text-yellow-400" viewBox="0 0 24 24"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/></svg>
              <svg v-else class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/></svg>
              {{ isFavorited ? '已收藏' : '收藏' }}
            </button>
            <!-- 订阅下载按钮 -->
            <button @click="handleSubscribe"
              :disabled="subscribing"
              class="btn-secondary flex items-center gap-2 disabled:opacity-50 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
              {{ subscribing ? '订阅中...' : '订阅下载' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 剧集列表 -->
      <div v-if="item.media_type !== 'movie' && item.seasons?.length" class="mt-10">
        <h2 class="text-xl font-semibold mb-4">剧集列表</h2>
        <div v-for="season in item.seasons" :key="season.id" class="mb-6">
          <h3 class="text-lg font-medium mb-2">{{ season.name || `第 ${season.season_number} 季` }}</h3>
          <div class="grid gap-2">
            <div v-for="ep in season.episodes" :key="ep.id"
              @click="play(item.id, ep.id)"
              class="flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors hover:bg-[var(--bg-hover)]"
              style="background: var(--bg-card)">
              <span class="w-8 text-center text-sm" style="color: var(--text-muted)">{{ ep.episode_number }}</span>
              <div class="flex-1 min-w-0">
                <div class="text-sm truncate">{{ ep.title || `第 ${ep.episode_number} 集` }}</div>
                <div class="text-xs" style="color: var(--text-faint)">{{ ep.air_date || '' }}</div>
              </div>
              <svg class="w-5 h-5 shrink-0" style="color: var(--text-faint)" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
            </div>
          </div>
        </div>
      </div>
    </div>



    <!-- 编辑元数据模态框 -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="editModalVisible" class="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <!-- 遮罩 -->
          <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="closeEditModal" />
          <!-- 模态框 -->
          <div class="relative w-full max-w-2xl max-h-[85vh] overflow-y-auto bg-[var(--bg-card-solid)] border border-[var(--border-primary)] rounded-2xl shadow-2xl">
            <!-- 头部 -->
            <div class="sticky top-0 z-10 flex items-center justify-between px-6 py-4 border-b border-[var(--border-primary)] bg-[var(--bg-card-solid)]">
              <h2 class="text-lg font-semibold">编辑元数据</h2>
              <button @click="closeEditModal" class="p-1 rounded-lg hover:bg-[var(--bg-hover)] transition-colors" style="color: var(--text-muted)">
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
              </button>
            </div>

            <!-- 表单 -->
            <div class="p-6 space-y-5">
              <!-- 标题 & 原标题 -->
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label class="block text-xs font-medium mb-1.5" style="color: var(--text-muted)">标题</label>
                  <input v-model="editForm.title" class="input w-full text-sm" placeholder="媒体标题" />
                </div>
                <div>
                  <label class="block text-xs font-medium mb-1.5" style="color: var(--text-muted)">原标题</label>
                  <input v-model="editForm.original_title" class="input w-full text-sm" placeholder="Original Title" />
                </div>
              </div>

              <!-- 年份 & 类型 & 评分 -->
              <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div>
                  <label class="block text-xs font-medium mb-1.5" style="color: var(--text-muted)">年份</label>
                  <input v-model.number="editForm.year" type="number" class="input w-full text-sm" placeholder="2024" min="1900" max="2030" />
                </div>
                <div>
                  <label class="block text-xs font-medium mb-1.5" style="color: var(--text-muted)">类型</label>
                  <select v-model="editForm.media_type" class="input w-full text-sm">
                    <option value="movie">电影</option>
                    <option value="tv">电视剧</option>
                    <option value="anime">动漫</option>
                  </select>
                </div>
                <div>
                  <label class="block text-xs font-medium mb-1.5" style="color: var(--text-muted)">TMDb 评分</label>
                  <input v-model.number="editForm.rating" type="number" class="input w-full text-sm" placeholder="0" min="0" max="10" step="0.1" />
                </div>
                <div>
                  <label class="block text-xs font-medium mb-1.5" style="color: var(--text-muted)">豆瓣评分</label>
                  <input v-model.number="editForm.douban_rating" type="number" class="input w-full text-sm" placeholder="0" min="0" max="10" step="0.1" />
                </div>
              </div>

              <!-- Bangumi 评分 & TMDb ID & 时长 -->
              <div class="grid grid-cols-3 gap-4">
                <div>
                  <label class="block text-xs font-medium mb-1.5" style="color: var(--text-muted)">Bangumi 评分</label>
                  <input v-model.number="editForm.bangumi_rating" type="number" class="input w-full text-sm" placeholder="0" min="0" max="10" step="0.1" />
                </div>
                <div>
                  <label class="block text-xs font-medium mb-1.5" style="color: var(--text-muted)">TMDb ID</label>
                  <input v-model.number="editForm.tmdb_id" type="number" class="input w-full text-sm" placeholder="如 12345" />
                </div>
                <div>
                  <label class="block text-xs font-medium mb-1.5" style="color: var(--text-muted)">时长(分钟)</label>
                  <input v-model.number="editForm.duration" type="number" class="input w-full text-sm" placeholder="120" min="0" />
                </div>
              </div>

              <!-- 类型标签 -->
              <div>
                <label class="block text-xs font-medium mb-1.5" style="color: var(--text-muted)">类型标签（逗号分隔）</label>
                <input v-model="editForm.genresStr" class="input w-full text-sm" placeholder="动作, 科幻, 冒险" />
              </div>

              <!-- 海报 URL & 背景 URL -->
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label class="block text-xs font-medium mb-1.5" style="color: var(--text-muted)">海报 URL</label>
                  <input v-model="editForm.poster_url" class="input w-full text-sm" placeholder="https://image.tmdb.org/..." />
                </div>
                <div>
                  <label class="block text-xs font-medium mb-1.5" style="color: var(--text-muted)">背景图 URL</label>
                  <input v-model="editForm.backdrop_url" class="input w-full text-sm" placeholder="https://image.tmdb.org/..." />
                </div>
              </div>

              <!-- 简介 -->
              <div>
                <label class="block text-xs font-medium mb-1.5" style="color: var(--text-muted)">简介</label>
                <textarea v-model="editForm.overview" rows="4" class="input w-full text-sm resize-y" placeholder="剧情简介..." />
              </div>
            </div>

            <!-- 底部操作 -->
            <div class="sticky bottom-0 flex items-center justify-end gap-3 px-6 py-4 border-t border-[var(--border-primary)] bg-[var(--bg-card-solid)]">
              <button @click="closeEditModal" class="btn-secondary text-sm">取消</button>
              <button @click="saveMetadata" :disabled="saving"
                class="btn-primary text-sm flex items-center gap-2 disabled:opacity-50">
                <svg v-if="saving" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
                {{ saving ? '保存中...' : '保存' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { mediaApi } from '@/api/media'
import { playbackApi } from '@/api/playback'
import { dlnaApi } from '@/api/dlna'
import { subscribeApi } from '@/api/subscribe'
import { useAuthStore } from '@/stores/auth'
import { useFormat } from '@/composables/useFormat'
import { useToast } from '@/composables/useToast'

const { formatDuration } = useFormat()
const toast = useToast()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const isAdmin = computed(() => auth.isAdmin)

const item = ref<any>(null)
const loading = ref(true)
const scraping = ref(false)
const aiScraping = ref(false)
const isFavorited = ref(false)
const favLoading = ref(false)
const externalMenuVisible = ref(false)
const externalMenuRef = ref<HTMLElement>()
const dlnaMenuVisible = ref(false)
const dlnaMenuRef = ref<HTMLElement>()
const dlnaDevices = ref<any[]>([])
const dlnaLoading = ref(false)
const externalUrl = ref('')
const copySuccess = ref(false)
const subscribing = ref(false)

// ── 编辑元数据 ──
const editModalVisible = ref(false)
const saving = ref(false)
// 数字字段可能为空字符串(number input)或数字或null
type NumberField = number | null | ''
const editForm = reactive({
  title: '',
  original_title: '',
  year: null as NumberField,
  media_type: 'movie',
  rating: null as NumberField,
  douban_rating: null as NumberField,
  bangumi_rating: null as NumberField,
  tmdb_id: null as NumberField,
  duration: null as NumberField,
  genresStr: '',
  poster_url: '',
  backdrop_url: '',
  overview: '',
})

function openEditModal() {
  if (!item.value) return
  editForm.title = item.value.title || ''
  editForm.original_title = item.value.original_title || ''
  editForm.year = item.value.year || null
  editForm.media_type = item.value.media_type || 'movie'
  editForm.rating = item.value.rating || null
  editForm.douban_rating = item.value.douban_rating || null
  editForm.bangumi_rating = item.value.bangumi_rating || null
  editForm.tmdb_id = item.value.tmdb_id || null
  editForm.duration = item.value.duration || null
  editForm.genresStr = Array.isArray(item.value.genres) ? item.value.genres.join(', ') : ''
  editForm.poster_url = item.value.poster_url || ''
  editForm.backdrop_url = item.value.backdrop_url || ''
  editForm.overview = item.value.overview || ''
  editModalVisible.value = true
}

function closeEditModal() {
  editModalVisible.value = false
}

async function saveMetadata() {
  if (!item.value) return
  saving.value = true
  try {
    const payload: any = {}
    // 只发送有变化的字段
    if (editForm.title !== item.value.title) payload.title = editForm.title
    if (editForm.original_title !== item.value.original_title) payload.original_title = editForm.original_title
    // year: 确保为空时发送 null 而不是空字符串
    const editYear = editForm.year === '' || editForm.year === null ? null : editForm.year
    const oldYear = item.value.year || null
    if (editYear !== oldYear) payload.year = editYear
    if (editForm.media_type !== item.value.media_type) payload.media_type = editForm.media_type
    // rating: 确保为空时发送 null
    const editRating = editForm.rating === '' ? null : editForm.rating
    if (editRating !== (item.value.rating || null)) payload.rating = editRating
    // douban_rating
    const editDoubanRating = editForm.douban_rating === '' ? null : editForm.douban_rating
    if (editDoubanRating !== (item.value.douban_rating || null)) payload.douban_rating = editDoubanRating
    // bangumi_rating
    const editBangumiRating = editForm.bangumi_rating === '' ? null : editForm.bangumi_rating
    if (editBangumiRating !== (item.value.bangumi_rating || null)) payload.bangumi_rating = editBangumiRating
    // tmdb_id
    const editTmdbId = editForm.tmdb_id === '' ? null : editForm.tmdb_id
    if (editTmdbId !== (item.value.tmdb_id || null)) payload.tmdb_id = editTmdbId
    // duration
    const editDuration = editForm.duration === '' ? null : editForm.duration
    if (editDuration !== (item.value.duration || null)) payload.duration = editDuration

    const newGenres = editForm.genresStr ? editForm.genresStr.split(/[,，]/).map(s => s.trim()).filter(Boolean) : []
    const oldGenres = Array.isArray(item.value.genres) ? item.value.genres : []
    if (JSON.stringify(newGenres) !== JSON.stringify(oldGenres)) payload.genres = newGenres

    if (editForm.poster_url !== (item.value.poster_url || '')) payload.poster_url = editForm.poster_url
    if (editForm.backdrop_url !== (item.value.backdrop_url || '')) payload.backdrop_url = editForm.backdrop_url
    if (editForm.overview !== (item.value.overview || '')) payload.overview = editForm.overview

    if (Object.keys(payload).length === 0) {
      toast.info('没有修改任何内容')
      closeEditModal()
      return
    }

    const { data } = await mediaApi.updateItem(item.value.id, payload)
    item.value = data
    closeEditModal()
    toast.success('元数据已更新')
  } catch (e: any) {
    toast.error(`保存失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    saving.value = false
  }
}

const externalPlayers = [
  { name: 'Infuse', icon: '🎬', scheme: 'infuse://x-callback-url/play?url=' },
  { name: 'VLC', icon: '🟠', scheme: 'vlc://' },
  { name: 'IINA', icon: '🎬', scheme: 'iina://weblink?url=' },
  { name: 'NPlayer', icon: '▶️', scheme: 'nplayer-' },
  { name: 'MX Player', icon: '📱', scheme: 'intent:' },
  { name: 'Kodi', icon: '📺', scheme: '' },
]

function handleClickOutside(e: MouseEvent) {
  if (externalMenuRef.value && !externalMenuRef.value.contains(e.target as Node)) {
    externalMenuVisible.value = false
  }
  if (dlnaMenuRef.value && !dlnaMenuRef.value.contains(e.target as Node)) {
    dlnaMenuVisible.value = false
  }
}

onMounted(() => {
  loadItem()
  document.addEventListener('click', handleClickOutside)
})
onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

async function loadItem() {
  loading.value = true
  try {
    const { data } = await mediaApi.getDetail(Number(route.params.id))
    item.value = data
    // 加载收藏状态
    loadFavoriteStatus()
  } catch (e) {
    console.error(e)
    router.push('/media')
  } finally {
    loading.value = false
  }
}

async function scrape() {
  scraping.value = true
  try {
    const { data } = await mediaApi.scrapeItem(item.value.id)
    item.value = data
    toast.success('元数据获取成功')
  } catch (e: any) {
    toast.error(`刮削失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    scraping.value = false
  }
}

async function rescrapeConfirm() {
  if (!item.value) return
  // 使用确认对话框提示用户
  if (!confirm(`确定要重新刮削「${item.value.title}」的元数据吗？\n\n当前元数据将被覆盖。如果识别不准确，可以先手动编辑标题后再重新刮削。`)) {
    return
  }
  scraping.value = true
  try {
    const { data } = await mediaApi.scrapeItem(item.value.id)
    item.value = data
    toast.success('元数据已重新获取')
  } catch (e: any) {
    toast.error(`刮削失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    scraping.value = false
  }
}

async function aiScrape() {
  aiScraping.value = true
  try {
    const { data } = await mediaApi.aiScrape(item.value.id, {
      operations: ['overview', 'title', 'tags', 'validate'],
      apply: true,
    })
    if (data.success) {
      item.value = { ...item.value, ...(data.data || {}) }
      toast.success(`AI 优化完成! 置信度: ${(data.data?.confidence * 100)?.toFixed(0)}%`)
    } else {
      toast.error(`AI 优化失败: ${data.error}`)
    }
  } catch (e: any) {
    toast.error(`AI 优化失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    aiScraping.value = false
  }
}

// ── 收藏 ──
async function loadFavoriteStatus() {
  try {
    const { data } = await mediaApi.checkFavorite(item.value.id)
    isFavorited.value = data.is_favorite
  } catch { /* 静默 */ }
}

async function toggleFavorite() {
  favLoading.value = true
  try {
    if (isFavorited.value) {
      await mediaApi.removeFavorite(item.value.id)
      isFavorited.value = false
      toast.info('已取消收藏')
    } else {
      await mediaApi.addFavorite(item.value.id)
      isFavorited.value = true
      toast.success('已添加到收藏')
    }
  } catch (e: any) {
    toast.error(`操作失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    favLoading.value = false
  }
}

function play(mediaId: number, episodeId?: number) {
  router.push({ path: `/player/${mediaId}`, query: episodeId ? { episode: String(episodeId) } : {} })
}

function toggleExternalMenu() {
  externalMenuVisible.value = !externalMenuVisible.value
}

async function loadExternalUrl(episodeId?: number) {
  if (externalUrl.value) return externalUrl.value
  const { data } = await playbackApi.getExternalUrl(item.value.id, episodeId)
  const base = window.location.origin
  externalUrl.value = base + data.url
  return externalUrl.value
}

async function openExternalPlayer(player: any) {
  try {
    const url = await loadExternalUrl()
    externalMenuVisible.value = false

    if (player.name === 'Kodi') {
      await navigator.clipboard.writeText(url)
      toast.info(`已复制播放地址，请在 Kodi 中添加。\n\n地址: ${url}`)
      return
    }

    if (player.name === 'MX Player') {
      window.location.href = `intent:${encodeURIComponent(url)}#Intent;scheme=https;type=video/mp4;end`
      return
    }

    if (player.name === 'NPlayer') {
      window.location.href = `nplayer-${url.replace(/^https?:\/\//, '')}`
      return
    }

    const fullUrl = player.scheme + encodeURIComponent(url)
    window.location.href = fullUrl
  } catch (e: any) {
    console.error('打开外部播放器失败:', e)
    try {
      const url = await loadExternalUrl()
      await navigator.clipboard.writeText(url)
      toast.info(`无法直接唤起播放器，已复制地址到剪贴板。`)
    } catch {
      toast.error('操作失败，请重试')
    }
  }
}

async function copyExternalUrl() {
  try {
    const url = await loadExternalUrl()
    await navigator.clipboard.writeText(url)
    externalMenuVisible.value = false
    copySuccess.value = true
    setTimeout(() => { copySuccess.value = false }, 2000)
  } catch (e) {
    toast.error('复制失败，请手动复制')
  }
}

// ── 订阅下载 ──
async function handleSubscribe() {
  if (!item.value) return
  subscribing.value = true
  try {
    await subscribeApi.createSubscription({
      name: item.value.title,
      tmdb_id: item.value.tmdb_id || null,
      media_type: item.value.media_type || 'movie',
      year: item.value.year || null,
      quality_filter: ['1080p', '720p'],
    })
    toast.success(`「${item.value.title}」已添加到订阅列表！`)
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

// ── DLNA ──
function toggleDlnaMenu() {
  dlnaMenuVisible.value = !dlnaMenuVisible.value
  if (dlnaMenuVisible.value && dlnaDevices.value.length === 0) {
    discoverDlna()
  }
}

async function discoverDlna() {
  dlnaLoading.value = true
  try {
    const { data } = await dlnaApi.discover(true)
    dlnaDevices.value = data.devices || []
  } catch (e: any) {
    console.error('DLNA discover failed:', e)
  } finally {
    dlnaLoading.value = false
  }
}

async function castToDlna(dev: any) {
  try {
    const url = await loadExternalUrl()
    const base = window.location.origin
    const fullUrl = base + url

    dlnaMenuVisible.value = false
    toast.info(`正在推送到 ${dev.name}...`)

    const { data } = await dlnaApi.cast({
      device_uuid: dev.uuid,
      media_url: fullUrl,
      title: item.value.title,
    })

    if (data.ok) {
      toast.success(data.message || '投屏成功！')
    } else {
      toast.error(`投屏失败: ${data.error}`)
    }
  } catch (e: any) {
    toast.error(`投屏失败: ${e.response?.data?.detail || e.message}`)
  }
}

</script>

<style scoped>
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
.scale-enter-active, .scale-leave-active {
  transition: all 0.15s ease;
}
.scale-enter-from, .scale-leave-to {
  opacity: 0;
  transform: scale(0.95);
}
</style>
