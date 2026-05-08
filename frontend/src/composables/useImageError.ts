/**
 * 图片加载错误处理 composable
 * 用于处理外部图片（豆瓣、TMDb 等）加载失败的情况
 */
import { ref } from 'vue'

/**
 * 创建图片错误处理状态
 * @param defaultHidden 初始时是否隐藏图片（默认false，图片正常显示）
 */
export function useImageError(defaultHidden = false) {
  const imgLoaded = ref(!defaultHidden)

  /**
   * 图片加载失败时调用：隐藏图片，显示占位符
   */
  function handleImageError(e: Event) {
    const img = e.target as HTMLImageElement
    if (img) {
      img.style.display = 'none'
      imgLoaded.value = false
    }
  }

  /**
   * 图片加载成功时调用
   */
  function handleImageLoad(e: Event) {
    const img = e.target as HTMLImageElement
    if (img) {
      img.style.display = ''
      imgLoaded.value = true
    }
  }

  return { imgLoaded, handleImageError, handleImageLoad }
}

/**
 * 批量图片错误处理
 * 适用于卡片列表（如海报墙、收藏等有多个图片的组件）
 * 返回一个 Map，key 是图片标识，value 是否加载成功
 */
export function useImageErrorMap() {
  const errorMap = ref<Map<string, boolean>>(new Map())

  function handleImageError(key: string, e: Event) {
    const img = e.target as HTMLImageElement
    if (img) {
      img.style.display = 'none'
    }
    errorMap.value.set(key, false)
  }

  function clearError(key: string) {
    errorMap.value.delete(key)
  }

  function isImageFailed(key: string): boolean {
    return errorMap.value.get(key) === false
  }

  return { errorMap, handleImageError, clearError, isImageFailed }
}
