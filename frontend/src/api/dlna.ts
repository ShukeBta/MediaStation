import api from './client'

export const dlnaApi = {
  // 设备发现
  discover: (force?: boolean) => api.get('/api/dlna/devices', { params: { force } }),

  // 投屏
  cast: (data: { device_uuid: string; media_url: string; title?: string }) =>
    api.post('/api/dlna/cast', data),

  // 播放控制
  play: (uuid: string) => api.post(`/api/dlna/${uuid}/play`),
  pause: (uuid: string) => api.post(`/api/dlna/${uuid}/pause`),
  stop: (uuid: string) => api.post(`/api/dlna/${uuid}/stop`),
  status: (uuid: string) => api.get(`/api/dlna/${uuid}/status`),
}
