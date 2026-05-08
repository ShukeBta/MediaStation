import api from './client'

// ── STRM 配置类型 ──────────────────────────────────────────────────

export interface StrmConfig {
  enabled: boolean
  allowed_protocols: string[]
  max_file_size: number
}

export interface MediaStrmInfo {
  media_id: number
  title: string
  strm_url: string | null
  has_strm: boolean
}

export interface StrmConfigUpdate {
  enabled?: boolean
  allowed_protocols?: string[]
  max_file_size?: number
}

export interface MediaStrmUpdate {
  strm_url: string
}

// ── STRM API ───────────────────────────────────────────────────────

export const strmApi = {
  // 获取 STRM 配置
  getConfig: () =>
    api.get<{ data: StrmConfig }>('/api/admin/strm/config'),

  // 更新 STRM 配置
  updateConfig: (data: StrmConfigUpdate) =>
    api.put<{ data: StrmConfig & { message: string } }>('/api/admin/strm/config', data),

  // 获取媒体的 STRM URL
  getMediaStrm: (mediaId: number) =>
    api.get<{ data: MediaStrmInfo }>(`/api/admin/strm/media/${mediaId}`),

  // 设置媒体的 STRM URL
  setMediaStrm: (mediaId: number, strmUrl: string) =>
    api.put<{ data: MediaStrmInfo & { message: string } }>(`/api/admin/strm/media/${mediaId}`, {
      strm_url: strmUrl,
    }),

  // 清除媒体的 STRM URL
  clearMediaStrm: (mediaId: number) =>
    api.delete<{ data: { message: string; media_id: number } }>(`/api/admin/strm/media/${mediaId}`),
}
