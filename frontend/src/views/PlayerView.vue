<template>
  <div class="relative z-50 bg-black flex flex-col" ref="playerContainer"
    :style="playerContainerStyle">
    <!-- 顶部信息栏 -->
    <div class="shrink-0 flex items-center gap-4 px-4 py-2 bg-black/80 backdrop-blur">
      <button @click="goBack" class="text-gray-400 hover:text-white transition-colors">
        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
      </button>
      <div class="flex-1 min-w-0">
        <div class="text-white text-sm font-medium truncate">{{ mediaInfo?.title || '加载中...' }}</div>
        <div v-if="currentEpisode" class="text-gray-500 text-xs truncate">
          {{ currentEpisode.season_number ? `S${String(currentEpisode.season_number).padStart(2,'0')}` : '' }}
          E{{ String(currentEpisode.episode_number).padStart(2,'0') }}
          {{ currentEpisode.title || '' }}
        </div>
        <!-- 文件信息标签 -->
        <div v-if="mediaInfo?.file_info" class="flex items-center gap-2 mt-0.5">
          <span class="text-[10px] px-1.5 py-0.5 rounded bg-brand-600/30 text-brand-300 uppercase font-mono">
            {{ mediaInfo.file_info.container || 'N/A' }}
          </span>
          <span v-if="mediaInfo.file_info.video_codec" class="text-[10px] text-gray-500">
            {{ mediaInfo.file_info.video_codec.toUpperCase() }}
          </span>
          <span v-if="mediaInfo.file_info.resolution" class="text-[10px] text-gray-500">
            {{ mediaInfo.file_info.resolution }}
          </span>
          <span
            :class="[
              'text-[10px] px-1.5 py-0.5 rounded uppercase font-medium',
              mediaInfo.stream_mode === 'direct'
                ? 'bg-emerald-500/20 text-emerald-400'
                : 'bg-amber-500/20 text-amber-400',
            ]">
            {{ mediaInfo.stream_mode === 'direct' ? '直连播放' : 'HLS转码' }}
          </span>
          <span v-if="mediaInfo?.status === 'started'" class="text-[10px] text-amber-400 animate-pulse">转码中...</span>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <!-- 剧集列表切换 -->
        <button v-if="episodeList.length > 0" @click="showEpisodeList = !showEpisodeList"
          :class="['text-sm px-2 py-1 rounded transition-colors', showEpisodeList ? 'bg-brand-600/30 text-brand-400' : 'text-gray-400 hover:text-white']">
          选集
        </button>
        <select
          v-model="quality"
          @change="changeQuality"
          class="bg-gray-800/80 text-gray-300 text-xs rounded px-2 py-1 border border-gray-700 focus:outline-none focus:border-brand-500 transition-colors"
          :disabled="!transcodeEnabled && quality !== 'original'"
          title="画质选择"
        >
          <option value="auto">自动</option>
          <option value="original">原画直连</option>
          <template v-if="transcodeEnabled">
            <option value="4k">4K (转码)</option>
            <option value="1080p">1080P (转码)</option>
            <option value="720p">720P (转码)</option>
            <option value="480p">480P (转码)</option>
          </template>
        </select>
      </div>
    </div>

    <!-- 视频播放器区域 -->
    <div class="flex-1 relative bg-black flex items-center justify-center"
      @mousemove="showControls" @click="togglePlayFromVideo"
      @touchstart="onTouchStart" @touchend="onTouchEnd"
      ref="videoContainer">
      <!-- 加载动画 -->
      <div v-if="loading" class="absolute inset-0 flex items-center justify-center z-10">
        <div class="animate-spin w-12 h-12 border-2 border-brand-500 border-t-transparent rounded-full" />
      </div>

      <!-- 转码等待提示 -->
      <div v-if="mediaInfo?.stream_mode === 'hls' && mediaInfo?.status === 'started' && !isPlaying"
        class="absolute inset-0 flex items-center justify-center z-10 bg-black/60">
        <div class="text-center">
          <div class="animate-spin w-12 h-12 border-2 border-amber-500 border-t-transparent rounded-full mx-auto mb-3" />
          <div class="text-gray-300 text-sm">正在转码，请稍候...</div>
          <div class="text-gray-500 text-xs mt-1">首次播放需要转码处理</div>
        </div>
      </div>

      <!-- video 元素 -->
      <video
        ref="videoEl"
        class="w-full h-full object-contain"
        :style="videoStyle"
        :src="directPlayUrl"
        @timeupdate="onTimeUpdate"
        @loadedmetadata="onMetaLoaded"
        @ended="onEnded"
        @waiting="loading = true"
        @canplay="loading = false"
        @play="isPlaying = true"
        @pause="isPlaying = false"
      ></video>

      <!-- 播放大按钮 -->
      <div v-if="!isPlaying && !loading" class="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
        <div class="w-20 h-20 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center">
          <svg class="w-10 h-10 text-white ml-1" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
        </div>
      </div>

      <!-- 快进/快退指示器 -->
      <Transition name="fade">
        <div v-if="seekIndicator.visible" class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-20 pointer-events-none">
          <div class="bg-black/70 backdrop-blur-sm rounded-xl px-6 py-4 flex flex-col items-center min-w-[120px]">
            <svg v-if="seekIndicator.direction > 0" class="w-8 h-8 text-white mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 5l7 7-7 7M5 5l7 7-7 7"/></svg>
            <svg v-else class="w-8 h-8 text-white mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 19l-7-7 7-7m8 14l-7-7 7-7"/></svg>
            <span class="text-white font-mono text-lg">{{ formatDuration(seekIndicator.targetTime) }}</span>
          </div>
        </div>
      </Transition>

      <!-- 自动播放下一集倒计时 -->
      <Transition name="fade">
        <div v-if="autoPlayCountdown > 0" class="absolute bottom-32 left-1/2 -translate-x-1/2 z-20">
          <div class="bg-black/80 backdrop-blur-sm rounded-xl px-6 py-3 flex items-center gap-3">
            <span class="text-gray-300 text-sm">下一集:</span>
            <span class="text-white text-sm font-medium">{{ nextEpisodeLabel }}</span>
            <div class="flex items-center gap-1.5 ml-2">
              <button @click="cancelAutoPlay" class="text-gray-400 hover:text-white text-xs px-2 py-1 rounded border border-gray-600">取消</button>
              <button @click="playNextNow" class="text-brand-400 text-xs px-2 py-1 rounded bg-brand-600/30 hover:bg-brand-600/50">立即播放</button>
            </div>
            <div class="w-8 h-8 relative ml-1">
              <svg class="w-8 h-8 -rotate-90"><circle cx="16" cy="16" r="14" fill="none" stroke="#374151" stroke-width="3"/><circle cx="16" cy="16" r="14" fill="none" stroke="#6366f1" stroke-width="3" :stroke-dasharray="88" :stroke-dashoffset="88 * (1 - autoPlayCountdown / 10)" stroke-linecap="round"/></svg>
              <span class="absolute inset-0 flex items-center justify-center text-xs text-white font-mono">{{ autoPlayCountdown }}</span>
            </div>
          </div>
        </div>
      </Transition>

      <!-- 底部控制栏（始终完全可见） -->
      <transition name="fade">
        <div
          :class="[
            'absolute bottom-0 left-0 right-0 z-20 bg-gradient-to-t from-black/90 via-black/60 to-transparent pt-16 pb-3 px-4 transition-opacity duration-300'
          ]"
          @mouseenter="controlsVisible = true"
          @mouseleave="onControlsMouseLeave"
        >
          <!-- 进度条 -->
          <div class="flex items-center gap-2 mb-2 group">
            <span class="text-gray-400 text-xs w-16 text-right tabular-nums">{{ formatDuration(currentTime) }}</span>
            <div class="flex-1 h-1.5 bg-gray-700 rounded-full cursor-pointer relative group-hover:h-2.5 transition-all"
              @click="seek" @mousedown="startDrag" ref="progressBar">
              <div class="absolute h-full bg-gray-600 rounded-full" :style="{ width: bufferedPercent + '%' }" />
              <div class="absolute h-full bg-brand-500 rounded-full" :style="{ width: progressPercent + '%' }">
                <div class="absolute right-0 top-1/2 -translate-y-1/2 w-3.5 h-3.5 bg-brand-400 rounded-full opacity-0 group-hover:opacity-100 transition-opacity shadow-lg" />
              </div>
            </div>
            <span class="text-gray-400 text-xs w-16 tabular-nums">{{ formatDuration(duration) }}</span>
          </div>

          <!-- 控制按钮行 -->
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <!-- 播放/暂停 -->
              <button @click.stop="togglePlay" class="text-white hover:text-brand-400 transition-colors p-1">
                <svg v-if="isPlaying" class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
                <svg v-else class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
              </button>

              <!-- 快退 10s -->
              <button @click="skipTime(-10)" class="text-gray-400 hover:text-white transition-colors p-1 hidden sm:block" title="快退 10 秒 (←)">
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12.066 11.2a1 1 0 000 1.6l5.334 4A1 1 0 0019 16V8a1 1 0 00-1.6-.8l-5.333 4zM4.066 11.2a1 1 0 000 1.6l5.334 4A1 1 0 0011 16V8a1 1 0 00-1.6-.8l-5.333 4z"/></svg>
                <span class="text-[9px] block text-center -mt-1">10</span>
              </button>

              <!-- 快进 10s -->
              <button @click="skipTime(10)" class="text-gray-400 hover:text-white transition-colors p-1 hidden sm:block" title="快进 10 秒 (→)">
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11.933 12.8a1 1 0 000-1.6L6.6 7.2A1 1 0 005 8v8a1 1 0 001.6.8l5.333-4zM19.933 12.8a1 1 0 000-1.6l-5.333-4A1 1 0 0013 8v8a1 1 0 001.6.8l5.333-4z"/></svg>
                <span class="text-[9px] block text-center -mt-1">10</span>
              </button>

              <!-- 音量 -->
              <div class="flex items-center gap-1 group/vol">
                <button @click.stop="toggleMute" class="text-gray-400 hover:text-white transition-colors p-1">
                  <svg v-if="muted || volume === 0" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2"/></svg>
                  <svg v-else class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"/></svg>
                </button>
                <div class="w-0 group-hover/vol:w-20 overflow-hidden transition-all duration-200">
                  <input type="range" min="0" max="1" step="0.01" :value="volume"
                    @input="setVolume(($event.target as HTMLInputElement).valueAsNumber)"
                    class="w-20 h-1 accent-brand-500 cursor-pointer" />
                </div>
              </div>

              <!-- 倍速 -->
              <div class="relative group/rate">
                <button @click.stop="cyclePlaybackRate" :class="['text-xs px-2 py-1 rounded transition-colors', playbackRate !== 1 ? 'text-brand-400' : 'text-gray-400 hover:text-white']" :title="`倍速 ${playbackRate}x`">
                  {{ playbackRate }}x
                </button>
                <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 bg-gray-900 rounded-lg shadow-xl opacity-0 invisible group-hover/rate:opacity-100 group-hover/rate:visible transition-all z-50 whitespace-nowrap">
                  <div class="py-1 px-1 grid grid-cols-3 gap-0.5">
                    <button v-for="r in [0.5, 0.75, 1, 1.25, 1.5, 2]" :key="r"
                      @click="setRate(r)"
                      :class="['px-3 py-1.5 rounded text-xs transition-colors', playbackRate === r ? 'bg-brand-600 text-white' : 'text-gray-300 hover:bg-gray-700']">
                      {{ r }}x
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div class="flex items-center gap-3">
              <!-- 画中画 PiP -->
              <button v-if="pipSupported" @click.stop="togglePiP"
                :class="['transition-colors p-1', isInPiP ? 'text-brand-400' : 'text-gray-400 hover:text-white']"
                :title="isInPiP ? '退出画中画' : '画中画'">
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h12a2 2 0 012 2v8a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm2 12a2 2 0 00-2 2v1a2 2 0 002 2h12a2 2 0 002-2v-1a2 2 0 00-2-2H6z"/></svg>
              </button>

              <!-- 外部播放直链 -->
              <button @click.stop="copyExternalUrl" :title="copySuccess ? '已复制' : '复制外部播放直链'"
                class="text-gray-400 hover:text-white transition-colors p-1">
                <svg v-if="!copySuccess" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
                <svg v-else class="w-5 h-5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
              </button>

              <!-- 外部播放器选择 -->
              <div class="relative group/ext" v-if="authStore.hasPermission('can_external_player')">
                <button @click.stop="showExternalPlayers = !showExternalPlayers" :title="'外部播放器'"
                  class="text-gray-400 hover:text-white transition-colors p-1">
                  <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                </button>
                <div v-if="showExternalPlayers"
                  class="absolute bottom-full right-0 mb-2 bg-gray-900 border border-gray-700 rounded-xl shadow-2xl p-2 min-w-[180px] z-50">
                  <div class="text-xs text-gray-400 px-3 py-1.5 font-medium">外部播放器</div>
                  <button v-for="(info, key) in externalPlayerList" :key="key"
                    @click.stop="openExternalPlayer(key)"
                    class="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800 hover:text-white rounded-lg transition-colors text-left">
                    <span class="text-base">{{ info.icon }}</span>
                    <span>{{ info.name }}</span>
                  </button>
                </div>
              </div>

              <!-- 字幕选择 -->
              <select v-if="subtitleTracks.length > 0" v-model="activeSubtitle"
                class="bg-transparent text-gray-400 text-xs cursor-pointer hover:text-white focus:outline-none">
                <option value="">关闭字幕</option>
                <option v-for="st in subtitleTracks" :key="st.label" :value="st.src">{{ st.label }}</option>
              </select>

              <!-- 全屏 -->
              <button @click.stop="toggleFullscreen" class="text-gray-400 hover:text-white transition-colors p-1">
                <svg v-if="!isFullscreen" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"/></svg>
                <svg v-else class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 9V4H4v5m11 0V4h5v5M9 15v5H4v-5m11 5v-5h5v5"/></svg>
              </button>
            </div>
          </div>
        </div>
      </transition>

      <!-- 快捷键提示浮层 (首次显示或按 ? 键) -->
      <Transition name="fade">
        <div v-if="showShortcutHelp" class="absolute inset-0 z-30 bg-black/85 backdrop-blur-sm flex items-center justify-center" @click="showShortcutHelp = false">
          <div class="bg-gray-900 border border-gray-700 rounded-2xl p-6 max-w-md w-full mx-4 shadow-2xl">
            <h3 class="text-white font-bold text-lg mb-4">键盘快捷键</h3>
            <div class="grid grid-cols-2 gap-2 text-sm">
              <div v-for="sc in shortcuts" :key="sc.key" class="flex items-center gap-2 text-gray-300">
                <kbd class="min-w-[48px] text-center px-1.5 py-0.5 rounded bg-gray-800 border border-gray-600 text-xs font-mono text-gray-200">{{ sc.key }}</kbd>
                <span>{{ sc.desc }}</span>
              </div>
            </div>
            <p class="text-gray-500 text-xs mt-4 text-center">按任意键或点击关闭</p>
          </div>
        </div>
      </Transition>
    </div>

    <!-- 剧集列表侧栏 -->
    <transition name="slide">
      <div v-if="showEpisodeList && episodeList.length > 0"
        class="shrink-0 w-72 bg-gray-900 border-t border-gray-800 overflow-y-auto">
        <div class="p-3 border-b border-gray-800 flex items-center justify-between">
          <span class="text-sm font-medium text-white">选集</span>
          <button @click="showEpisodeList = false" class="text-gray-500 hover:text-gray-300">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
        <div v-for="ep in episodeList" :key="ep.id"
          @click="switchEpisode(ep)"
          :class="[
            'flex items-center gap-3 px-3 py-2.5 cursor-pointer transition-colors text-sm',
            currentEpisode?.id === ep.id
              ? 'bg-brand-600/20 text-brand-400'
              : 'hover:bg-gray-800 text-gray-300',
          ]">
          <span class="text-gray-500 w-8 text-center text-xs">{{ ep.episode_number }}</span>
          <div class="flex-1 min-w-0">
            <div class="truncate">{{ ep.title || `第 ${ep.episode_number} 集` }}</div>
          </div>
          <svg v-if="currentEpisode?.id === ep.id" class="w-4 h-4 text-brand-500 shrink-0" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { playbackApi } from '@/api/playback'
