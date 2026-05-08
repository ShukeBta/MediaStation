import api from './client'

export const downloadApi = {
  // 客户端
  getClients: () => api.get('/api/download/clients'),
  createClient: (data: any) => api.post('/api/download/clients', data),
  updateClient: (id: number, data: any) => api.put(`/api/download/clients/${id}`, data),
  deleteClient: (id: number) => api.delete(`/api/download/clients/${id}`),
  testClient: (id: number) => api.post(`/api/download/clients/${id}/test`),

  // 任务
  getTasks: (params?: any) => api.get('/api/download/tasks', { params }),
  addTask: (data: any) => api.post('/api/download/add', data),
  pauseTask: (id: number) => api.post(`/api/download/${id}/pause`),
  resumeTask: (id: number) => api.post(`/api/download/${id}/resume`),
  deleteTask: (id: number, deleteFiles?: boolean) =>
    api.delete(`/api/download/${id}`, { params: { delete_files: deleteFiles } }),
  syncTasks: () => api.post('/api/download/sync'),
  startAutoSync: () => api.post('/api/download/start-auto-sync'),

  // 整理入库
  organizeAll: () => api.post('/api/download/organize'),
  organizeTask: (id: number) => api.post(`/api/download/${id}/organize`),

  // Aria2 扩展
  getAria2Stats: (clientId: number) => api.get('/api/download/aria2/stats', { params: { client_id: clientId } }),
}
