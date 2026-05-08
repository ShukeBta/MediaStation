import api from './client'

// ── Types ──────────────────────────────────────────────────────────────────

export interface FileItem {
  name: string
  path: string
  is_dir: boolean
  size?: number
  modified?: string
  permissions?: string
}

export interface BrowseResponse {
  current: string
  parent: string | null
  items: FileItem[]
}

export interface FolderCreateRequest {
  path: string
}

export interface FolderRenameRequest {
  path: string
  new_name: string
}

export interface FolderDeleteRequest {
  path: string
  force?: boolean
}

export interface BatchRenameOperation {
  path: string
  new_name: string
}

export interface BatchRenameRequest {
  operations: BatchRenameOperation[]
  mode: 'preview' | 'execute'
}

export interface BatchResponse {
  message: string
  started: string[]
  errors: Array<{ path?: string; id?: string; error: string }>
  total: number
  success_count: number
  error_count: number
}

export interface AIRenameRequest {
  paths: string[]
  style?: 'media' | 'clean' | 'original'
  language?: 'zh' | 'en'
  extra_hint?: string
}

export interface AIRenameCandidate {
  original: string
  original_path: string
  suggested: string
  suggested_path: string
  confidence: number
  reason: string
  exists: boolean
  error?: string
}

export interface AIRenameResponse {
  total: number
  success: number
  failed: number
  candidates: AIRenameCandidate[]
  model_used: string
  tokens_used: number
}

// ── Admin File Manager API ──────────────────────────────────────────────────

export const adminApi = {
  // 浏览目录
  browseFiles: (path: string = '.') =>
    api.get<{ data: BrowseResponse }>('/api/admin/files/browse', { params: { path } }),

  // 获取媒体库根文件夹
  getMediaFolders: () =>
    api.get<{ data: string[] }>('/api/admin/files/folders'),

  // 创建文件夹
  createFolder: (path: string) =>
    api.post<{ data: FileItem }>('/api/admin/files/folders/create', { path } as FolderCreateRequest),

  // 重命名文件夹
  renameFolder: (path: string, new_name: string) =>
    api.post<{ data: FileItem }>('/api/admin/files/folders/rename', { path, new_name } as FolderRenameRequest),

  // 删除文件夹
  deleteFolder: (path: string, force: boolean = false) =>
    api.post<{ data: Record<string, unknown> }>('/api/admin/files/folders/delete', { path, force } as FolderDeleteRequest),

  // 删除文件（通用）
  deleteFile: (path: string, force: boolean = false) =>
    api.delete<{ message: string }>('/api/admin/files', { params: { path, force } }),

  // 重命名文件
  renameFile: (path: string, new_name: string) =>
    api.post<{ data: FileItem }>('/api/admin/files/rename', { path, new_name }),

  // 预览重命名
  previewRename: (path: string, new_name: string) =>
    api.post<{ data: { original: string; renamed: string; exists: boolean; warning?: string } }>(
      '/api/admin/files/rename/preview',
      { path, new_name },
    ),

  // 批量重命名
  batchRename: (request: BatchRenameRequest) =>
    api.post<BatchResponse>('/api/admin/files/batch-rename', request),

  // 批量刮削
  batchScrape: (paths: string[]) =>
    api.post<BatchResponse>('/api/admin/files/batch-scrape', paths),

  // AI 生成重命名建议
  aiRename: (request: AIRenameRequest) =>
    api.post<{ data: AIRenameResponse }>('/api/admin/files/rename/ai', request),
}

// ── Utilities ───────────────────────────────────────────────────────────────

/** 格式化文件大小 */
export function formatFileSize(bytes?: number): string {
  if (!bytes) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = bytes
  let unitIdx = 0
  while (size >= 1024 && unitIdx < units.length - 1) {
    size /= 1024
    unitIdx++
  }
  return `${size.toFixed(unitIdx === 0 ? 0 : 1)} ${units[unitIdx]}`
}

/** 格式化修改时间 */
export function formatModified(dateStr?: string): string {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** 获取文件扩展名（小写） */
export function getFileExt(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot + 1).toLowerCase() : ''
}

/** 判断是否为媒体文件 */
export function isMediaFile(name: string): boolean {
  const ext = getFileExt(name)
  return ['mkv', 'mp4', 'avi', 'mov', 'm4v', 'wmv', 'flv', 'ts', 'rmvb'].includes(ext)
}

/** 判断是否为字幕文件 */
export function isSubtitleFile(name: string): boolean {
  const ext = getFileExt(name)
  return ['srt', 'ass', 'ssa', 'sub', 'idx', 'vtt'].includes(ext)
}