import { usePlayerStore } from '@/stores/player'
import { useAuthStore } from '@/stores/auth'
import { useFormat } from '@/composables/useFormat'
import { useToast } from '@/composables/useToast'
import Hls from 'hls.js'

const route = useRoute()
const router = useRouter()
const playerStore = usePlayerStore()
const authStore = useAuthStore()
const { formatDuration } = useFormat()
const toast = useToast()

const videoEl = ref<HTMLVideoElement>()
const progressBar = ref<HTMLDivElement>()
const playerContainer = ref<HTMLDivElement>()
const videoContainer = ref<HTMLDivElement>()

// 状态
const loading = ref(true)
const isPlaying = ref(false)
const isFullscreen = ref(false)
const controlsVisible = ref(true)
const muted = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const volume = ref(1)
const quality = ref('auto')
const playbackRate = ref(1)
const activeSubtitle = ref('')
const showEpisodeList = ref(false)
const copySuccess = ref(false)
const transcodeEnabled = ref(false)
const showShortcutHelp = ref(false)
const autoPlayCountdown = ref(0)
const showExternalPlayers = ref(false)
const externalPlayerUrls = ref<Record<string, string>>({})

// PiP
const pipSupported = ref(false)
const isInPiP = ref(false)

// 触屏手势
let touchStartX = 0
let touchStartY = 0
let touchStartTime = 0
let lastTapTime = 0

