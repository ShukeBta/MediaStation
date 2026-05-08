import { reactive } from 'vue'

export interface ToastItem {
  id: number
  type: 'success' | 'error' | 'info' | 'warning'
  message: string
  duration?: number
}

export interface ConfirmOptions {
  title?: string
  message: string
  confirmText?: string
  cancelText?: string
  danger?: boolean
}

let toastId = 0
const toasts = reactive<ToastItem[]>([])
const confirmState = reactive<{
  show: boolean
  resolve: ((value: boolean) => void) | null
  options: Required<ConfirmOptions>
}>({
  show: false,
  resolve: null,
  options: {
    title: '确认操作',
    message: '',
    confirmText: '确认',
    cancelText: '取消',
    danger: false,
  },
})

export function useToast() {
  function addToast(type: ToastItem['type'], message: string, duration = 3000) {
    const id = ++toastId
    toasts.push({ id, type, message, duration })
    if (duration > 0) {
      setTimeout(() => removeToast(id), duration)
    }
  }

  function removeToast(id: number) {
    const idx = toasts.findIndex(t => t.id === id)
    if (idx > -1) toasts.splice(idx, 1)
  }

  function success(message: string) { addToast('success', message) }
  function error(message: string) { addToast('error', message, 5000) }
  function info(message: string) { addToast('info', message) }
  function warning(message: string) { addToast('warning', message, 4000) }

  function confirm(opts: ConfirmOptions): Promise<boolean> {
    return new Promise((resolve) => {
      confirmState.resolve = resolve
      confirmState.options = {
        title: opts.title || '确认操作',
        message: opts.message,
        confirmText: opts.confirmText || '确认',
        cancelText: opts.cancelText || '取消',
        danger: opts.danger ?? false,
      }
      confirmState.show = true
    })
  }

  function resolveConfirm(value: boolean) {
    confirmState.show = false
    confirmState.resolve?.(value)
    confirmState.resolve = null
  }

  return {
    toasts,
    confirmState,
    addToast,
    removeToast,
    success,
    error,
    info,
    warning,
    confirm,
    resolveConfirm,
  }
}
