import { ref } from 'vue'

export function useFormat() {
  function formatFileSize(bytes: number): string {
    if (!bytes || bytes <= 0 || isNaN(bytes)) return '0 B'
    const units = ['B', 'KB', 'MB', 'GB', 'TB']
    const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
    return `${(bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0)} ${units[i]}`
  }

  function formatDuration(seconds: number): string {
    if (!seconds || seconds <= 0) return '0:00'
    const h = Math.floor(seconds / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    const s = Math.floor(seconds % 60)
    if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  function formatSpeed(bytesPerSec: number): string {
    if (!bytesPerSec || bytesPerSec <= 0) return '0 B/s'
    return `${formatFileSize(bytesPerSec)}/s`
  }

  function formatDate(dateStr: string): string {
    if (!dateStr) return ''
    const d = new Date(dateStr)
    return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
  }

  return { formatFileSize, formatDuration, formatSpeed, formatDate }
}