// 快进快退指示器
const seekIndicator = reactive({
  visible: false,
  direction: 0,
  targetTime: 0,
})
let seekIndicatorTimer: ReturnType<typeof setTimeout> | null = null
let hideControlsTimer: ReturnType<typeof setTimeout> | null = null
let progressReportTimer: ReturnType<typeof setInterval> | null = null
let transcodePollTimer: ReturnType<typeof setInterval> | null = null
let isDragging = false
let autoPlayTimer: ReturnType<typeof setInterval> | null = null

// 播放信息
const mediaInfo = ref<any>(null)
const currentEpisode = ref<any>(null)
const episodeList = ref<any[]>([])
const subtitleTracks = ref<{ src: string; label: string; lang?: string }[]>([])
const directPlayUrl = ref('')

let hls: Hls | null = null

// 快捷键列表
const shortcuts = [
  { key: 'Space/K', desc: '播放/暂停' },
  { key: '← / →', desc: '快退/快进 10s' },
  { key: '↑ / ↓', desc: '音量 +/- 10%' },
  { key: 'J / L', desc: '快退/快进 10s' },
  { key: 'F', desc: '全屏切换' },
  { key: 'M', desc: '静音切换' },
  { key: 'E', desc: '剧集列表' },
  { key: 'P', desc: '画中画' },
  { key: '< / >', desc: '逐帧后退/前进' },
  { key: '0-9', desc: '跳转 0%-90%' },
  { key: '[ / ]', desc: '减速/加速 0.1x' },
  { key: '?', desc: '显示快捷键帮助' },
  { key: 'Esc', desc: '退出/返回' },
]

