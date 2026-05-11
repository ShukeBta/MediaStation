import api from './client'

export const mediaApi = {
  // 媒体库
  getLibraries: () => api.get('/api/libraries'),
  createLibrary: (data: any) => api.post('/api/libraries', data),
  updateLibrary: (id: number, data: any) => api.put(`/api/libraries/${id}`, data),
  deleteLibrary: (id: number) => api.delete(`/api/libraries/${id}`),
  scanLibrary: (id: number) => api.post(`/api/libraries/${id}/scan`),

  // 媒体条目
  getItems: (params?: any) => api.get('/api/media', { params }),
  getRecent: (limit?: number) => api.get('/api/media/recent', { params: { limit } }),
  getDetail: (id: number) => api.get(`/api/media/${id}`),
  updateItem: (id: number, data: any) => api.put(`/api/media/${id}`, data),
  deleteItem: (id: number) => api.delete(`/api/media/${id}`),
  getStats: () => api.get('/api/media/stats'),

  // 刮削
  scrapeItem: (id: number, data?: any) => api.post(`/api/media/${id}/scrape`, data || {}),
  aiScrape: (id: number, data: any) => api.post(`/api/media/${id}/ai-scrape`, data),
  searchTmdb: (query: string, type?: string) =>
    api.get('/api/search/tmdb', { params: { query, media_type: type || 'movie' } }),

  // Adult Provider 测试
  scrapeTest: (code: string) => api.post('/api/media/scrape/test', { code }),

  // 整理
  organize: (sourcePath?: string) => api.post('/api/media/organize', null, { params: sourcePath ? { source_path: sourcePath } : {} }),

  // 收藏
  addFavorite: (id: number) => api.post(`/api/media/${id}/favorite`),
  removeFavorite: (id: number) => api.delete(`/api/media/${id}/favorite`),
  checkFavorite: (id: number) => api.get(`/api/media/${id}/favorite/status`),
  getFavorites: (params?: any) => api.get('/api/favorites', { params }),

  // 发现/探索
  getDiscoverSections: () => api.get('/api/discover/sections'),
  getDiscoverFeed: (sectionKeys?: string) => api.get('/api/discover/feed', { params: { sections: sectionKeys } }),

  // 全局搜索
  search: (q: string, limit?: number) => api.get('/api/search', { params: { q, limit } }),
}
