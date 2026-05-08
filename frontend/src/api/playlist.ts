import api from './client'

export interface Playlist {
  id: number
  user_id: number
  name: string
  description: string | null
  cover_url: string | null
  is_public: boolean
  item_count: number
  total_duration: number
  created_at: string
  updated_at: string
}

export interface PlaylistDetail extends Playlist {
  items: PlaylistItem[]
}

export interface PlaylistItem {
  id: number
  playlist_id: number
  media_item_id: number
  position: number
  added_at: string
  media_title: string | null
  media_poster: string | null
  media_type: string | null
  media_duration: number | null
}

export interface CreatePlaylistData {
  name: string
  description?: string
  is_public?: boolean
}

export interface UpdatePlaylistData {
  name?: string
  description?: string
  cover_url?: string
  is_public?: boolean
}

export const playlistApi = {
  // 获取播放列表
  getPlaylists: () => api.get<{ data: Playlist[] }>('/api/playlists'),

  // 获取播放列表详情
  getPlaylist: (id: number) =>
    api.get<{ data: PlaylistDetail }>(`/api/playlists/${id}`),

  // 创建播放列表
  createPlaylist: (data: CreatePlaylistData) =>
    api.post<{ data: Playlist }>('/api/playlists', data),

  // 更新播放列表
  updatePlaylist: (id: number, data: UpdatePlaylistData) =>
    api.put<{ data: Playlist }>(`/api/playlists/${id}`, data),

  // 删除播放列表
  deletePlaylist: (id: number) =>
    api.delete(`/api/playlists/${id}`),

  // 添加项目到播放列表
  addItem: (playlistId: number, mediaId: number, position?: number) =>
    api.post<{ data: PlaylistItem }>(`/api/playlists/${playlistId}/items`, {
      media_id: mediaId,
      position
    }),

  // 从播放列表移除项目
  removeItem: (playlistId: number, itemId: number) =>
    api.delete(`/api/playlists/${playlistId}/items/${itemId}`),

  // 重新排序
  reorderItems: (playlistId: number, itemIds: number[]) =>
    api.put(`/api/playlists/${playlistId}/reorder`, { item_ids: itemIds }),
}