// 外部播放器列表
const externalPlayerList: Record<string, { name: string; icon: string }> = {
  potplayer: { name: 'PotPlayer', icon: '🎬' },
  vlc: { name: 'VLC', icon: '🔶' },
  iina: { name: 'IINA', icon: '🟣' },
  infuse: { name: 'Infuse', icon: '🍎' },
  nplayer: { name: 'NPlayer', icon: '🔵' },
  mpv: { name: 'MPV', icon: '⬛' },
  mpchc: { name: 'MPC-HC', icon: '🔳' },
  mxplayer: { name: 'MX Player', icon: '🟠' },
}

// 计算属性
const progressPercent = computed(() => {
  if (!duration.value) return 0
  return (currentTime.value / duration.value) * 100
})

const bufferedPercent = computed(() => {
  const video = videoEl.value
  if (!video || !video.buffered.length || !duration.value) return 0
  return (video.buffered.end(video.buffered.length - 1) / duration.value) * 100
})

const nextEpisodeLabel = computed(() => {
  if (!currentEpisode.value || episodeList.value.length === 0) return ''
  const idx = episodeList.value.findIndex(ep => ep.id === currentEpisode.value!.id)
  const nextEp = episodeList.value[idx + 1]
  if (!nextEp) return ''
  return nextEp.title || `第 ${nextEp.episode_number} 集`
})

// 播放器容器样式：全屏时移除宽度限制
const playerContainerStyle = computed(() => {
  if (isFullscreen.value) {
    return { minHeight: '100vh', width: '100%', maxWidth: '100%', margin: '0' }
  }
  return { maxWidth: '1200px', margin: '0 auto', minHeight: '100vh' }
})

