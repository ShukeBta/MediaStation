<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <p class="text-sm" style="color: var(--text-muted)">配置文件整理规则和元数据刮削选项</p>
    </div>

    <!-- 整理配置区块 -->
    <div class="card p-5 space-y-4">
      <h3 class="font-medium flex items-center gap-2" style="color: var(--text-primary)">
        <span class="text-lg">📁</span> 文件整理规则
      </h3>
      <p class="text-xs" style="color: var(--text-muted)">
        配置下载完成后的自动整理规则，支持 Jinja2 模板语法
      </p>

      <!-- 电影重命名格式 -->
      <div>
        <div class="flex items-center justify-between mb-1.5">
          <label class="text-sm" style="color: var(--text-muted)">电影重命名格式</label>
          <button @click="showMoviePreview = !showMoviePreview" class="text-xs text-brand-400 hover:underline">
            {{ showMoviePreview ? '隐藏预览' : '显示预览' }}
          </button>
        </div>
        <textarea
          v-model="form.organize.movie_rename_format"
          rows="2"
          class="input font-mono text-xs"
          placeholder="{{title}} ({{year}})/{{title}} ({{year}}) - {{resolution}}{{fileExt}}"
        ></textarea>
        <p class="text-xs mt-1" style="color: var(--text-faint)">
          变量: title, year, resolution, fileExt
        </p>

        <!-- 预览 -->
        <div v-if="showMoviePreview" class="mt-2 p-3 rounded-lg border"
          :style="{ background: 'var(--bg-elevated)', borderColor: 'var(--border-primary)' }">
          <p class="text-xs mb-2" style="color: var(--text-muted)">预览（示例：Title (2024) / Title (2024) - 1080p.mkv）</p>
          <p class="text-xs font-mono" style="color: var(--text-primary)">
            {{ previewMoviePath }}
          </p>
        </div>
      </div>

      <!-- 电视剧重命名格式 -->
      <div>
        <div class="flex items-center justify-between mb-1.5">
          <label class="text-sm" style="color: var(--text-muted)">电视剧重命名格式</label>
          <button @click="showTvPreview = !showTvPreview" class="text-xs text-brand-400 hover:underline">
            {{ showTvPreview ? '隐藏预览' : '显示预览' }}
          </button>
        </div>
        <textarea
          v-model="form.organize.tv_rename_format"
          rows="2"
          class="input font-mono text-xs"
          placeholder="{{title}}/Season {{season}}/{{title}} - {{season_episode}}{{fileExt}}"
        ></textarea>
        <p class="text-xs mt-1" style="color: var(--text-faint)">
          变量: title, year, season, episode, season_episode, resolution, fileExt
        </p>

        <!-- 预览 -->
        <div v-if="showTvPreview" class="mt-2 p-3 rounded-lg border"
          :style="{ background: 'var(--bg-elevated)', borderColor: 'var(--border-primary)' }">
          <p class="text-xs mb-2" style="color: var(--text-muted)">预览（示例：Title (2024)/Season 01/Title - S01E01 - 第 1 集.mkv）</p>
          <p class="text-xs font-mono" style="color: var(--text-primary)">
            {{ previewTvPath }}
          </p>
        </div>
      </div>

      <!-- 动漫重命名格式 -->
      <div>
        <div class="flex items-center justify-between mb-1.5">
          <label class="text-sm" style="color: var(--text-muted)">动漫重命名格式</label>
        </div>
        <textarea
          v-model="form.organize.anime_rename_format"
          rows="2"
          class="input font-mono text-xs"
          placeholder="{{title}}/Season {{season}}/[{{season_episode}}] {{title}}{{fileExt}}"
        ></textarea>
        <p class="text-xs mt-1" style="color: var(--text-faint)">
          变量: title, year, season, episode, season_episode, fileExt
        </p>
      </div>

      <!-- 整理模式 -->
      <div>
        <label class="block text-sm mb-1.5" style="color: var(--text-muted)">整理模式</label>
        <select v-model="form.organize.mode" class="input !w-auto">
          <option value="move_to_library">移动到媒体库</option>
          <option value="keep_in_place">保留在原目录</option>
        </select>
        <p class="text-xs mt-1" style="color: var(--text-faint)">
          选择是否将刮削后的文件转移到媒体库目录
        </p>
      </div>

      <!-- 开关选项 -->
      <div class="space-y-3 pt-2">
        <!-- 自动整理 -->
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm" style="color: var(--text-primary)">下载完成自动整理</p>
            <p class="text-xs" style="color: var(--text-faint)">下载完成后自动整理文件到媒体库</p>
          </div>
          <button @click="form.organize.auto_organize = form.organize.auto_organize === 'true' ? 'false' : 'true'"
            type="button" role="switch"
            :aria-checked="form.organize.auto_organize === 'true'"
            :class="[
              'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full transition-colors duration-200',
              form.organize.auto_organize === 'true' ? 'bg-emerald-500' : 'bg-gray-600',
            ]">
            <span :class="[
              'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5 ml-0.5',
              form.organize.auto_organize === 'true' ? 'translate-x-5' : '',
            ]"></span>
          </button>
        </div>

        <!-- 同步移动字幕 -->
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm" style="color: var(--text-primary)">同步移动字幕</p>
            <p class="text-xs" style="color: var(--text-faint)">整理视频时同步移动关联的字幕文件</p>
          </div>
          <button @click="form.organize.move_subtitles = form.organize.move_subtitles === 'true' ? 'false' : 'true'"
            type="button" role="switch"
            :aria-checked="form.organize.move_subtitles === 'true'"
            :class="[
              'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full transition-colors duration-200',
              form.organize.move_subtitles === 'true' ? 'bg-emerald-500' : 'bg-gray-600',
            ]">
            <span :class="[
              'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5 ml-0.5',
              form.organize.move_subtitles === 'true' ? 'translate-x-5' : '',
            ]"></span>
          </button>
        </div>

        <!-- 清理空目录 -->
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm" style="color: var(--text-primary)">清理空目录</p>
            <p class="text-xs" style="color: var(--text-faint)">整理完成后删除空文件夹</p>
          </div>
          <button @click="form.organize.cleanup_empty_dirs = form.organize.cleanup_empty_dirs === 'true' ? 'false' : 'true'"
            type="button" role="switch"
            :aria-checked="form.organize.cleanup_empty_dirs === 'true'"
            :class="[
              'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full transition-colors duration-200',
              form.organize.cleanup_empty_dirs === 'true' ? 'bg-emerald-500' : 'bg-gray-600',
            ]">
            <span :class="[
              'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5 ml-0.5',
              form.organize.cleanup_empty_dirs === 'true' ? 'translate-x-5' : '',
            ]"></span>
          </button>
        </div>
      </div>
    </div>

    <!-- 刮削配置区块 -->
    <div class="card p-5 space-y-4">
      <h3 class="font-medium flex items-center gap-2" style="color: var(--text-primary)">
        <span class="text-lg">🔍</span> 元数据刮削
      </h3>
      <p class="text-xs" style="color: var(--text-muted)">
        配置刮削数据源优先级和刮削行为
      </p>

      <!-- 刮削数据源 -->
      <div>
        <label class="block text-sm mb-1.5" style="color: var(--text-muted)">刮削数据源优先级</label>
        <input
          v-model="form.scrape.providers"
          class="input"
          placeholder="tmdb,douban,bangumi"
        />
        <p class="text-xs mt-1" style="color: var(--text-faint)">
          用逗号分隔，支持: tmdb, douban, bangumi, thetvdb
        </p>
        <div class="flex flex-wrap gap-2 mt-2">
          <span
            v-for="p in availableProviders"
            :key="p.value"
            @click="toggleProvider(p.value)"
            :class="[
              'px-2 py-1 rounded-full text-xs cursor-pointer transition-colors',
              form.scrape.providers.includes(p.value)
                ? 'bg-brand-500/20 text-brand-400'
                : 'bg-gray-700/50 text-gray-400 hover:bg-gray-700'
            ]"
          >
            {{ p.label }}
          </span>
        </div>
      </div>

      <!-- 语言选择 -->
      <div>
        <label class="block text-sm mb-1.5" style="color: var(--text-muted)">刮削语言</label>
        <select v-model="form.scrape.language" class="input !w-auto">
          <option value="zh-CN">简体中文</option>
          <option value="zh-TW">繁体中文</option>
          <option value="en">English</option>
          <option value="ja">日本語</option>
        </select>
        <p class="text-xs mt-1" style="color: var(--text-faint)">
          刮削时优先返回的语言
        </p>
      </div>

      <!-- 海报尺寸 -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label class="block text-sm mb-1.5" style="color: var(--text-muted)">海报尺寸</label>
          <select v-model="form.scrape.poster_size" class="input !w-auto">
            <option value="w185">小 (185px)</option>
            <option value="w342">中 (342px)</option>
            <option value="w500">大 (500px)</option>
            <option value="original">原始尺寸</option>
          </select>
        </div>
        <div>
          <label class="block text-sm mb-1.5" style="color: var(--text-muted)">背景图尺寸</label>
          <select v-model="form.scrape.backdrop_size" class="input !w-auto">
            <option value="w300">小 (300px)</option>
            <option value="w780">中 (780px)</option>
            <option value="w1280">大 (1280px)</option>
            <option value="original">原始尺寸</option>
          </select>
        </div>
      </div>

      <!-- 开关选项 -->
      <div class="space-y-3 pt-2">
        <!-- 自动刮削 -->
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm" style="color: var(--text-primary)">扫描时自动刮削</p>
            <p class="text-xs" style="color: var(--text-faint)">媒体库扫描时自动刮削缺失的元数据</p>
          </div>
          <button @click="form.scrape.auto_scrape_on_scan = form.scrape.auto_scrape_on_scan === 'true' ? 'false' : 'true'"
            type="button" role="switch"
            :aria-checked="form.scrape.auto_scrape_on_scan === 'true'"
            :class="[
              'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full transition-colors duration-200',
              form.scrape.auto_scrape_on_scan === 'true' ? 'bg-emerald-500' : 'bg-gray-600',
            ]">
            <span :class="[
              'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5 ml-0.5',
              form.scrape.auto_scrape_on_scan === 'true' ? 'translate-x-5' : '',
            ]"></span>
          </button>
        </div>

        <!-- 添加时自动刮削 -->
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm" style="color: var(--text-primary)">添加时自动刮削</p>
            <p class="text-xs" style="color: var(--text-faint)">添加新文件时自动刮削元数据</p>
          </div>
          <button @click="form.scrape.auto_scrape_on_add = form.scrape.auto_scrape_on_add === 'true' ? 'false' : 'true'"
            type="button" role="switch"
            :aria-checked="form.scrape.auto_scrape_on_add === 'true'"
            :class="[
              'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full transition-colors duration-200',
              form.scrape.auto_scrape_on_add === 'true' ? 'bg-emerald-500' : 'bg-gray-600',
            ]">
            <span :class="[
              'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5 ml-0.5',
              form.scrape.auto_scrape_on_add === 'true' ? 'translate-x-5' : '',
            ]"></span>
          </button>
        </div>

        <!-- 覆盖已有 -->
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm" style="color: var(--text-primary)">覆盖已有元数据</p>
            <p class="text-xs" style="color: var(--text-faint)">刮削时覆盖已存在的元数据</p>
          </div>
          <button @click="form.scrape.overwrite_existing = form.scrape.overwrite_existing === 'true' ? 'false' : 'true'"
            type="button" role="switch"
            :aria-checked="form.scrape.overwrite_existing === 'true'"
            :class="[
              'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full transition-colors duration-200',
              form.scrape.overwrite_existing === 'true' ? 'bg-emerald-500' : 'bg-gray-600',
            ]">
            <span :class="[
              'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5 ml-0.5',
              form.scrape.overwrite_existing === 'true' ? 'translate-x-5' : '',
            ]"></span>
          </button>
        </div>
      </div>
    </div>

    <!-- 保存按钮 -->
    <div class="flex justify-end gap-3">
      <button @click="loadSettings" class="btn-secondary text-sm">重置</button>
      <button @click="save" :disabled="saving" class="btn-primary text-sm disabled:opacity-50 flex items-center gap-2">
        <svg v-if="saving" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
        </svg>
        {{ saving ? '保存中...' : '保存配置' }}
      </button>
    </div>

    <!-- 保存提示 -->
    <div v-if="savedMsg" class="rounded-lg p-3 text-sm flex items-center gap-2 border"
      :class="savedMsg.type === 'success'
        ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
        : 'bg-red-500/10 border-red-500/30 text-red-400'">
      <svg v-if="savedMsg.type === 'success'" class="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
      </svg>
      <svg v-else class="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
      </svg>
      {{ savedMsg.text }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { settingsApi } from '@/api/settings'

// 可用的数据源列表
const availableProviders = [
  { value: 'tmdb', label: 'TheMovieDb (TMDb)' },
  { value: 'douban', label: '豆瓣' },
  { value: 'bangumi', label: 'Bangumi' },
  { value: 'thetvdb', label: 'TheTVDB' },
]

// 表单数据
const form = ref({
  organize: {
    mode: 'move_to_library',
    movie_rename_format: '{{title}}{% if year %} ({{year}}){% endif %}/{{title}}{% if year %} ({{year}}){% endif %}{% if resolution %} - {{resolution}}{% endif %}{{fileExt}}',
    tv_rename_format: '{{title}}{% if year %} ({{year}}){% endif %}/Season {{season}}/{{title}} - {{season_episode}}{% if episode %} - 第 {{episode}} 集{% endif %}{{fileExt}}',
    anime_rename_format: '{{title}}{% if year %} ({{year}}){% endif %}/Season {{season}}/[{{season_episode}}] {{title}}{{fileExt}}',
    auto_organize: 'true',
    move_subtitles: 'true',
    cleanup_empty_dirs: 'true',
  },
  scrape: {
    providers: 'tmdb',
    language: 'zh-CN',
    poster_size: 'w500',
    backdrop_size: 'original',
    auto_scrape_on_scan: 'true',
    auto_scrape_on_add: 'true',
    overwrite_existing: 'false',
  },
})

// 默认值（用于重置）
const defaults = {
  organize: {
    mode: 'move_to_library',
    movie_rename_format: '{{title}}{% if year %} ({{year}}){% endif %}/{{title}}{% if year %} ({{year}}){% endif %}{% if resolution %} - {{resolution}}{% endif %}{{fileExt}}',
    tv_rename_format: '{{title}}{% if year %} ({{year}}){% endif %}/Season {{season}}/{{title}} - {{season_episode}}{% if episode %} - 第 {{episode}} 集{% endif %}{{fileExt}}',
    anime_rename_format: '{{title}}{% if year %} ({{year}}){% endif %}/Season {{season}}/[{{season_episode}}] {{title}}{{fileExt}}',
    auto_organize: 'true',
    move_subtitles: 'true',
    cleanup_empty_dirs: 'true',
  },
  scrape: {
    providers: 'tmdb',
    language: 'zh-CN',
    poster_size: 'w500',
    backdrop_size: 'original',
    auto_scrape_on_scan: 'true',
    auto_scrape_on_add: 'true',
    overwrite_existing: 'false',
  },
}

const saving = ref(false)
const savedMsg = ref<{ type: 'success' | 'error'; text: string } | null>(null)
const showMoviePreview = ref(false)
const showTvPreview = ref(false)

// 预览路径
const previewMoviePath = computed(() => {
  return 'Title (2024)/Title (2024) - 1080p.mkv'
})

const previewTvPath = computed(() => {
  return 'Title (2024)/Season 01/Title - S01E01 - 第 1 集.mkv'
})

// 切换数据源
function toggleProvider(provider: string) {
  const current = form.value.scrape.providers.split(',').map(p => p.trim())
  const index = current.indexOf(provider)
  if (index > -1) {
    current.splice(index, 1)
  } else {
    current.push(provider)
  }
  form.value.scrape.providers = current.join(',')
}

// 加载设置
async function loadSettings() {
  try {
    const { data } = await settingsApi.getAll()
    // 填充整理配置
    if (data['organize.movie_rename_format']) {
      form.value.organize.movie_rename_format = data['organize.movie_rename_format']
    }
    if (data['organize.tv_rename_format']) {
      form.value.organize.tv_rename_format = data['organize.tv_rename_format']
    }
    if (data['organize.anime_rename_format']) {
      form.value.organize.anime_rename_format = data['organize.anime_rename_format']
    }
    form.value.organize.auto_organize = data['organize.auto_organize'] || 'true'
    form.value.organize.move_subtitles = data['organize.move_subtitles'] || 'true'
    form.value.organize.cleanup_empty_dirs = data['organize.cleanup_empty_dirs'] || 'true'
    form.value.organize.mode = data['organize.mode'] || 'move_to_library'

    // 填充刮削配置
    if (data['scrape.providers']) {
      form.value.scrape.providers = data['scrape.providers']
    }
    if (data['scrape.language']) {
      form.value.scrape.language = data['scrape.language']
    }
    if (data['scrape.poster_size']) {
      form.value.scrape.poster_size = data['scrape.poster_size']
    }
    if (data['scrape.backdrop_size']) {
      form.value.scrape.backdrop_size = data['scrape.backdrop_size']
    }
    form.value.scrape.auto_scrape_on_scan = data['scrape.auto_scrape_on_scan'] || 'true'
    form.value.scrape.auto_scrape_on_add = data['scrape.auto_scrape_on_add'] || 'true'
    form.value.scrape.overwrite_existing = data['scrape.overwrite_existing'] || 'false'
  } catch (e) {
    console.error('加载设置失败:', e)
  }
}

// 保存设置
async function save() {
  saving.value = true
  savedMsg.value = null
  try {
    const settings: Record<string, string> = {}

    // 整理配置
    settings['organize.movie_rename_format'] = form.value.organize.movie_rename_format
    settings['organize.tv_rename_format'] = form.value.organize.tv_rename_format
    settings['organize.anime_rename_format'] = form.value.organize.anime_rename_format
    settings['organize.auto_organize'] = form.value.organize.auto_organize
    settings['organize.move_subtitles'] = form.value.organize.move_subtitles
    settings['organize.cleanup_empty_dirs'] = form.value.organize.cleanup_empty_dirs
    settings['organize.mode'] = form.value.organize.mode

    // 刮削配置
    settings['scrape.providers'] = form.value.scrape.providers
    settings['scrape.language'] = form.value.scrape.language
    settings['scrape.poster_size'] = form.value.scrape.poster_size
    settings['scrape.backdrop_size'] = form.value.scrape.backdrop_size
    settings['scrape.auto_scrape_on_scan'] = form.value.scrape.auto_scrape_on_scan
    settings['scrape.auto_scrape_on_add'] = form.value.scrape.auto_scrape_on_add
    settings['scrape.overwrite_existing'] = form.value.scrape.overwrite_existing

    await settingsApi.batchUpdate(settings)
    savedMsg.value = { type: 'success', text: '配置已保存' }
    setTimeout(() => { savedMsg.value = null }, 4000)
  } catch (e: any) {
    let errorMsg = '未知错误'
    const detail = e.response?.data?.detail
    if (Array.isArray(detail)) {
      errorMsg = detail.map((d: any) => d.msg || d.message || JSON.stringify(d)).join('; ')
    } else if (typeof detail === 'string') {
      errorMsg = detail
    } else if (e.message) {
      errorMsg = e.message
    }
    savedMsg.value = {
      type: 'error',
      text: `保存失败: ${errorMsg}`,
    }
  } finally {
    saving.value = false
  }
}

onMounted(() => loadSettings())
</script>
