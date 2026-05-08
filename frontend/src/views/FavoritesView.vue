<template>
  <div class="p-4 md:p-6 max-w-7xl mx-auto space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold">我的收藏</h1>
      <span v-if="total > 0" class="text-sm" style="color: var(--text-muted)">共 {{ total }} 部</span>
    </div>

    <!-- 加载骨架 -->
    <div v-if="loading" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3 md:gap-4">
      <div v-for="i in 12" :key="i" class="animate-pulse">
        <div class="rounded-lg aspect-[2/3] bg-[var(--bg-input)]" />
        <div class="h-4 bg-[var(--bg-input)] rounded mt-2 w-3/4" />
        <div class="h-3 bg-[var(--bg-input)] rounded mt-1 w-1/2" />
      </div>
    </div>

    <!-- 收藏列表 -->
    <div v-else-if="items.length > 0" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3 md:gap-4 stagger-in">
      <div v-for="(item, index) in items" :key="item.id"
        @click="$router.push(`/media/${item.id}`)"
        class="cursor-pointer group relative"
        :style="{ '--stagger': `${index * 30}ms` }">
        <div class="aspect-[2/3] rounded-lg bg-[var(--bg-input)] overflow-hidden relative shadow-md group-hover:shadow-xl transition-all duration-300">
          <img v-if="item.poster_url" :src="item.poster_url" :alt="item.title"
            class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            loading="lazy" referrerpolicy="no-referrer"
            @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />
          <div v-else class="w-full h-full flex items-center justify-center" style="color: var(--text-faint)">
            <svg class="w-16 h-16" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"/></svg>
          </div>
          <!-- 评分 -->
          <div v-if="item.rating" class="absolute top-2 right-2 bg-black/70 text-xs px-1.5 py-0.5 rounded text-yellow-400 backdrop-blur-sm">
            ★ {{ item.rating.toFixed(1) }}
          </div>
          <!-- 类型标签 -->
          <div class="absolute top-2 left-2 text-[10px] font-medium uppercase px-1.5 py-0.5 rounded backdrop-blur-sm"
            :class="{
              'bg-blue-500/80 text-white': item.media_type === 'movie',
              'bg-emerald-500/80 text-white': item.media_type === 'tv',
              'bg-pink-500/80 text-white': item.media_type === 'anime',
            }">
            {{ item.media_type === 'movie' ? '电影' : item.media_type === 'tv' ? '剧' : '漫' }}
          </div>
          <!-- 取消收藏按钮（悬停显示） -->
          <button @click.stop.prevent="removeFavorite(item)" title="取消收藏"
            class="absolute top-2 right-8 w-6 h-6 rounded-full bg-black/60 backdrop-blur-sm flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity text-yellow-400 hover:bg-red-500/90 hover:text-white">
            <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/></svg>
          </button>
          <!-- 悬浮播放 -->
          <div class="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors duration-300 flex items-center justify-center">
            <div class="w-12 h-12 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 scale-75 group-hover:scale-100 transition-all duration-300">
              <svg class="w-6 h-6 text-white ml-0.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
            </div>
          </div>
        </div>
        <div class="mt-2">
          <div class="text-sm font-medium truncate">{{ item.title }}</div>
          <div class="text-xs" style="color: var(--text-muted)">{{ item.year || '—' }} · {{ item.resolution || '未知' }}</div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="py-16 text-center">
      <AppEmpty message="还没有收藏任何内容" subMessage="浏览媒体库，点击星标按钮添加收藏" />
      <router-link to="/media" class="inline-flex items-center gap-2 mt-4 btn-primary text-sm px-4 py-2">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"/></svg>
        去浏览媒体库
      </router-link>
    </div>

    <!-- 分页 -->
    <div v-if="totalPages > 1" class="flex justify-center gap-2">
      <button @click="page > 1 && loadFavorites(page - 1)" :disabled="page <= 1"
        class="btn-secondary text-sm disabled:opacity-30">上一页</button>
      <span class="text-sm self-center" style="color: var(--text-muted)">{{ page }} / {{ totalPages }}</span>
      <button @click="page < totalPages && loadFavorites(page + 1)" :disabled="page >= totalPages"
        class="btn-secondary text-sm disabled:opacity-30">下一页</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { mediaApi } from '@/api/media'
import AppEmpty from '@/components/AppEmpty.vue'
import { useToast } from '@/composables/useToast'

const toast = useToast()
const items = ref<any[]>([])
const loading = ref(true)
const page = ref(1)
const total = ref(0)
const pageSize = 24
const totalPages = computed(() => Math.ceil(total.value / pageSize))

async function loadFavorites(p?: number) {
  if (p) page.value = p
  loading.value = true
  try {
    const { data } = await mediaApi.getFavorites({ page: page.value, page_size: pageSize })
    items.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function removeFavorite(item: any) {
  try {
    await mediaApi.removeFavorite(item.id)
    items.value = items.value.filter(i => i.id !== item.id)
    total.value = Math.max(0, total.value - 1)
    toast.info(`已取消收藏「${item.title}」`)
  } catch (e: any) {
    toast.error(`取消失败: ${e.response?.data?.detail || e.message}`)
  }
}

onMounted(() => loadFavorites())
</script>
