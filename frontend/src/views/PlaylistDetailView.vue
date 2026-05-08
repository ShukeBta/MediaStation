<template>
  <div class="playlist-detail-view">
    <!-- 返回按钮 -->
    <button class="back-btn" @click="$router.back()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M19 12H5M12 19l-7-7 7-7"/>
      </svg>
      返回
    </button>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <div class="loading-spinner"></div>
      <p>加载中...</p>
    </div>

    <!-- 播放列表详情 -->
    <template v-else-if="playlist">
      <!-- 头部 -->
      <div class="detail-header">
        <div class="playlist-cover" v-if="playlist.cover_url">
          <img :src="playlist.cover_url" :alt="playlist.name" />
        </div>
        <div class="cover-placeholder" v-else>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"/>
          </svg>
        </div>

        <div class="header-info">
          <div class="header-badges">
            <span v-if="playlist.is_public" class="badge badge-public">公开</span>
            <span v-else class="badge badge-private">私人</span>
          </div>
          <h1 class="playlist-title">{{ playlist.name }}</h1>
          <p v-if="playlist.description" class="playlist-desc">{{ playlist.description }}</p>
          <div class="playlist-stats">
            <span>{{ playlist.item_count }} 项</span>
            <span v-if="playlist.total_duration > 0">
              {{ formatDuration(playlist.total_duration) }}
            </span>
          </div>
        </div>

        <div class="header-actions">
          <button class="btn btn-primary" @click="playAll" :disabled="items.length === 0">
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z"/>
            </svg>
            播放全部
          </button>
          <button class="btn btn-secondary" @click="openEditModal">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
            </svg>
            编辑
          </button>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="items.length === 0" class="empty-state">
        <div class="empty-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/>
          </svg>
        </div>
        <h3>播放列表为空</h3>
        <p>添加媒体到播放列表开始观看</p>
      </div>

      <!-- 项目列表 -->
      <div v-else class="items-list">
        <div
          v-for="(item, index) in items"
          :key="item.id"
          class="item-row"
          @click="playItem(item)"
        >
          <div class="item-index">{{ index + 1 }}</div>
          <div class="item-poster">
            <img
              v-if="item.media_poster"
              :src="item.media_poster"
              :alt="item.media_title || ''"
            />
            <div v-else class="poster-placeholder">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/>
              </svg>
            </div>
          </div>
          <div class="item-info">
            <h4 class="item-title">{{ item.media_title || '未知标题' }}</h4>
            <div class="item-meta">
              <span class="media-type">{{ getMediaTypeLabel(item.media_type) }}</span>
              <span v-if="item.media_duration" class="duration">
                {{ formatDuration(item.media_duration) }}
              </span>
            </div>
          </div>
          <div class="item-actions" @click.stop>
            <button class="action-btn" @click="playItem(item)">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M8 5v14l11-7z"/>
              </svg>
            </button>
            <button class="action-btn" @click="removeItem(item)">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </template>

    <!-- 编辑 Modal -->
    <Teleport to="body">
      <div v-if="showEditModal" class="modal-overlay" @click.self="showEditModal = false">
        <div class="modal">
          <div class="modal-header">
            <h2>编辑播放列表</h2>
            <button class="modal-close" @click="showEditModal = false">&times;</button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label for="edit-name">名称 *</label>
              <input
                id="edit-name"
                v-model="editForm.name"
                type="text"
                class="form-input"
                placeholder="输入播放列表名称"
              />
            </div>
            <div class="form-group">
              <label for="edit-desc">描述</label>
              <textarea
                id="edit-desc"
                v-model="editForm.description"
                class="form-input form-textarea"
                placeholder="添加描述"
                rows="3"
              ></textarea>
            </div>
            <div class="form-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="editForm.is_public" class="form-checkbox" />
                <span>设为公开</span>
              </label>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showEditModal = false">取消</button>
            <button class="btn btn-primary" @click="saveEdit" :disabled="submitting">
              {{ submitting ? '保存中...' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Toast -->
    <Teleport to="body">
      <Transition name="toast">
        <div v-if="toast.show" class="toast" :class="`toast-${toast.type}`">
          {{ toast.message }}
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { playlistApi, type PlaylistDetail, type PlaylistItem } from '@/api/playlist'

const router = useRouter()
const route = useRoute()

const playlistId = computed(() => Number(route.params.id))

// 状态
const loading = ref(true)
const playlist = ref<PlaylistDetail | null>(null)
const showEditModal = ref(false)
const submitting = ref(false)

// 编辑表单
const editForm = reactive({
  name: '',
  description: '',
  is_public: false,
})

// Toast
const toast = reactive({
  show: false,
  type: 'success',
  message: '',
})

function showToast(type: 'success' | 'error', message: string) {
  toast.type = type
  toast.message = message
  toast.show = true
  setTimeout(() => { toast.show = false }, 3000)
}

const items = computed(() => playlist.value?.items || [])

// 加载播放列表
async function loadPlaylist() {
  try {
    loading.value = true
    const res = await playlistApi.getPlaylist(playlistId.value)
    playlist.value = res.data.data
  } catch (e: any) {
    showToast('error', e.message || '加载失败')
    router.back()
  } finally {
    loading.value = false
  }
}

// 播放
function playItem(item: PlaylistItem) {
  router.push(`/player/${item.media_item_id}`)
}

function playAll() {
  if (items.value.length > 0) {
    playItem(items.value[0])
  }
}

// 编辑
function openEditModal() {
  if (!playlist.value) return
  editForm.name = playlist.value.name
  editForm.description = playlist.value.description || ''
  editForm.is_public = playlist.value.is_public
  showEditModal.value = true
}

async function saveEdit() {
  if (!playlist.value || !editForm.name.trim()) return
  try {
    submitting.value = true
    await playlistApi.updatePlaylist(playlist.value.id, {
      name: editForm.name,
      description: editForm.description || undefined,
      is_public: editForm.is_public,
    })
    showToast('success', '保存成功')
    showEditModal.value = false
    loadPlaylist()
  } catch (e: any) {
    showToast('error', e.message || '保存失败')
  } finally {
    submitting.value = false
  }
}

// 移除项目
async function removeItem(item: PlaylistItem) {
  if (!playlist.value) return
  try {
    await playlistApi.removeItem(playlist.value.id, item.id)
    showToast('success', '已移除')
    loadPlaylist()
  } catch (e: any) {
    showToast('error', e.message || '移除失败')
  }
}

// 格式化
function formatDuration(seconds: number): string {
  if (!seconds) return ''
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h === 0) return `${m}分钟`
  return `${h}小时${m > 0 ? m + '分钟' : ''}`
}

function getMediaTypeLabel(type: string | null): string {
  const map: Record<string, string> = {
    movie: '电影',
    tv: '电视剧',
    anime: '动漫',
    variety: '综艺',
  }
  return type ? (map[type] || type) : '未知'
}

onMounted(() => {
  loadPlaylist()
})
</script>

<style scoped>
.playlist-detail-view {
  padding: 24px;
  max-width: 1000px;
  margin: 0 auto;
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 14px;
  cursor: pointer;
  margin-bottom: 24px;
  transition: all 0.2s;
}

.back-btn:hover {
  background: var(--bg-tertiary);
}

.back-btn svg {
  width: 18px;
  height: 18px;
}

/* Header */
.detail-header {
  display: flex;
  gap: 24px;
  margin-bottom: 32px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--border-color);
}