// 视频元素样式：全屏时撑满，非全屏时限制最大高度
const videoStyle = computed(() => {
  if (isFullscreen.value) {
    return { maxHeight: '100vh' }
  }
  return { aspectRatio: '16/9', maxHeight: 'calc(100vh - 160px)' }
})

// 初始化
onMounted(async () => {
  await loadPlayInfo()
  // 检测 PiP 支持
  pipSupported.value = !!document.pictureInPictureEnabled ||
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    !!(videoEl.value as any)?.webkitSupportsPresentationMode &&
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    typeof (videoEl.value as any)?.webkitSetPresentationMode === 'function'

  document.addEventListener('keydown', onKeydown)
  document.addEventListener('fullscreenchange', onFullscreenChange)
})

onUnmounted(() => {
  cleanup()
  document.removeEventListener('keydown', onKeydown)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
})

async function loadPlayInfo() {
  const mediaId = Number(route.params.id)
  const episodeId = route.query.episode ? Number(route.query.episode) : undefined

  try {
    loading.value = true
    const { data } = await playbackApi.getPlayInfo(mediaId, episodeId ? { episode_id: episodeId } : undefined)
    mediaInfo.value = data
    transcodeEnabled.value = data.transcode_enabled ?? false

    if (data.stream_mode === 'direct' && data.direct_url) {
      // 浏览器 <video src> 不能携带 Authorization header，需把 token 附在 URL 里
      const token = authStore.token || localStorage.getItem('access_token') || ''
      const separator = data.direct_url.includes('?') ? '&' : '?'
      directPlayUrl.value = token ? `${data.direct_url}${separator}token=${encodeURIComponent(token)}` : data.direct_url
      // 如果有播放兼容性警告，提示用户
      if (data.playback_warning) {
        toast.addToast('warning', data.playback_warning, 10000)
      }
      await nextTick()
    } else if (data.hls_playlist_url) {
      directPlayUrl.value = ''
      await nextTick()
      // HLS 播放：在 URL 中附带 token，供后端认证
      const token = authStore.token || localStorage.getItem('access_token') || ''
      const hlsUrl = token
        ? `${data.hls_playlist_url}${data.hls_playlist_url.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}`
        : data.hls_playlist_url
      initHls(hlsUrl)

      // 如果转码刚启动，轮询状态，完成后重新加载
      if (data.status === 'started') {
        startTranscodePolling(mediaId)
      }
    }

    if (data.subtitles?.length) {
      subtitleTracks.value = data.subtitles.map((s: any) => ({
        src: s.url,
        label: s.language_name || s.language || '字幕',
        lang: s.language,
      }))
    }

    if (data.episodes?.length) {
      episodeList.value = data.episodes
      currentEpisode.value = data.episodes.find((ep: any) =>
        episodeId ? ep.id === episodeId : ep.episode_number === 1
      ) || data.episodes[0]
    }

    if (playerStore.volume) {
      volume.value = playerStore.volume
    }
  } catch (err) {
    console.error('加载播放信息失败:', err)
    router.back()
  }
}

function initHls(playlistUrl: string) {
  if (!videoEl.value) return

  if (Hls.isSupported()) {
    const token = authStore.token || localStorage.getItem('access_token') || ''
    hls = new Hls({
      enableWorker: true,
      lowLatencyMode: true,
      startLevel: quality.value === 'auto' ? -1 : undefined,
    })

    // 使用 pLoader 自定义加载器自动附加 token
    const origPLoader = hls.config.pLoader || Hls.DefaultConfig.pLoader
    const origXhrLoader = Hls.DefaultConfig.xhrLoader

    hls.config.loader = origPLoader || origXhrLoader

    // 监听请求，在加载前自动为 URL 附加 token
    hls.on(Hls.Events.FRAG_LOADING, (_event, data) => {
      const frag = data.frag
      if (token && !frag.url.includes('token=')) {
        const sep = frag.url.includes('?') ? '&' : '?'
        frag.url = `${frag.url}${sep}token=${encodeURIComponent(token)}`
      }
    })

    hls.on(Hls.Events.MANIFEST_LOADING, (_event, data) => {
      if (token && !data.url.includes('token=')) {
        const sep = data.url.includes('?') ? '&' : '?'
        data.url = `${data.url}${sep}token=${encodeURIComponent(token)}`
      }
    })

    hls.on(Hls.Events.LEVEL_LOADING, (_event, data) => {
      if (token && data.url && !data.url.includes('token=')) {
        const sep = data.url.includes('?') ? '&' : '?'
        data.url = `${data.url}${sep}token=${encodeURIComponent(token)}`
      }
    })

    hls.loadSource(playlistUrl)
    hls.attachMedia(videoEl.value)

    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      loading.value = false
      applyQuality()
      videoEl.value?.play()
    })

    hls.on(Hls.Events.ERROR, (_event, data) => {
      if (data.fatal) {
        switch (data.type) {
          case Hls.ErrorTypes.NETWORK_ERROR:
            console.error('HLS 网络错误，尝试恢复...', data)
            toast.warning('网络错误，正在重连...')
            // 如果是加载错误（如 playlist 404），延迟重试
            setTimeout(() => {
              if (hls) hls.startLoad()
            }, 2000)
            break
          case Hls.ErrorTypes.MEDIA_ERROR:
            console.error('HLS 媒体错误，尝试恢复...')
            hls?.recoverMediaError()
            break
          default:
            console.error('HLS 致命错误')
            toast.error('播放出错，请稍后重试')
            cleanup()
            break
        }
      }
    })
  } else if (videoEl.value.canPlayType('application/vnd.apple.mpegurl')) {
    videoEl.value.src = playlistUrl
  }
}

