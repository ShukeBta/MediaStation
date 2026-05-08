<template>
  <div class="playlist-view">
    <!-- 头部 -->
    <div class="page-header">
      <div class="header-content">
        <h1 class="page-title">我的播放列表</h1>
        <p class="page-subtitle">管理和组织你的媒体收藏</p>
      </div>
      <button class="btn btn-primary" @click="showCreateModal = true">
        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 5v14M5 12h14"/>
        </svg>
        创建播放列表
      </button>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <div class="loading-spinner"></div>
      <p>加载中...</p>
    </div>

    <!-- 空状态 -->
    <div v-else-if="playlists.length === 0" class="empty-state">
      <div class="empty-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"/>
        </svg>
      </div>
      <h3>还没有播放列表</h3>
      <p>创建一个播放列表来组织和收藏你喜欢的媒体</p>
      <button class="btn btn-primary" @click="showCreateModal = true">
        创建第一个播放列表
      </button>
    </div>

    <!-- 播放列表网格 -->
    <div v-else class="playlist-grid">
      <div
        v-for="playlist in playlists"
        :key="playlist.id"
        class="playlist-card"
        @click="goToDetail(playlist.id)"
      >
        <!-- 封面 -->
        <div class="playlist-cover">
          <img
            v-if="playlist.cover_url"
            :src="playlist.cover_url"
            :alt="playlist.name"
            class="cover-image"
          />
          <div v-else class="cover-placeholder">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"/>
            </svg>
          </div>
          <div class="cover-overlay">
            <span class="item-count">{{ playlist.item_count }} 项</span>
          </div>
        </div>

        <!-- 信息 -->
        <div class="playlist-info">
          <h3 class="playlist-name">{{ playlist.name }}</h3>
          <p v-if="playlist.description" class="playlist-desc">{{ playlist.description }}</p>
          <div class="playlist-meta">
            <span v-if="playlist.is_public" class="badge badge-public">公开</span>
            <span v-else class="badge badge-private">私人</span>
            <span class="duration" v-if="playlist.total_duration > 0">
              {{ formatDuration(playlist.total_duration) }}
            </span>
          </div>
        </div>

        <!-- 操作菜单 -->
        <div class="playlist-actions" @click.stop>
          <button class="action-btn" @click="openEditModal(playlist)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
            </svg>
          </button>
          <button class="action-btn action-btn-danger" @click="confirmDelete(playlist)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- 创建/编辑 Modal -->
    <Teleport to="body">
      <div v-if="showCreateModal || editingPlaylist" class="modal-overlay" @click.self="closeModal">
        <div class="modal">
          <div class="modal-header">
            <h2>{{ editingPlaylist ? '编辑播放列表' : '创建播放列表' }}</h2>
            <button class="modal-close" @click="closeModal">&times;</button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label for="name">名称 *</label>
              <input
                id="name"
                v-model="formData.name"
                type="text"
                class="form-input"
                placeholder="输入播放列表名称"
                maxlength="100"
              />
            </div>
            <div class="form-group">
              <label for="description">描述</label>
              <textarea
                id="description"
                v-model="formData.description"
                class="form-input form-textarea"
                placeholder="添加描述（可选）"
                maxlength="500"
                rows="3"
              ></textarea>
            </div>
            <div class="form-group">
              <label class="checkbox-label">
                <input
                  type="checkbox"
                  v-model="formData.is_public"
                  class="form-checkbox"
                />
                <span>设为公开</span>
              </label>
              <p class="form-hint">公开的播放列表可以被其他用户浏览</p>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="closeModal">取消</button>
            <button
              class="btn btn-primary"
              @click="editingPlaylist ? updatePlaylist() : createPlaylist()"
              :disabled="!formData.name || submitting"
            >
              {{ submitting ? '保存中...' : (editingPlaylist ? '保存' : '创建') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 删除确认 Modal -->
    <Teleport to="body">
      <div v-if="deletingPlaylist" class="modal-overlay" @click.self="deletingPlaylist = null">
        <div class="modal modal-sm">
          <div class="modal-header">
            <h2>确认删除</h2>
            <button class="modal-close" @click="deletingPlaylist = null">&times;</button>
          </div>
          <div class="modal-body">
            <p>确定要删除播放列表 <strong>{{ deletingPlaylist.name }}</strong> 吗？</p>
            <p class="text-muted">此操作不可恢复。</p>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="deletingPlaylist = null">取消</button>
            <button class="btn btn-danger" @click="deletePlaylist" :disabled="deleting">
              {{ deleting ? '删除中...' : '删除' }}
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
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { playlistApi, type Playlist, type CreatePlaylistData } from '@/api/playlist'

const router = useRouter()

// 状态
const loading = ref(true)
const playlists = ref<Playlist[]>([])
const showCreateModal = ref(false)
const editingPlaylist = ref<Playlist | null>(null)
const deletingPlaylist = ref<Playlist | null>(null)
const submitting = ref(false)
const deleting = ref(false)

// 表单数据
const formData = reactive<CreatePlaylistData & { description?: string }>({
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

// 加载播放列表
async function loadPlaylists() {
  try {
    loading.value = true
    const res = await playlistApi.getPlaylists()
    playlists.value = res.data.data || []
  } catch (e: any) {
    showToast('error', e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

// 创建播放列表
async function createPlaylist() {
  if (!formData.name.trim()) return
  try {
    submitting.value = true
    await playlistApi.createPlaylist({
      name: formData.name,
      description: formData.description || undefined,
      is_public: formData.is_public,
    })
    showToast('success', '播放列表创建成功')
    closeModal()
    loadPlaylists()
  } catch (e: any) {
    showToast('error', e.message || '创建失败')
  } finally {
    submitting.value = false
  }
}

// 编辑播放列表
function openEditModal(playlist: Playlist) {
  editingPlaylist.value = playlist
  formData.name = playlist.name
  formData.description = playlist.description || ''
  formData.is_public = playlist.is_public
}

// 更新播放列表
async function updatePlaylist() {
  if (!editingPlaylist.value || !formData.name.trim()) return
  try {
    submitting.value = true
    await playlistApi.updatePlaylist(editingPlaylist.value.id, {
      name: formData.name,
      description: formData.description || undefined,
      is_public: formData.is_public,
    })
    showToast('success', '播放列表更新成功')
    closeModal()
    loadPlaylists()
  } catch (e: any) {
    showToast('error', e.message || '更新失败')
  } finally {
    submitting.value = false
  }
}

// 删除播放列表
async function deletePlaylist() {
  if (!deletingPlaylist.value) return
  try {
    deleting.value = true
    await playlistApi.deletePlaylist(deletingPlaylist.value.id)
    showToast('success', '播放列表已删除')
    deletingPlaylist.value = null
    loadPlaylists()
  } catch (e: any) {
    showToast('error', e.message || '删除失败')
  } finally {
    deleting.value = false
  }
}

// 确认删除
function confirmDelete(playlist: Playlist) {
  deletingPlaylist.value = playlist
}

// 关闭 Modal
function closeModal() {
  showCreateModal.value = false
  editingPlaylist.value = null
  formData.name = ''
  formData.description = ''
  formData.is_public = false
}

// 跳转详情
function goToDetail(id: number) {
  router.push(`/playlists/${id}`)
}

// 格式化时长
function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}秒`
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  if (hours === 0) return `${mins}分钟`
  return `${hours}小时${mins > 0 ? mins + '分钟' : ''}`
}

onMounted(() => {
  loadPlaylists()
})
</script>

<style scoped>
.playlist-view {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 32px;
}

.page-title {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 4px 0;
}

.page-subtitle {
  color: var(--text-secondary);
  margin: 0;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-primary {
  background: var(--accent-color, #3b82f6);
  color: white;
}

.btn-primary:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

.btn-secondary {
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

.btn-danger {
  background: #ef4444;
  color: white;
}

.btn-icon {
  width: 18px;
  height: 18px;
}

/* Loading */
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: var(--text-secondary);
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

/* Empty State */
.empty-state {
  text-align: center;
  padding: 80px 20px;
}

.empty-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto 20px;
  color: var(--text-secondary);
  opacity: 0.5;
}

.empty-icon svg {
  width: 100%;
  height: 100%;
}

.empty-state h3 {
  font-size: 20px;
  color: var(--text-primary);
  margin: 0 0 8px 0;
}

.empty-state p {
  color: var(--text-secondary);
  margin: 0 0 24px 0;
}

/* Grid */
.playlist-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 24px;
}

.playlist-card {
  background: var(--bg-secondary);
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.playlist-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.15);
}

.playlist-cover {
  position: relative;
  aspect-ratio: 16/9;
  background: var(--bg-tertiary);
}

.cover-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cover-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  opacity: 0.5;
}

.cover-placeholder svg {
  width: 48px;
  height: 48px;
}

.cover-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 8px 12px;
  background: linear-gradient(transparent, rgba(0,0,0,0.8));
  color: white;
  font-size: 13px;
}

.item-count {
  font-weight: 500;
}

.playlist-info {
  padding: 16px;
}

.playlist-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 6px 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.playlist-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 12px 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.playlist-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.badge {
  padding: 2px 8px;
  border-radius: 4px;
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

.duration {
  color: var(--text-secondary);
}

.playlist-actions {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  gap: 8px;
  opacity: 0;
  transition: opacity 0.2s;
}

.playlist-card:hover .playlist-actions {
  opacity: 1;
}

.action-btn {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.6);
  color: white;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.action-btn:hover {
  background: rgba(0, 0, 0, 0.8);
}

.action-btn-danger:hover {
  background: rgba(239, 68, 68, 0.9);
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
  max-height: 90vh;
  overflow: auto;
}

.modal-sm {
  max-width: 400px;
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
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-close:hover {
  background: var(--bg-tertiary);
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
  color: var(--text-primary);
}

.form-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-size: 14px;
  background: var(--bg-primary);
  color: var(--text-primary);
  transition: border-color 0.2s;
}

.form-input:focus {
  outline: none;
  border-color: var(--accent-color, #3b82f6);
}

.form-textarea {
  resize: vertical;
  min-height: 80px;
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
  cursor: pointer;
}

.form-hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 6px 0 0 28px;
}

.text-muted {
  color: var(--text-secondary);
  font-size: 14px;
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
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
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