.playlist-cover,
.cover-placeholder {
  width: 200px;
  height: 200px;
  border-radius: 12px;
  flex-shrink: 0;
  overflow: hidden;
}

.playlist-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cover-placeholder {
  background: var(--bg-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  opacity: 0.5;
}

.cover-placeholder svg {
  width: 64px;
  height: 64px;
}

.header-info {
  flex: 1;
  min-width: 0;
}

.header-badges {
  margin-bottom: 8px;
}

.badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.badge-public {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

.badge-private {
  background: rgba(107, 114, 128, 0.15);
  color: #6b7280;
}

.playlist-title {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px 0;
}

.playlist-desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0 0 16px 0;
  line-height: 1.5;
}

.playlist-stats {
  display: flex;
  gap: 16px;
  font-size: 14px;
  color: var(--text-secondary);
}

.header-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex-shrink: 0;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
  white-space: nowrap;
}

.btn svg {
  width: 18px;
  height: 18px;
}

.btn-primary {
  background: var(--accent-color, #3b82f6);
  color: white;
}

.btn-primary:hover {
  opacity: 0.9;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

.btn-secondary:hover {
  background: var(--bg-tertiary);
}

/* Loading */
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border-color);
  border-top-color: var(--accent-color, #3b82f6);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Empty */
.empty-state {
  text-align: center;
  padding: 60px;
}

.empty-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 16px;
  color: var(--text-secondary);
  opacity: 0.5;
}

.empty-state h3 {
  font-size: 18px;
  color: var(--text-primary);
  margin: 0 0 8px 0;
}

.empty-state p {
  color: var(--text-secondary);
  margin: 0;
}

/* Items List */
.items-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.item-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  background: var(--bg-secondary);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.item-row:hover {
  background: var(--bg-tertiary);
}

.item-index {
  width: 32px;
  text-align: center;
  font-size: 14px;
  color: var(--text-secondary);
  font-weight: 500;
}

.item-poster {
  width: 80px;
  height: 45px;
  border-radius: 6px;
  overflow: hidden;
  flex-shrink: 0;
}

.item-poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.poster-placeholder {
  width: 100%;
  height: 100%;
  background: var(--bg-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  opacity: 0.5;
}

.poster-placeholder svg {
  width: 24px;
  height: 24px;
}

.item-info {
  flex: 1;
  min-width: 0;
}

.item-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0 0 4px 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-secondary);
}

