<template>
  <div class="p-4 md:p-6 max-w-6xl mx-auto space-y-6">
    <div class="flex items-center gap-3">
      <div class="w-10 h-10 rounded-lg bg-violet-500/10 flex items-center justify-center">
        <svg class="w-5 h-5 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
        </svg>
      </div>
      <div>
        <h1 class="text-2xl font-bold">DLNA 投屏</h1>
        <p class="text-sm mt-0.5" style="color: var(--text-muted)">发现 DLNA 设备，将媒体投射到电视或音箱</p>
      </div>
    </div>

    <!-- 设备发现 -->
    <div class="card p-6 space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">发现设备</h2>
        <button @click="discoverDevices" :disabled="discovering"
          class="btn-secondary text-sm px-4 py-2 disabled:opacity-50 flex items-center gap-2">
          <span v-if="discovering" class="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
          <svg v-else class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.966 8.966 0 0020 8a8.966 8.966 0 00-5.314-2.514M15 11a5 5 0 11-10 0 5 5 0 0110 0z"/>
          </svg>
          刷新设备
        </button>
      </div>

      <!-- 加载中 -->
      <div v-if="discovering" class="space-y-3">
        <div v-for="i in 3" :key="i" class="animate-pulse flex items-center gap-4 p-4">
          <div class="w-12 h-12 rounded-lg bg-[var(--bg-input)]" />
          <div class="flex-1 space-y-2">
            <div class="h-4 bg-[var(--bg-input)] rounded w-48" />
            <div class="h-3 bg-[var(--bg-input)] rounded w-64" />
          </div>
        </div>
      </div>

      <!-- 设备列表 -->
      <div v-else-if="devices.length > 0" class="space-y-3">
        <div v-for="device in devices" :key="device.uuid"
          class="p-4 rounded-lg border transition-all duration-300"
          :class="selectedDevice === device.uuid ? 'border-brand-500 bg-brand-500/5' : 'border-[var(--border-primary)] hover:border-[var(--border-secondary)]'">
          <div class="flex items-center gap-4">
            <!-- 设备图标 -->
            <div class="w-12 h-12 rounded-lg flex items-center justify-center"
              :class="getDeviceIconBg(device.type)">
              <svg class="w-6 h-6" :class="getDeviceIconColor(device.type)" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path v-if="device.type === 'MEDIA_RENDERER'" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
                <path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"/>
              </svg>
            </div>
            <!-- 设备信息 -->
            <div class="flex-1 min-w-0">
              <div class="font-medium">{{ device.friendly_name || device.name }}</div>
              <div class="text-xs mt-0.5" style="color: var(--text-muted)">
                {{ device.manufacturer || '未知品牌' }} · {{ device.model || '未知型号' }}
              </div>
              <div class="flex items-center gap-2 mt-1">
                <span class="text-[10px] px-1.5 py-0.5 rounded" :class="device.status === 'online' ? 'bg-green-500/15 text-green-400' : 'bg-gray-500/15 text-gray-400'">
                  {{ device.status === 'online' ? '在线' : '离线' }}
                </span>
                <span class="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-400">
                  {{ device.type === 'MEDIA_RENDERER' ? '渲染器' : device.type === 'MEDIA_SERVER' ? '服务器' : device.type }}
                </span>
              </div>
            </div>
            <!-- 选择按钮 -->
            <button @click="selectDevice(device)"
              :class="['text-sm px-3 py-1.5 rounded-lg transition-colors',
                selectedDevice === device.uuid
                  ? 'bg-brand-500 text-white'
                  : 'btn-secondary']">
              {{ selectedDevice === device.uuid ? '已选择' : '选择' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else class="text-center py-8" style="color: var(--text-muted)">
        <svg class="w-16 h-16 mx-auto mb-3 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
        </svg>
        <div class="text-sm">未发现 DLNA 设备</div>
        <div class="text-xs mt-1">请确保设备和本服务器在同一局域网内</div>
        <button @click="discoverDevices" class="mt-3 btn-secondary text-sm px-4 py-2">
          重新搜索
        </button>
      </div>
    </div>

    <!-- 投屏控制 -->
    <div v-if="selectedDevice" class="card p-6 space-y-5">
      <h2 class="text-lg font-semibold">投屏控制</h2>

      <!-- 媒体 URL 输入 -->
      <div>
        <label class="block text-sm font-medium mb-2" style="color: var(--text-secondary)">媒体 URL</label>
        <div class="flex gap-2">
          <input v-model="castUrl" type="url" placeholder="输入媒体 URL 或选择媒体库中的视频..."
            class="flex-1 px-3 py-2 text-sm rounded-lg border bg-[var(--bg-input)] border-[var(--border-primary)] focus:border-brand-500 focus:outline-none"
            style="color: var(--text-primary)" />
          <button @click="showMediaSelector = !showMediaSelector" class="btn-secondary text-sm px-3 py-2">
            选择媒体
          </button>
        </div>
        <input v-model="castTitle" type="text" placeholder="标题（可选）"
          class="mt-2 w-full px-3 py-2 text-sm rounded-lg border bg-[var(--bg-input)] border-[var(--border-primary)] focus:border-brand-500 focus:outline-none"
          style="color: var(--text-primary)" />
      </div>

      <!-- 媒体选择器 -->
      <div v-if="showMediaSelector" class="border rounded-lg overflow-hidden" style="border-color: var(--border-primary)">
        <div class="p-3 border-b" style="border-color: var(--border-primary)">
          <input v-model="mediaSearch" placeholder="搜索媒体..."
            class="w-full px-3 py-1.5 text-sm rounded border bg-[var(--bg-input)] border-[var(--border-primary)]"
            style="color: var(--text-primary)" />
        </div>
        <div class="max-h-60 overflow-y-auto">
          <div v-for="item in filteredMediaList" :key="item.id"
            @click="selectMedia(item)"
            class="p-3 cursor-pointer hover:bg-[var(--bg-hover)] transition-colors flex items-center gap-3">
            <div class="w-10 h-14 rounded overflow-hidden bg-[var(--bg-input)] shrink-0">
              <img v-if="item.poster_url" :src="item.poster_url" class="w-full h-full object-cover" />
            </div>
            <div class="flex-1 min-w-0">
              <div class="text-sm font-medium truncate">{{ item.title }}</div>
              <div class="text-xs" style="color: var(--text-muted)">{{ item.media_type }} · {{ item.year || '—' }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 控制按钮 -->
      <div class="flex gap-3">
        <button @click="castMedia" :disabled="!castUrl.trim() || casting"
          class="btn-primary text-sm px-6 py-2.5 disabled:opacity-50 flex items-center gap-2">
          <span v-if="casting" class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          <svg v-else class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M8 5v14l11-7z"/>
          </svg>
          {{ casting ? '投屏中...' : '开始投屏' }}
        </button>

        <button @click="playDevice" :disabled="!isCasting" class="btn-secondary text-sm px-4 py-2.5 disabled:opacity-50">
          <svg class="w-4 h-4 inline mr-1" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
          播放
        </button>

        <button @click="pauseDevice" :disabled="!isCasting" class="btn-secondary text-sm px-4 py-2.5 disabled:opacity-50">
          <svg class="w-4 h-4 inline mr-1" fill="currentColor" viewBox="0 0 24 24"><path d="M6 4h4v16H6zM14 4h4v16h-4z"/></svg>
          暂停
        </button>

        <button @click="stopDevice" :disabled="!isCasting" class="btn-danger text-sm px-4 py-2.5 disabled:opacity-50">
          <svg class="w-4 h-4 inline mr-1" fill="currentColor" viewBox="0 0 24 24"><path d="M6 6h12v12H6z"/></svg>
          停止
        </button>
      </div>

      <!-- 状态显示 -->
      <div v-if="deviceStatus" class="p-4 rounded-lg" style="background: var(--bg-secondary)">
        <div class="text-sm font-medium mb-2">设备状态</div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div>
            <div class="text-xs" style="color: var(--text-faint)">状态</div>
            <div :class="deviceStatus.playing ? 'text-green-400' : 'text-yellow-400'">
              {{ deviceStatus.playing ? '播放中' : '已暂停' }}
            </div>
          </div>
          <div>
            <div class="text-xs" style="color: var(--text-faint)">进度</div>
            <div style="color: var(--text-primary)">{{ formatTime(deviceStatus.position) }} / {{ formatTime(deviceStatus.duration) }}</div>
          </div>
          <div>
            <div class="text-xs" style="color: var(--text-faint)">音量</div>
            <div style="color: var(--text-primary)">{{ deviceStatus.volume || 0 }}%</div>
          </div>
          <div>
            <div class="text-xs" style="color: var(--text-faint)">媒体</div>
            <div class="truncate" style="color: var(--text-primary)">{{ deviceStatus.title || '—' }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { dlnaApi } from '@/api/dlna'
import { mediaApi } from '@/api/media'
import { playbackApi } from '@/api/playback'
import { useToast } from '@/composables/useToast'

const toast = useToast()

// ── 设备状态 ──
const devices = ref<any[]>([])
const discovering = ref(false)
const selectedDevice = ref('')
const deviceStatus = ref<any>(null)
const isCasting = ref(false)

// ── 投屏状态 ──
const castUrl = ref('')
const castTitle = ref('')
const casting = ref(false)

// ── 媒体选择 ──
const showMediaSelector = ref(false)
const mediaSearch = ref('')
const mediaList = ref<any[]>([])

// 发现设备
async function discoverDevices(force = true) {
  discovering.value = true
  try {
    const { data } = await dlnaApi.discover(force)
    devices.value = data || []
    if (devices.value.length === 0) {
      toast.info('未发现 DLNA 设备')
    } else {
      toast.success(`发现 ${devices.value.length} 个设备`)
    }
  } catch (e: any) {
    toast.error(`搜索失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    discovering.value = false
  }
}

// 选择设备
function selectDevice(device: any) {
  selectedDevice.value = device.uuid
  deviceStatus.value = null
  isCasting.value = false
  // 自动查询状态
  queryDeviceStatus()
}

// 获取设备图标样式
function getDeviceIconBg(type: string) {
  if (type === 'MEDIA_RENDERER') return 'bg-violet-500/10'
  if (type === 'MEDIA_SERVER') return 'bg-blue-500/10'
  return 'bg-gray-500/10'
}
function getDeviceIconColor(type: string) {
  if (type === 'MEDIA_RENDERER') return 'text-violet-400'
  if (type === 'MEDIA_SERVER') return 'text-blue-400'
  return 'text-gray-400'
}

// 查询设备状态
let statusTimer: ReturnType<typeof setInterval> | null = null
async function queryDeviceStatus() {
  if (!selectedDevice.value) return
  try {
    const { data } = await dlnaApi.status(selectedDevice.value)
    deviceStatus.value = data
    isCasting.value = data.playing || data.paused
  } catch {
    // 忽略错误
  }
}

// 投屏
async function castMedia() {
  if (!selectedDevice.value || !castUrl.value.trim()) return
  casting.value = true
  try {
    await dlnaApi.cast({
      device_uuid: selectedDevice.value,
      media_url: castUrl.value.trim(),
      title: castTitle.value || undefined,
    })
    isCasting.value = true
    toast.success('投屏已开始')
    queryDeviceStatus()
  } catch (e: any) {
    toast.error(`投屏失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    casting.value = false
  }
}

// 播放控制
async function playDevice() {
  if (!selectedDevice.value) return
  try {
    await dlnaApi.play(selectedDevice.value)
    toast.success('已继续播放')
    queryDeviceStatus()
  } catch (e: any) {
    toast.error(`播放失败: ${e.response?.data?.detail || e.message}`)
  }
}
async function pauseDevice() {
  if (!selectedDevice.value) return
  try {
    await dlnaApi.pause(selectedDevice.value)
    toast.success('已暂停')
    queryDeviceStatus()
  } catch (e: any) {
    toast.error(`暂停失败: ${e.response?.data?.detail || e.message}`)
  }
}
async function stopDevice() {
  if (!selectedDevice.value) return
  try {
    await dlnaApi.stop(selectedDevice.value)
    isCasting.value = false
    deviceStatus.value = null
    toast.success('已停止投屏')
  } catch (e: any) {
    toast.error(`停止失败: ${e.response?.data?.detail || e.message}`)
  }
}

// 媒体选择
async function selectMedia(item: any) {
  // 如果是内网地址的媒体，需要获取带token的external-url供DLNA设备访问
  try {
    const { data } = await playbackApi.getExternalUrl(item.id)
    castUrl.value = data.url
    castTitle.value = item.title
    showMediaSelector.value = false
    toast.info(`已选择: ${item.title}`)
  } catch {
    // fallback: 使用本地地址
    castUrl.value = `${window.location.origin}/api/playback/${item.id}/stream`
    castTitle.value = item.title
    showMediaSelector.value = false
    toast.info(`已选择: ${item.title} (本地模式)`)
  }
}

const filteredMediaList = computed(() => {
  if (!mediaSearch.value) return mediaList.value
  const q = mediaSearch.value.toLowerCase()
  return mediaList.value.filter(m => m.title?.toLowerCase().includes(q))
})

async function loadMediaList() {
  try {
    const { data } = await mediaApi.getItems({ page_size: 50 })
    mediaList.value = data.items || []
  } catch {}
}

// 时间格式化
function formatTime(seconds: number): string {
  if (!seconds) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

// 定时查询状态
onMounted(() => {
  discoverDevices()
  loadMediaList()
  statusTimer = setInterval(() => {
    if (selectedDevice.value && isCasting.value) {
      queryDeviceStatus()
    }
  }, 3000)
})

onUnmounted(() => {
  if (statusTimer) clearInterval(statusTimer)
})
</script>
