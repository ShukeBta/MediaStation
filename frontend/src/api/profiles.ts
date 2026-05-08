import api from './client'

// ── Profile 类型 ──────────────────────────────────────────────────

export interface Profile {
  id: number
  name: string
  description: string | null
  is_active: boolean
  content_filter: {
    max_rating: string | null
    allowed_tags: string[]
    blocked_tags: string[]
  }
  playback_limits: {
    max_quality: string | null
    allowed_media_types: string[]
  }
  created_at: string
  updated_at: string
}

export interface ProfileCreate {
  name: string
  description?: string
  content_filter?: {
    max_rating?: string | null
    allowed_tags?: string[]
    blocked_tags?: string[]
  }
  playback_limits?: {
    max_quality?: string | null
    allowed_media_types?: string[]
  }
}

export interface ProfileWatchLog {
  id: number
  media_item_id: number
  media_title: string
  media_type: string
  started_at: string
  ended_at: string | null
  progress: number
  duration: number
}

export interface ProfileUsage {
  total_plays: number
  total_duration: number
  most_watched_genre: string | null
  last_active: string | null
  plays_by_day: Array<{ date: string; count: number }>
}

// ── Profiles API ─────────────────────────────────────────────────

export const profilesApi = {
  // 列出所有 Profile
  list: () =>
    api.get<{ data: Profile[] }>('/api/profiles'),

  // 创建 Profile
  create: (data: ProfileCreate) =>
    api.post<{ data: Profile }>('/api/profiles', data),

  // 获取 Profile 详情
  get: (id: number) =>
    api.get<{ data: Profile }>(`/api/profiles/${id}`),

  // 更新 Profile
  update: (id: number, data: Partial<ProfileCreate>) =>
    api.put<{ data: Profile }>(`/api/profiles/${id}`, data),

  // 删除 Profile
  delete: (id: number) =>
    api.delete(`/api/profiles/${id}`),

  // 切换活跃 Profile
  switchProfile: (id: number) =>
    api.post<{ data: { message: string } }>(`/api/profiles/${id}/switch`),

  // 获取观看日志
  getWatchLogs: (id: number, params?: { limit?: number; offset?: number }) =>
    api.get<{ data: ProfileWatchLog[] | { items: ProfileWatchLog[]; total: number } }>(
      `/api/profiles/${id}/watch-logs`,
      { params },
    ),

  // 获取使用统计
  getUsage: (id: number) =>
    api.get<{ data: ProfileUsage }>(`/api/profiles/${id}/usage`),
}