.media-type {
  background: var(--bg-tertiary);
  padding: 1px 6px;
  border-radius: 3px;
}

.item-actions {
  display: flex;
  gap: 8px;
  opacity: 0;
  transition: opacity 0.2s;
}

.item-row:hover .item-actions {
  opacity: 1;
}

.action-btn {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.action-btn:hover {
  background: var(--accent-color, #3b82f6);
  color: white;
  border-color: transparent;
}

.action-btn svg {
  width: 16px;
  height: 16px;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal {
  background: var(--bg-secondary);
  border-radius: 12px;
  width: 100%;
  max-width: 480px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-color);
}

.modal-header h2 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

.modal-close {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: none;
  border: none;
  font-size: 24px;
  color: var(--text-secondary);
  cursor: pointer;
}

.modal-body {
  padding: 24px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid var(--border-color);
}

.form-group {
  margin-bottom: 20px;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 8px;
}

.form-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-size: 14px;
  background: var(--bg-primary);
  color: var(--text-primary);
}

.form-input:focus {
  outline: none;
  border-color: var(--accent-color, #3b82f6);
}

.form-textarea {
  resize: vertical;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.form-checkbox {
  width: 18px;
  height: 18px;
}

/* Toast */
.toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  padding: 12px 24px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  z-index: 2000;
}

.toast-success {
  background: #22c55e;
  color: white;
}

.toast-error {
  background: #ef4444;
  color: white;
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(20px);
}

/* Responsive */
@media (max-width: 768px) {
  .detail-header {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .playlist-cover,
  .cover-placeholder {
    width: 160px;
    height: 160px;
  }

  .header-badges {
    justify-content: center;
  }

  .playlist-stats {
    justify-content: center;
  }

  .header-actions {
    flex-direction: row;
    width: 100%;
  }

  .header-actions .btn {
    flex: 1;
  }
}

/* Dark mode */
@media (prefers-color-scheme: dark) {
  :root {
    --bg-primary: #1a1a2e;
    --bg-secondary: #16213e;
    --bg-tertiary: #0f3460;
    --text-primary: #eaeaea;
    --text-secondary: #a0a0a0;
    --border-color: rgba(255, 255, 255, 0.1);
    --accent-color: #3b82f6;
  }
}

@media (prefers-color-scheme: light) {
  :root {
    --bg-primary: #ffffff;
    --bg-secondary: #f9fafb;
    --bg-tertiary: #f3f4f6;
    --text-primary: #111827;
    --text-secondary: #6b7280;
    --border-color: #e5e7eb;
    --accent-color: #3b82f6;
  }
}
</style>
