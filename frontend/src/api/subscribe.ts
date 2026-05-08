import api from './client'

export const subscribeApi = {
  // 站点
  getSites: () => api.get('/api/sites'),
  createSite: (data: any) => api.post('/api/sites', data),
  updateSite: (id: number, data: any) => api.put(`/api/sites/${id}`, data),
  deleteSite: (id: number) => api.delete(`/api/sites/${id}`),
  testSite: (id: number) => api.post(`/api/sites/${id}/test`),
  refreshSiteUserdata: (id: number) => api.get(`/api/sites/${id}/userdata`),
  getSiteResource: (id: number, params?: any) => api.get(`/api/sites/${id}/resource`, { params }),

  // 资源搜索
  searchSites: (keyword: string, siteIds?: string) =>
    api.get('/api/search/sites', { params: { keyword, site_ids: siteIds } }),

  // 订阅
  getSubscriptions: (status?: string) =>
    api.get('/api/subscriptions', { params: { status } }),
  createSubscription: (data: any) => api.post('/api/subscriptions', data),
  updateSubscription: (id: number, data: any) => api.put(`/api/subscriptions/${id}`, data),
  deleteSubscription: (id: number) => api.delete(`/api/subscriptions/${id}`),
  triggerSearch: (id: number) => api.post(`/api/subscriptions/${id}/search`),

  // 通知
  getNotifyChannels: () => api.get('/api/notify/channels'),
  createNotifyChannel: (data: any) => api.post('/api/notify/channels', data),
  updateNotifyChannel: (id: number, data: any) => api.put(`/api/notify/channels/${id}`, data),
  deleteNotifyChannel: (id: number) => api.delete(`/api/notify/channels/${id}`),
  testNotifyChannel: (id: number) => api.post(`/api/notify/channels/${id}/test`),
}
