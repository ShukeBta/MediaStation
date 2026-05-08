import api from './client'

// 整理 & 刮削配置 API
export const settingsApi = {
  // 获取所有设置
  getAll: () => api.get('/api/settings'),

  // 获取单个设置
  get: (key: string) => api.get(`/api/settings/${encodeURIComponent(key)}`),

  // 更新单个设置
  update: (key: string, value: string) =>
    api.put(`/api/settings/${encodeURIComponent(key)}`, { value }),

  // 批量更新设置
  batchUpdate: (settings: Record<string, string>) =>
    api.patch('/api/settings', { settings }),

  // 重置单个设置为默认值
  reset: (key: string) =>
    api.delete(`/api/settings/${encodeURIComponent(key)}`),

  // 重置所有设置为默认值
  resetAll: () => api.delete('/api/settings'),

  // 获取配置 Schema（用于前端渲染表单）
  getSchema: () => api.get('/api/settings/schema'),
}

// 设置项类型定义
export interface SettingItem {
  key: string
  value: string
  default?: string
  type: 'text' | 'boolean' | 'select'
  group: string
  label: string
  description?: string
  options?: { value: string; label: string }[]
}

export interface SettingsSchema {
  groups: Record<string, SettingItem[]>
  schema: Record<string, SettingItem>
}

// 便捷方法：获取特定类型的设置
export const organizeSettings = {
  getMovieFormat: () => settingsApi.get('organize.movie_rename_format'),
  getTvFormat: () => settingsApi.get('organize.tv_rename_format'),
  getAnimeFormat: () => settingsApi.get('organize.anime_rename_format'),
  isAutoOrganize: () => settingsApi.get('organize.auto_organize'),
  setMovieFormat: (format: string) => settingsApi.update('organize.movie_rename_format', format),
  setTvFormat: (format: string) => settingsApi.update('organize.tv_rename_format', format),
  setAnimeFormat: (format: string) => settingsApi.update('organize.anime_rename_format', format),
  setAutoOrganize: (enabled: boolean) => settingsApi.update('organize.auto_organize', String(enabled)),
}

export const scrapeSettings = {
  getProviders: () => settingsApi.get('scrape.providers'),
  getLanguage: () => settingsApi.get('scrape.language'),
  isAutoScrape: () => settingsApi.get('scrape.auto_scrape_on_scan'),
  setProviders: (providers: string) => settingsApi.update('scrape.providers', providers),
  setLanguage: (lang: string) => settingsApi.update('scrape.language', lang),
  setAutoScrape: (enabled: boolean) => settingsApi.update('scrape.auto_scrape_on_scan', String(enabled)),
}
