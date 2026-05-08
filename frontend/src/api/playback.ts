import api from './client'

export const playbackApi = {
  getPlayInfo: (id: number, params?: any) =>
    api.get(`/api/playback/${id}/info`, { params }),
  reportProgress: (id: number, progress: number, duration: number, episodeId?: number) =>
    api.post(`/api/playback/${id}/progress`, null, {
      params: { progress, duration, episode_id: episodeId },
    }),
  /** 获取外部播放器直链 URL */
  getExternalUrl: (id: number, episodeId?: number) =>
    api.get<{ url: string; title: string; filename: string; expires_in: number }>(
      `/api/playback/${id}/external-url`,
      { params: episodeId ? { episode_id: episodeId } : undefined },
    ),
  /** 获取各外部播放器的协议直链（PotPlayer, VLC, IINA 等） */
  getExternalPlayers: (id: number, episodeId?: number) =>
    api.get<{
      direct_url: string
      file_name: string
      players: Record<string, string>
    }>(
      `/api/playback/${id}/external-players`,
      { params: episodeId ? { episode_id: episodeId } : undefined },
    ),
  /** 查询转码任务状态 */
  getTranscodeStatus: (jobId: string) =>
    api.get(`/api/playback/transcode/${jobId}/status`),
}
