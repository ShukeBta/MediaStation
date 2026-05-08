import { defineStore } from 'pinia'
import { ref } from 'vue'

export const usePlayerStore = defineStore('player', () => {
  const currentMedia = ref<any>(null)
  const isPlaying = ref(false)
  const currentTime = ref(0)
  const duration = ref(0)
  const volume = ref(1)
  const isFullscreen = ref(false)
  const quality = ref('auto')

  function setMedia(media: any) {
    currentMedia.value = media
    currentTime.value = 0
    isPlaying.value = false
  }

  function togglePlay() {
    isPlaying.value = !isPlaying.value
  }

  return {
    currentMedia, isPlaying, currentTime, duration,
    volume, isFullscreen, quality,
    setMedia, togglePlay,
  }
})