// ── 转码轮询 ──
function startTranscodePolling(mediaId: number) {
  stopTranscodePolling()
  transcodePollTimer = setInterval(async () => {
    try {
      const { data } = await playbackApi.getTranscodeStatus(`${mediaId}_${quality.value}`)
      if (data.status === 'completed') {
        stopTranscodePolling()
        mediaInfo.value.status = 'completed'
        // 转码完成，重新初始化 HLS
        if (hls) { hls.destroy(); hls = null }
        const token = authStore.token || localStorage.getItem('access_token') || ''
        const hlsUrl = `/api/playback/hls/${mediaId}_${quality.value}/playlist.m3u8?token=${encodeURIComponent(token)}`
        initHls(hlsUrl)
      } else if (data.status === 'failed') {
        stopTranscodePolling()
        toast.error(`转码失败: ${data.error || '未知错误'}`)
      }
    } catch (e) {
      console.error('Transcode status check failed:', e)
    }
  }, 3000)
}

function stopTranscodePolling() {
  if (transcodePollTimer) {
    clearInterval(transcodePollTimer)
    transcodePollTimer = null
  }
}

function applyQuality() {
  if (!hls) return
  if (quality.value === 'auto') {
    hls.currentLevel = -1
  } else {
    const levelMap: Record<string, number> = { '480p': 0, '720p': 1, '1080p': 2, '4k': 3, 'original': -1 }
    const target = levelMap[quality.value]
    if (target === -1) {
      hls.currentLevel = hls.levels.length - 1
    } else if (target < hls.levels.length) {
      hls.currentLevel = target
    }
  }
}

function changeQuality() {
  playerStore.quality = quality.value
  if (hls) {
    applyQuality()
  } else {
    loadPlayInfo()
  }
}

// ── 播放控制 ──
function togglePlay() {
  const video = videoEl.value
  if (!video) return
  if (video.paused) video.play()
  else video.pause()
}

function togglePlayFromVideo(e: MouseEvent | TouchEvent) {
  const target = e.target as HTMLElement
  if (target.closest('button, select, input')) return
  togglePlay()
}

function toggleMute() {
  if (!videoEl.value) return
  muted.value = !muted.value
  videoEl.value.muted = muted.value
}

function setVolume(val: number) {
  if (!videoEl.value) return
  volume.value = val
  playerStore.volume = val
  videoEl.value.volume = val
  if (val > 0) muted.value = false
}

function cyclePlaybackRate() {
  const rates = [0.5, 0.75, 1, 1.25, 1.5, 2]
  const idx = rates.indexOf(playbackRate.value)
  const nextIdx = (idx + 1) % rates.length
  setRate(rates[nextIdx])
}

function setRate(r: number) {
  playbackRate.value = r
  if (videoEl.value) videoEl.value.playbackRate = r
}

function skipTime(delta: number) {
  if (!videoEl.value || !duration.value) return
  const target = Math.max(0, Math.min(duration.value, videoEl.value.currentTime + delta))
  videoEl.value.currentTime = target
  // 显示指示器
  seekIndicator.direction = delta > 0 ? 1 : -1
  seekIndicator.targetTime = target
  seekIndicator.visible = true
  if (seekIndicatorTimer) clearTimeout(seekIndicatorTimer)
  seekIndicatorTimer = setTimeout(() => { seekIndicator.visible = false }, 600)
  showControls()
}

function seek(e: MouseEvent) {
  if (!progressBar.value || !videoEl.value) return
  const rect = progressBar.value.getBoundingClientRect()
  const percent = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  videoEl.value.currentTime = percent * duration.value
}

function startDrag(e: MouseEvent) {
  isDragging = true
  seek(e)
  const onMove = (ev: MouseEvent) => { if (isDragging) seek(ev) }
  const onUp = () => {
    isDragging = false
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

function toggleFullscreen() {
  const el = playerContainer.value
  if (!el) return
  if (!document.fullscreenElement) {
    el.requestFullscreen().catch(() => {
      // fallback: fullscreen entire page
      document.documentElement.requestFullscreen().catch(() => {})
    })
  } else {
    document.exitFullscreen()
  }
}

function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
}

// ── 画中画 ──
async function togglePiP() {
  if (!videoEl.value) return
  try {
    if (document.pictureInPictureElement) {
      await document.exitPictureInPicture()
      isInPiP.value = false
    } else {
      await videoEl.value.requestPictureInPicture()
      isInPiP.value = true
    }
  } catch (e) {
    // 尝试 webkit 前缀
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const v = videoEl.value as any
      if (v.webkitSetPresentationMode && v.webkitPresentationMode === 'inline') {
        v.webkitSetPresentationMode('picture-in-picture')
        isInPiP.value = true
      } else if (v.webkitSetPresentationMode) {
        v.webkitSetPresentationMode('inline')
        isInPiP.value = false
      }
    } catch (e2) {
      toast.warning('画中画不可用或被浏览器拒绝')
    }
  }
}

// 监听 PiP 事件
if (typeof window !== 'undefined') {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ;(window as any).addEventListener?.('enterpictureinpicture', () => { isInPiP.value = true })
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ;(window as any).addEventListener?.('leavepictureinpicture', () => { isInPiP.value = false })
}

