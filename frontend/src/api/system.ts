import api from './client'

export const systemApi = {
  getInfo: () => api.get('/api/system/info'),
  getStatus: () => api.get('/api/system/status'),
  getScheduledJobs: () => api.get('/api/system/scheduler'),
  triggerJob: (jobId: string) => api.post(`/api/system/scheduler/${jobId}/trigger`),
  getConfig: () => api.get('/api/system/config'),
  updateConfig: (data: Record<string, any>) => api.patch('/api/system/config', data),
}

// 统计数据 API
export const statsApi = {
  getOverview: () => api.get('/api/stats/overview'),
  getTrend: (params?: { period?: string }) => api.get('/api/stats/trend', { params }),
  getTopContent: (params?: { period?: string; limit?: number }) =>
    api.get('/api/stats/top-content', { params }),
  getTopUsers: (params?: { period?: string; limit?: number }) =>
    api.get('/api/stats/top-users', { params }),
  getLibraries: () => api.get('/api/stats/libraries'),
  getMonitor: () => api.get('/api/stats/monitor'),
  getUserStats: (userId: number) => api.get(`/api/stats/user/${userId}`),
  recordPlay: (data: { item_id: number; position: number; duration: number }) =>
    api.post('/api/stats/play', data),
}

// 观看历史
export const watchHistoryApi = {
  getList: (params?: any) => api.get('/api/watch-history', { params }),
  getStats: () => api.get('/api/watch-history/stats'),
  getContinueWatching: (limit = 10) =>
    api.get('/api/watch-history/continue', { params: { limit } }),
  deleteItem: (id: number) => api.delete(`/api/watch-history/${id}`),
  clearAll: (mediaItemId?: number) =>
    api.delete('/api/watch-history', { params: mediaItemId ? { media_item_id: mediaItemId } : {} }),
}