// ── 时间更新 ──
function onTimeUpdate() {
  if (!videoEl.value || isDragging) return
  currentTime.value = videoEl.value.currentTime
}

function onMetaLoaded() {
  if (!videoEl.value) return
  duration.value = videoEl.value.duration
  if (mediaInfo.value?.watch_progress) {
    const progress = mediaInfo.value.watch_progress
    if (progress > 5 && progress < duration.value - 10) {
      videoEl.value.currentTime = progress
    }
  }
  videoEl.value.volume = volume.value
  // 视频元数据加载完成后自动播放（非 HLS 转码模式）
  if (!hls) {
    videoEl.value.play().catch(() => {
      // 自动播放被阻止，等待用户交互
      console.log('Auto-play blocked, waiting for user interaction')
    })
  }
  startProgressReport()
}

function onEnded() {
  isPlaying.value = false
  // 自动播放下一集
  if (currentEpisode.value && episodeList.value.length > 0) {
    const idx = episodeList.value.findIndex(ep => ep.id === currentEpisode.value.id)
    if (idx < episodeList.value.length - 1) {
      startAutoPlayCountdown(episodeList.value[idx + 1])
      return
    }
  }
  // 电影结束或最后一集
  goBack()
}

function startAutoPlayCountdown(nextEp: any) {
  autoPlayCountdown.value = 10
  autoPlayTimer = setInterval(() => {
    autoPlayCountdown.value--
    if (autoPlayCountdown.value <= 0) {
      cancelAutoPlay()
      switchEpisode(nextEp)
    }
  }, 1000)
}

function cancelAutoPlay() {
  if (autoPlayTimer) {
    clearInterval(autoPlayTimer)
    autoPlayTimer = null
  }
  autoPlayCountdown.value = 0
}

function playNextNow() {
  cancelAutoPlay()
  const idx = episodeList.value.findIndex(ep => ep.id === currentEpisode.value?.id)
  if (idx >= 0 && idx < episodeList.value.length - 1) {
    switchEpisode(episodeList.value[idx + 1])
  }
}

function switchEpisode(ep: any) {
  cancelAutoPlay()
  stopProgressReport()
  stopTranscodePolling()
  // 重置播放器状态
  if (videoEl.value) {
    videoEl.value.pause()
    videoEl.value.currentTime = 0
  }
  currentTime.value = 0
  duration.value = 0
  isPlaying.value = false
  currentEpisode.value = ep
  loadPlayInfo()
}

// ── 进度上报 ──
function startProgressReport() {
  stopProgressReport()
  progressReportTimer = setInterval(async () => {
    if (!videoEl.value || videoEl.value.paused || !mediaInfo.value?.id) return
    try {
      await playbackApi.reportProgress(
        mediaInfo.value.id,
        Math.floor(videoEl.value.currentTime),
        Math.floor(videoEl.value.duration),
        currentEpisode.value?.id,
      )
    } catch (_) {}
  }, 15000)
}

function stopProgressReport() {
  if (progressReportTimer) {
    clearInterval(progressReportTimer)
    progressReportTimer = null
  }
}

// ── 控制栏自动隐藏（已禁用，改为始终显示）──
function showControls() {
  // 保持 controlsVisible 为 true，不自动隐藏
}

function onControlsMouseLeave() {
  // 鼠标离开控制栏时也保持显示
  controlsVisible.value = true
}

// ── 键盘快捷键（增强版）──
function onKeydown(e: KeyboardEvent) {
  // 输入框内不拦截
  if ((e.target as HTMLElement).tagName === 'INPUT' || (e.target as HTMLElement).tagName === 'SELECT') return
  if (!videoEl.value) return

  switch (e.key) {
    case ' ':
    case 'k':
      e.preventDefault()
      togglePlay()
      break
    case 'f':
      e.preventDefault()
      toggleFullscreen()
      break
    case 'm':
      e.preventDefault()
      toggleMute()
      break
    case 'p':
      e.preventDefault()
      togglePiP()
      break
    case 'ArrowLeft':
      e.preventDefault()
      skipTime(-10)
      break
    case 'ArrowRight':
      e.preventDefault()
      skipTime(10)
      break
    case 'ArrowUp':
      e.preventDefault()
      setVolume(Math.min(1, volume.value + 0.1))
      break
    case 'ArrowDown':
      e.preventDefault()
      setVolume(Math.max(0, volume.value - 0.1))
      break
    case 'j':
      e.preventDefault()
      skipTime(-10)
      break
    case 'l':
      e.preventDefault()
      skipTime(10)
      break
    case ',':
      e.preventDefault()
      setRate(Math.max(0.25, playbackRate.value - 0.1))
      break
    case '.':
      e.preventDefault()
      setRate(Math.min(4, playbackRate.value + 0.1))
      break
    case '<': // Shift+,
      e.preventDefault()
      if (videoEl.value) videoEl.value.currentTime -= 1 / 30
      break
    case '>': // Shift+.
      e.preventDefault()
      if (videoEl.value) videoEl.value.currentTime += 1 / 30
      break
    case 'Escape':
      if (showShortcutHelp.value) { showShortcutHelp.value = false; return }
      if (isFullscreen.value) toggleFullscreen()
      else goBack()
      break
    case 'e':
      if (episodeList.value.length > 0) showEpisodeList.value = !showEpisodeList.value
      break
    case '?':
      e.preventDefault()
      showShortcutHelp.value = !showShortcutHelp.value
      return // 不要触发 showControls
    default:
      // 数字键 0-9 跳转到对应百分比位置
      if (/^[0-9]$/.test(e.key)) {
        e.preventDefault()
        const pct = Number(e.key) / 10
        if (duration.value) videoEl.value.currentTime = pct * duration.value
        break
      }
      return // 未匹配的按键不触发 showControls
  }
  showControls()
}

// ── 触屏手势 ──
function onTouchStart(e: TouchEvent) {
  if (e.touches.length !== 1) return
  touchStartX = e.touches[0].clientX
  touchStartY = e.touches[0].clientY
  touchStartTime = Date.now()
}

function onTouchEnd(e: TouchEvent) {
  if (e.changedTouches.length !== 1) return
  const dx = e.changedTouches[0].clientX - touchStartX
  const dy = e.changedTouches[0].clientY - touchStartY
  const dt = Date.now() - touchStartTime
  const containerW = videoContainer.value?.offsetWidth || window.innerWidth

  // 双击检测
  if (dt < 300 && Math.abs(dx) < 30 && Math.abs(dy) < 30) {
    if (Date.now() - lastTapTime < 350) {
      togglePlay()
      lastTapTime = 0
      return
    }
    lastTapTime = Date.now()
    return
  }

  // 左右滑动快进快退
  if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5 && dt < 500) {
    const seconds = Math.round(Math.abs(dx) / containerW * duration.value * 0.1) * 10
    skipTime(dx > 0 ? Math.max(5, seconds) : Math.min(-5, -seconds))
  }
}

// ── 返回 ──
function goBack() {
  if (videoEl.value && mediaInfo.value?.id && !videoEl.value.paused) {
    playbackApi.reportProgress(
      mediaInfo.value.id,
      Math.floor(videoEl.value.currentTime),
      Math.floor(videoEl.value.duration),
      currentEpisode.value?.id,
    ).catch(() => {})
  }
  cancelAutoPlay()
  stopProgressReport()
  cleanup()
  router.back()
}

async function openExternalPlayer(playerKey: string) {
  if (!mediaInfo.value?.id) return
  try {
    const episodeId = currentEpisode.value?.id ? Number(currentEpisode.value.id) : undefined
    const { data } = await playbackApi.getExternalPlayers(mediaInfo.value.id, episodeId)
    const playerUrl = data.players?.[playerKey]
    if (playerUrl) {
      // 使用 window.open 或 location.href 打开协议链接
      window.open(playerUrl, '_blank')
      toast.success(`已唤起 ${externalPlayerList[playerKey]?.name || playerKey}`)
    } else {
      toast.error('不支持该播放器')
    }
    showExternalPlayers.value = false
  } catch (e) {
    console.error('打开外部播放器失败:', e)
    toast.error('打开外部播放器失败')
  }
  showExternalPlayers.value = false
}

async function copyExternalUrl() {
  if (!mediaInfo.value?.id) return
  try {
    copySuccess.value = false
    const episodeId = currentEpisode.value?.id ? Number(currentEpisode.value.id) : undefined
    const { data } = await playbackApi.getExternalUrl(mediaInfo.value.id, episodeId)
    const base = window.location.origin
    const fullUrl = base + data.url
    await navigator.clipboard.writeText(fullUrl)
    copySuccess.value = true
    setTimeout(() => { copySuccess.value = false }, 2000)
    toast.success('外部播放直链已复制')
  } catch (e) {
    console.error('复制外部直链失败:', e)
    toast.error('复制直链失败')
  }
}

function cleanup() {
  if (hls) { hls.destroy(); hls = null }
  stopProgressReport()
  stopTranscodePolling()
  cancelAutoPlay()
}
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.slide-enter-active, .slide-leave-active { transition: transform 0.3s ease, opacity 0.3s ease; }
.slide-enter-from { transform: translateY(100%); opacity: 0; }
.slide-leave-to { transform: translateY(100%); opacity: 0; }

/* 全屏时播放器容器撑满屏幕 */
:deep(:fullscreen) {
  max-width: 100% !important;
  width: 100% !important;
  margin: 0 !important;
  background: #000;
}
:deep(:-webkit-full-screen) {
  max-width: 100% !important;
  width: 100% !important;
  margin: 0 !important;
  background: #000;
}
:deep(:-moz-full-screen) {
  max-width: 100% !important;
  width: 100% !important;
  margin: 0 !important;
  background: #000;
}

/* Range 样式 */
input[type="range"] {
  -webkit-appearance: none;
  appearance: none;
  background: transparent;
}
input[type="range"]::-webkit-slider-runnable-track {
  height: 4px; background: #374151; border-radius: 2px;
}
input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none; appearance: none;
  width: 12px; height: 12px; background: #6366f1;
  border-radius: 50%; margin-top: -4px; cursor: pointer;
}
input[type="range"]::-moz-range-track {
  height: 4px; background: #374151; border-radius: 2px;
}
input[type="range"]::-moz-range-thumb {
  width: 12px; height: 12px; background: #6366f1;
  border-radius: 50%; border: none; cursor: pointer;
}
select option { background: #1f2937; color: #d1d5db; }
kbd {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
</style>
