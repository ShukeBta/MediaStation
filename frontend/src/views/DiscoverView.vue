<template>
  <div class="p-4 md:p-6 max-w-7xl mx-auto space-y-6">
    <!-- 顶部栏 -->
    <div class="flex flex-wrap items-center gap-3">
      <h1 class="text-2xl font-bold shrink-0">发现</h1>
      <!-- 搜索栏 -->
      <div class="flex-1 min-w-[200px] max-w-md">
        <div class="relative">
          <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none" style="color: var(--text-faint)" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
          <input v-model="searchQuery" @input="handleSearch"
            class="input w-full text-sm !pl-9 pr-4 py-2"
            placeholder="搜索电影、电视剧、动漫..." />
          <button v-if="searchQuery" @click="clearSearch"
            class="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded-full hover:bg-[var(--bg-hover)] transition-colors"
            style="color: var(--text-faint)">
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
      </div>
      <div class="flex-1" />
      <!-- 自定义内容按钮 -->
      <button @click="showCustomize = true"
        class="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border border-[var(--border)] hover:bg-[var(--bg-secondary)] transition-colors shrink-0">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h7" />
        </svg>
        自定义
      </button>
    </div>

    <!-- 轮播/Banner 区域（仅本地数据） -->
    <div v-if="banners.length > 0" class="relative rounded-xl overflow-hidden aspect-[21/9] md:aspect-[3/1] bg-[var(--bg-card)] shadow-lg group">
      <div class="relative w-full h-full overflow-hidden">
        <TransitionGroup name="fade">
          <div v-for="(item, idx) in banners" :key="item.id"
            v-show="currentBanner === idx"
            class="absolute inset-0 cursor-pointer"
            @click="$router.push(`/media/${item.id}`)">
            <img :src="item.backdrop_url || item.poster_url" :alt="item.title"
              class="w-full h-full object-cover" referrerpolicy="no-referrer"
              @error="handleBannerImageError($event, item)" />
            <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" />
            <div class="absolute bottom-0 left-0 right-0 p-5 md:p-8">
              <div class="flex items-center gap-2 mb-2">
                <span class="text-xs font-medium px-2 py-0.5 rounded uppercase backdrop-blur-sm"
                  :class="{
                    'bg-blue-500/80 text-white': item.media_type === 'movie',
                    'bg-emerald-500/80 text-white': item.media_type === 'tv',
                    'bg-pink-500/80 text-white': item.media_type === 'anime',
                  }">
                  {{ item.media_type === 'movie' ? '电影' : item.media_type === 'tv' ? '电视剧' : '动漫' }}
                </span>
                <span v-if="item.rating" class="text-xs text-yellow-400">★ {{ item.rating.toFixed(1) }}</span>
                <span v-if="item.year" class="text-xs text-white/70">{{ item.year }}</span>
              </div>
              <h2 class="text-xl md:text-3xl font-bold text-white mb-1">{{ item.title }}</h2>
              <p v-if="item.overview" class="hidden md:block text-sm text-white/70 line-clamp-2 max-w-2xl">{{ item.overview }}</p>
            </div>
          </div>
        </TransitionGroup>
      </div>
      <!-- 轮播指示器 -->
      <div class="absolute bottom-3 right-4 flex gap-1.5 z-10">
        <button v-for="(item, idx) in banners" :key="'dot-' + item.id"
          @click="goBanner(idx)"
          :class="['w-2 h-2 rounded-full transition-all duration-300', currentBanner === idx ? 'bg-brand-500 w-5' : 'bg-white/50 hover:bg-white/75']" />
      </div>
      <!-- 左右箭头 -->
      <button @click="prevBanner"
        class="absolute left-2 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-black/40 hover:bg-black/60 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all duration-200 z-10">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/></svg>
      </button>
      <button @click="nextBanner"
        class="absolute right-2 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-black/40 hover:bg-black/60 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all duration-200 z-10">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>
      </button>
    </div>

    <!-- 外部数据源推荐区块 -->
    <section v-for="section in externalSections" :key="'ext-' + section.key" class="space-y-3">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <h2 class="text-lg font-semibold">
            <span class="mr-1">{{ section.icon }}</span>{{ section.label }}
          </h2>
          <span v-if="section.source" class="text-xs px-1.5 py-0.5 rounded bg-[var(--bg-secondary)]" style="color: var(--text-muted)">
            {{ sourceLabel(section.source) }}
          </span>
        </div>
        <button
          @click="goSectionMore(section)"
          v-if="section.items && section.items.length >= (section.limit || 10)"
          class="text-sm text-[var(--accent)] hover:text-[var(--accent-hover)] transition-colors flex items-center gap-1">
          更多
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>
        </button>
      </div>
      <!-- 加载骨架 -->
      <div v-if="externalLoading && !section.items?.length" class="flex gap-4 overflow-x-auto pb-2">
        <div v-for="i in (section.limit || 8)" :key="'skel-' + i" class="shrink-0 animate-pulse w-28 md:w-36">
          <div class="aspect-[2/3] rounded-lg bg-[var(--bg-input)]" />
          <div class="h-4 bg-[var(--bg-input)] rounded mt-2 w-3/4" />
          <div class="h-3 bg-[var(--bg-input)] rounded mt-1 w-1/2" />
        </div>
      </div>
      <!-- 实际卡片 -->
      <div v-else-if="section.items && section.items.length > 0" class="flex gap-4 overflow-x-auto pb-2 scroll-smooth">
        <div v-for="(item, index) in section.items.slice(0, section.limit || 10)" :key="item.id"
          class="shrink-0 cursor-pointer group w-28 md:w-36"
          @click="handleExternalClick(item)">
          <div class="poster-wrapper rounded-lg bg-[var(--bg-input)] mb-2 shadow-md group-hover:shadow-xl transition-all duration-300 aspect-[2/3] h-40 md:h-52 relative z-0">
            <img v-if="item.poster_url" :src="proxyImage(item.poster_url)" :alt="item.title"
              class="w-full h-full object-cover"
              loading="lazy" referrerpolicy="no-referrer"
              @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />
            <div v-else class="w-full h-full flex items-center justify-center" style="color: var(--text-faint)">
              <svg class="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"/></svg>
            </div>
            <!-- 排名角标 -->
            <div v-if="item.rank && item.rank <= 3"
              class="absolute top-1.5 left-1.5 w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold text-white backdrop-blur-sm"
              :class="{ 'bg-yellow-500': item.rank === 1, 'bg-gray-400': item.rank === 2, 'bg-orange-600': item.rank === 3 }">
              {{ item.rank }}
            </div>
            <!-- 评分 -->
            <div v-if="item.rating" class="absolute top-1.5 right-1.5 bg-black/70 text-[10px] px-1 py-0.5 rounded text-yellow-400 backdrop-blur-sm">
              ★ {{ typeof item.rating === 'number' ? item.rating.toFixed(1) : item.rating }}
            </div>
            <!-- 周几标签(Bangumi) -->
            <div v-if="item.weekday" class="absolute bottom-8 right-1.5 bg-purple-500/80 text-[10px] px-1 py-0.5 rounded text-white backdrop-blur-sm">
              {{ item.weekday }}
            </div>
            <!-- 外部标记 -->
            <div v-if="item.external" class="absolute top-1.5 left-1.5 bg-brand-600/90 text-[9px] px-1.5 py-0.5 rounded text-white backdrop-blur-sm" v-show="!item.rank">
              {{ sourceLabel(item.source) }}
            </div>
            <!-- Hover 播放图标 -->
            <div class="absolute inset-0 bg-black/0 group-hover:bg-black/25 transition-colors duration-300 flex items-center justify-center">
              <div class="w-10 h-10 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all duration-300">
                <svg class="w-5 h-5 text-white ml-0.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
              </div>
            </div>
            <!-- 操作按钮（右下角，hover 显示） -->
            <div class="absolute bottom-1.5 right-1.5 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-10">
              <button @click.stop="showDetailModal(item)"
                class="w-7 h-7 rounded-full bg-black/60 hover:bg-brand-600 backdrop-blur-sm flex items-center justify-center transition-colors"
                title="查看详情">
                <svg class="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
              </button>
              <button @click.stop="quickSubscribe(item)"
                class="w-7 h-7 rounded-full bg-black/60 hover:bg-emerald-600 backdrop-blur-sm flex items-center justify-center transition-colors"
                title="订阅下载">
                <svg class="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
              </button>
            </div>
          </div>
          <div class="font-medium truncate text-xs">{{ item.title }}</div>
          <div class="text-xs" style="color: var(--text-muted)">{{ item.year || '—' }}</div>
        </div>
      </div>
      <!-- 空状态 -->
      <div v-else-if="!externalLoading" class="py-6 text-center" style="color: var(--text-muted)">
        <p class="text-sm">暂无数据</p>
      </div>
    </section>

    <!-- 空状态 -->
    <div v-if="allLoaded && banners.length === 0 && externalSections.every(s => !s.items?.length)">
      <AppEmpty message="暂无推荐内容，请开启外部数据源或添加媒体库" />
    </div>

    <!-- ═══════════ 自定义内容弹窗 ═══════════ -->
    <Teleport to="body">
      <div v-if="showCustomize" class="fixed inset-0 z-50 flex items-center justify-center p-4" @click.self="closeCustomize">
        <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" />
        <div class="relative bg-[var(--bg-card)] rounded-xl shadow-2xl w-full max-w-lg max-h-[85vh] flex flex-col animate-in">
          <div class="flex items-center justify-between p-5 border-b border-[var(--border)]">
            <div class="flex items-center gap-2">
              <svg class="w-5 h-5" style="color: var(--accent)" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h7" />
              </svg>
              <h3 class="text-lg font-semibold">自定义内容</h3>
            </div>
            <button @click="closeCustomize" class="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-[var(--bg-secondary)] transition-colors">
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
            </button>
          </div>
          <div class="px-5 pt-3 pb-1 text-xs" style="color: var(--text-muted)">选择您想在页面显示的内容</div>
          <div class="flex-1 overflow-y-auto p-5 pt-2">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <label v-for="opt in allSectionOptions" :key="opt.key"
                class="flex items-center gap-2.5 p-3 rounded-lg border cursor-pointer transition-all duration-150 select-none"
                :class="[
                  selectedKeys.has(opt.key)
                    ? 'border-[var(--accent)] bg-[var(--accent)]/5 shadow-sm'
                    : 'border-[var(--border)] hover:border-[var(--border-focus)] hover:bg-[var(--bg-secondary)]',
                  !opt.enabled ? 'opacity-45' : ''
                ]"
                :title="opt.enabled ? '' : `需配置 ${sourceLabel(opt.source)} 数据源`">
                <input type="checkbox" :value="opt.key" :checked="selectedKeys.has(opt.key)"
                  :disabled="!opt.enabled"
                  @change="toggleOption(opt.key, ($event as any).target.checked)"
                  class="w-4 h-4 rounded border-[var(--border)] accent-[var(--accent)]" />
                <div class="flex-1 min-w-0">
                  <div class="text-sm font-medium truncate flex items-center gap-1">
                    <span>{{ opt.icon }}</span>
                    <span>{{ opt.label }}</span>
                  </div>
                  <div v-if="!opt.enabled" class="text-[11px] mt-0.5" style="color: var(--text-muted)">需要先配置{{ sourceLabel(opt.source) }}</div>
                </div>
              </label>
            </div>
          </div>
          <div class="flex items-center justify-between p-5 border-t border-[var(--border)]">
            <div class="flex gap-2">
              <button @click="selectAll" class="text-sm px-3 py-1.5 rounded-lg hover:bg-[var(--bg-secondary)] transition-colors">全选</button>
              <button @click="selectNone" class="text-sm px-3 py-1.5 rounded-lg hover:bg-[var(--bg-secondary)] transition-colors">全不选</button>
            </div>
            <button @click="saveCustomize"
              class="flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg bg-[var(--accent)] text-white hover:opacity-90 transition-opacity">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              保存
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ═══════════ 详情 + 订阅弹窗 ═══════════ -->
    <Teleport to="body">
      <div v-if="detailItem" class="fixed inset-0 z-50 flex items-center justify-center p-4" @click.self="closeDetail">
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" />
        <div class="relative bg-[var(--bg-card)] rounded-xl shadow-2xl w-full max-w-lg max-h-[85vh] flex flex-col animate-in overflow-hidden">
          <!-- 顶部背景条 -->
          <div v-if="detailItem.backdrop_url || detailItem.poster_url" class="h-36 relative shrink-0 overflow-hidden">
            <img :src="proxyImage(detailItem.backdrop_url || detailItem.poster_url)" class="w-full h-full object-cover opacity-40" referrerpolicy="no-referrer"
              @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />
            <div class="absolute inset-0 bg-gradient-to-t from-[var(--bg-card)] via-transparent to-transparent" />
          </div>
          <!-- 关闭按钮 -->
          <button @click="closeDetail" class="absolute top-3 right-3 z-10 w-8 h-8 rounded-full bg-black/40 hover:bg-black/60 text-white flex items-center justify-center transition-colors">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
          <!-- 海报（悬浮） -->
          <div v-if="detailItem.poster_url" class="absolute top-20 left-5 z-10 w-28 rounded-lg overflow-hidden shadow-xl border-2 border-[var(--bg-card)]">
            <img :src="proxyImage(detailItem.poster_url)" :alt="detailItem.title" class="w-full aspect-[2/3] object-cover" referrerpolicy="no-referrer"
              @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />
          </div>
          <!-- 内容区（可滚动） -->
          <div class="flex-1 overflow-y-auto pt-14 px-5 pb-5">
            <div class="ml-32 space-y-1 mb-3">
              <h3 class="text-lg font-bold leading-tight">{{ detailItem.title }}</h3>
              <div v-if="detailItem.original_title && detailItem.original_title !== detailItem.title" class="text-xs" style="color: var(--text-muted)">{{ detailItem.original_title }}</div>
            </div>
            <div class="flex flex-wrap items-center gap-2 text-xs mb-3 ml-0">
              <span v-if="detailItem.media_type" class="px-2 py-0.5 rounded uppercase font-medium"
                :class="{
                  'bg-blue-500/20 text-blue-400': detailItem.media_type === 'movie',
                  'bg-emerald-500/20 text-emerald-400': detailItem.media_type === 'tv',
                  'bg-pink-500/20 text-pink-400': detailItem.media_type === 'anime',
                }">
                {{ detailItem.media_type === 'movie' ? '电影' : detailItem.media_type === 'tv' ? '电视剧' : '动漫' }}
              </span>
              <span v-if="detailItem.year" class="px-2 py-0.5 rounded bg-[var(--bg-secondary)]" style="color: var(--text-muted)">{{ detailItem.year }}</span>
              <span v-if="detailItem.rating" class="text-yellow-400 font-medium">★ {{ typeof detailItem.rating === 'number' ? detailItem.rating.toFixed(1) : detailItem.rating }}</span>
              <span v-if="detailItem.external" class="px-2 py-0.5 rounded bg-brand-600/20 text-brand-400 text-[11px]">{{ sourceLabel(detailItem.source) }}</span>
            </div>
            <p v-if="detailItem.overview" class="text-sm leading-relaxed mb-4" style="color: var(--text-muted)">
              {{ detailItem.overview.length > 200 ? detailItem.overview.slice(0, 200) + '...' : detailItem.overview }}
            </p>
            <p v-else class="text-sm italic mb-4" style="color: var(--text-faint)">暂无简介</p>
            <!-- 操作按钮区 -->
            <div class="flex flex-wrap gap-2 pt-2 border-t border-[var(--border)]">
              <button @click="doSubscribe"
                :disabled="subscribing"
                class="flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-50 transition-colors">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
                {{ subscribing ? '订阅中...' : '订阅下载' }}
              </button>
              <button @click="searchMedia"
                class="flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg bg-[var(--bg-secondary)] hover:bg-[var(--bg-hover)] border border-[var(--border)] transition-colors"
                style="color: var(--text-secondary)">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
                搜索资源
              </button>
              <button v-if="detailItem.tmdb_id"
                class="flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg bg-[var(--bg-secondary)] hover:bg-[var(--bg-hover)] border border-[var(--border)] transition-colors"
                style="color: var(--text-secondary)"
                @click="copyTmdbId">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>
                {{ copiedTmdb ? '已复制!' : 'TMDb' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ═══════════ "更多"影片列表弹窗 ═══════════ -->
    <Teleport to="body">
      <div v-if="moreSection" class="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-8" @click.self="closeMore">
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" />
        <div class="relative bg-[var(--bg-card)] rounded-xl shadow-2xl w-full max-w-4xl max-h-[85vh] flex flex-col animate-in overflow-hidden">
          <!-- 标题栏 -->
          <div class="flex items-center justify-between p-5 border-b border-[var(--border)] shrink-0">
            <div class="flex items-center gap-2">
              <span class="text-lg">{{ moreSection.icon }}</span>
              <h3 class="text-lg font-semibold">{{ moreSection.label }} — 全部</h3>
              <span class="text-xs px-1.5 py-0.5 rounded bg-[var(--bg-secondary)]" style="color: var(--text-muted)">
                {{ sourceLabel(moreSection.source) }} · 共 {{ moreSection.items?.length || 0 }} 部
              </span>
            </div>
            <button @click="closeMore" class="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-[var(--bg-secondary)] transition-colors">
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
            </button>
          </div>
          <!-- 影片网格 -->
          <div class="flex-1 overflow-y-auto p-5 pt-3">
            <div v-if="moreLoading" class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-3 md:gap-4">
              <div v-for="i in 18" :key="'mskel-' + i" class="animate-pulse">
                <div class="aspect-[2/3] rounded-lg bg-[var(--bg-input)]" />
                <div class="h-4 bg-[var(--bg-input)] rounded mt-2 w-3/4" />
                <div class="h-3 bg-[var(--bg-input)] rounded mt-1 w-1/2" />
              </div>
            </div>
            <div v-else-if="moreSection.items && moreSection.items.length > 0" class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-3 md:gap-4">
              <div v-for="(item) in moreSection.items" :key="'m-' + item.id"
                class="cursor-pointer group"
                @click="closeMore(); handleExternalClick(item)">
                <div class="rounded-lg bg-[var(--bg-input)] overflow-hidden aspect-[2/3] h-40 sm:h-48 md:h-56 relative shadow-md group-hover:shadow-xl transition-all duration-300 image-container">
                  <img v-if="item.poster_url" :src="proxyImage(item.poster_url)" :alt="item.title"
                    class="w-full h-full object-cover transition-transform duration-300"
                    loading="lazy" referrerpolicy="no-referrer"
                    @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />
                  <div v-else class="w-full h-full flex items-center justify-center" style="color: var(--text-faint)">
                    <svg class="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"/></svg>
                  </div>
                  <!-- 评分 -->
                  <div v-if="item.rating" class="absolute top-1 right-1 bg-black/70 text-[9px] px-1 py-0.5 rounded text-yellow-400 backdrop-blur-sm">
                    ★ {{ typeof item.rating === 'number' ? item.rating.toFixed(1) : item.rating }}
                  </div>
                  <!-- 排名角标 -->
                  <div v-if="item.rank && item.rank <= 3"
                    class="absolute top-1 left-1 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white backdrop-blur-sm"
                    :class="{ 'bg-yellow-500': item.rank === 1, 'bg-gray-400': item.rank === 2, 'bg-orange-600': item.rank === 3 }">
                    {{ item.rank }}
                  </div>
                </div>
                <div class="mt-1.5">
                  <div class="text-xs font-medium truncate">{{ item.title }}</div>
                  <div class="text-[11px]" style="color: var(--text-muted)">{{ item.year || '—' }}</div>
                </div>
              </div>
            </div>
            <div v-else class="py-12 text-center" style="color: var(--text-muted)">
              <p class="text-sm">暂无数据</p>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { mediaApi } from '@/api/media'
import { subscribeApi } from '@/api/subscribe'
import AppEmpty from '@/components/AppEmpty.vue'
import { useToast } from '@/composables/useToast'

const router = useRouter()
const toast = useToast()

// ── Banner 轮播 ──
const localLoaded = ref(false)
const externalLoading = ref(true)
const currentBanner = ref(0)
let bannerTimer: ReturnType<typeof setInterval> | null = null
const banners = ref<any[]>([])

// ── 自定义弹窗 ──
const showCustomize = ref(false)

interface SectionOption {
  key: string
  label: string
  icon: string
  source: string
  enabled: boolean
}

const allSectionOptions = ref<SectionOption[]>([])
const selectedKeys = ref<Set<string>>(new Set())
const STORAGE_KEY = 'mediastation_discover_sections'

const DEFAULT_SECTIONS = [
  'tmdb_trending', 'tmdb_popular_movies', 'tmdb_now_playing', // TMDB
  'douban_hot_movies', 'douban_top250',                        // 豆瓣
]

// ── 外部数据源区块 ──
interface ExternalSection {
  key: string
  label: string
  icon: string
  source: string
  items?: any[]
  limit?: number
}
const externalSections = reactive<ExternalSection[]>([])

const allLoaded = computed(() => localLoaded.value && !externalLoading.value)

// ── 搜索功能 ──
const searchQuery = ref('')
let searchTimer: any

function handleSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    const q = searchQuery.value.trim()
    if (q) {
      // 跳转到专门的搜索结果页面
      router.push({ path: '/search', query: { q } })
    }
  }, 500)
}

function clearSearch() {
  searchQuery.value = ''
}

// ── 工具函数 ──
function sourceLabel(source: string): string {
  const map: Record<string, string> = {
    tmdb: 'TMDb',
    douban: '豆瓣',
    bangumi: 'Bangumi',
    tmdb_np: 'TMDb',
  }
  return map[source] || source
}

/** 图片代理：豆瓣等防盗链图片通过后端代理加载 */
function proxyImage(url: string | undefined | null): string {
  if (!url) return ''
  // 豆瓣图片需要走代理
  if (url.includes('doubanio.com')) {
    return `/api/discover/image-proxy?url=${encodeURIComponent(url)}`
  }
  // TMDb / Bangumi 等直接返回（CDN 无防盗链）
  return url
}

/** Banner 图片加载失败处理 */
function handleBannerImageError(e: Event, item: any) {
  const img = e.target as HTMLImageElement
  // 如果当前是 backdrop，尝试使用 poster
  if (item.poster_url && img.src.includes('backdrop') || img.src === item.backdrop_url) {
    img.src = item.poster_url
    img.style.objectFit = 'contain'  // 使用 contain 避免放大
  } else {
    img.style.display = 'none'
  }
}

function nextBanner() {
  if (banners.value.length === 0) return
  currentBanner.value = (currentBanner.value + 1) % banners.value.length
}

function prevBanner() {
  if (banners.value.length === 0) return
  currentBanner.value = (currentBanner.value - 1 + banners.value.length) % banners.value.length
}

function goBanner(idx: number) {
  currentBanner.value = idx
}

function startAutoPlay() {
  stopAutoPlay()
  if (banners.value.length > 1) {
    bannerTimer = setInterval(nextBanner, 5000)
  }
}

function stopAutoPlay() {
  if (bannerTimer) {
    clearInterval(bannerTimer)
    bannerTimer = null
  }
}

// ── 详情弹窗 + 订阅 ──
const detailItem = ref<any>(null)
const subscribing = ref(false)
const copiedTmdb = ref(false)

function handleExternalClick(item: any) {
  if (!item.external) {
    router.push(`/media/${item.id}`)
    return
  }
  showDetailModal(item)
}

function showDetailModal(item: any) {
  // 如果是 TMDB 搜索结果，转换格式
  if (item.poster_path !== undefined && !item.poster_url) {
    detailItem.value = {
      ...item,
      tmdb_id: item.id,
      title: item.title || item.name,
      poster_url: item.poster_path ? `https://image.tmdb.org/t/p/w500${item.poster_path}` : null,
      backdrop_url: item.backdrop_path ? `https://image.tmdb.org/t/p/w780${item.backdrop_path}` : null,
      overview: item.overview,
      year: (item.release_date || item.first_air_date || '').substring(0, 4) || null,
      media_type: item.media_type === 'movie' ? 'movie' : 'tv',
      rating: item.vote_average,
      // 保存 TMDB 原始英文名称，用于站点搜索
      original_title: item.original_title || null,
      original_name: item.original_name || null,
      external: true,
      source: 'tmdb',
    }
  } else {
    detailItem.value = item
  }
  copiedTmdb.value = false
}

function closeDetail() {
  detailItem.value = null
}

async function quickSubscribe(item: any) {
  detailItem.value = item
  await doSubscribe()
}

async function doSubscribe() {
  if (!detailItem.value) return
  const item = detailItem.value
  subscribing.value = true
  try {
    // 从 TMDB 搜索结果获取英文原名（用于站点搜索）
    // 电影使用 original_title，剧集使用 original_name
    const originalName = item.original_title || item.original_name || null
    await subscribeApi.createSubscription({
      name: item.title,
      original_name: originalName,
      tmdb_id: item.tmdb_id || null,
      media_type: item.media_type || 'movie',
      year: item.year || null,
      quality_filter: ['1080p', '720p'],
    })
    toast.success(`「${item.title}」已添加到订阅列表！`)
    closeDetail()
  } catch (e: any) {
    const msg = e.response?.data?.detail || e.message
    if (typeof msg === 'string' && msg.includes('already exists')) {
      toast.info('该订阅已存在')
    } else {
      toast.error(`订阅失败: ${msg}`)
    }
  } finally {
    subscribing.value = false
  }
}

/** 跳转到搜索资源页 */
function searchMedia() {
  if (!detailItem.value) return
  router.push({ path: '/subscribe', query: { search: detailItem.value.title } })
}

/** 复制 TMDb ID */
async function copyTmdbId() {
  if (!detailItem.value?.tmdb_id) return
  try {
    await navigator.clipboard.writeText(String(detailItem.value.tmdb_id))
    copiedTmdb.value = true
    setTimeout(() => { copiedTmdb.value = false }, 2000)
  } catch { /* ignore */ }
}

// ── "更多"按钮：展开显示更多影片 ──
const moreSection = ref<ExternalSection | null>(null)
const moreLoading = ref(false)

async function goSectionMore(section: ExternalSection) {
  moreSection.value = section
  moreLoading.value = true
  try {
    // 重新请求该区块的更多数据（不限制 limit）
    const res = await mediaApi.getDiscoverFeed(section.key)
    const data = res.data
    const feedData = data[section.key]
    const items = feedData?.items || []
    // 更新 section 的 items 为完整列表
    if (moreSection.value) {
      moreSection.value.items = items
    }
  } catch (e) {
    console.error('Load more failed:', e)
  } finally {
    moreLoading.value = false
  }
}

function closeMore() {
  moreSection.value = null
}

// ── 自定义弹窗操作 ──
function toggleOption(key: string, checked: boolean) {
  if (checked) {
    selectedKeys.value.add(key)
  } else {
    selectedKeys.value.delete(key)
  }
}

function selectAll() {
  for (const opt of allSectionOptions.value) {
    if (opt.enabled) selectedKeys.value.add(opt.key)
  }
}

function selectNone() {
  selectedKeys.value.clear()
}

function saveCustomize() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...selectedKeys.value]))
  showCustomize.value = false
  loadExternalData()
}

function closeCustomize() {
  showCustomize.value = false
}

// ── 数据加载 ──

/** 加载本地 Banner 数据 */
async function loadLocalData() {
  try {
    const res = await mediaApi.getItems({ page: 1, page_size: 6, sort_by: 'rating', sort_order: 'desc' })
    const data = res.data
    const allItems = data.items || []
    banners.value = allItems.filter((i: any) => i.backdrop_url || i.poster_url).slice(0, 5)
    if (banners.value.length === 0 && allItems.length > 0) {
      banners.value = allItems.slice(0, Math.min(5, allItems.length))
    }
    startAutoPlay()
  } catch (e) {
    console.error('Discover banner load error:', e)
  } finally {
    localLoaded.value = true
  }
}

/** 加载外部数据源 */
async function loadExternalData() {
  const extKeys = [...selectedKeys.value].filter(k =>
    !['recent_movies', 'recent_tv', 'top_rated', 'anime'].includes(k)
  )

  externalSections.splice(0, externalSections.length)

  if (extKeys.length === 0) {
    externalLoading.value = false
    return
  }

  externalLoading.value = true

  try {
    const sectionsParam = extKeys.join(',')
    const res = await mediaApi.getDiscoverFeed(sectionsParam)
    const data = res.data

    for (const opt of allSectionOptions.value) {
      if (!extKeys.includes(opt.key)) continue

      const feedData = data[opt.key]
      const items = feedData?.items || []

      externalSections.push({
        key: opt.key,
        label: opt.label,
        icon: opt.icon,
        source: opt.source,
        items: items,
        limit: opt.key === 'douban_top250' ? 20 : 10,
      })
    }
  } catch (e) {
    console.error('Discover external load error:', e)
  } finally {
    externalLoading.value = false
  }
}

/** 初始化选项列表和用户偏好 */
async function initOptions() {
  try {
    const secRes = await mediaApi.getDiscoverSections()
    allSectionOptions.value = secRes.data.sections || []

    const saved = localStorage.getItem(STORAGE_KEY)
    let savedKeys: string[] | null = null
    if (saved) {
      try { savedKeys = JSON.parse(saved) } catch { /* ignore */ }
    }

    const keys = savedKeys || DEFAULT_SECTIONS
    selectedKeys.value = new Set(keys.filter(k =>
      allSectionOptions.value.some(o => o.key === k && o.enabled)
    ))
  } catch (e) {
    console.error('Init options failed:', e)
    selectedKeys.value = new Set(DEFAULT_SECTIONS)
  }
}

onMounted(async () => {
  await initOptions()
  await Promise.all([
    loadLocalData(),
    loadExternalData(),
  ])
})

onUnmounted(() => {
  stopAutoPlay()
})
</script>

<style scoped>
.scroll-smooth::-webkit-scrollbar {
  display: none;
}
.scroll-smooth {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

/* 防止图片溢出容器 - 确保所有图片容器正确裁剪 */
:deep(.poster-wrapper) {
  overflow: hidden;
  border-radius: 0.5rem;
  transform: translateZ(0);
  isolation: isolate;
}

/* 确保图片在hover时不会溢出 */
:deep(.poster-wrapper img) {
  max-width: 100%;
  max-height: 100%;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  will-change: transform;
  transform: translateZ(0);
}

/* hover 时图片缩放，但不会溢出容器 */
:deep(.poster-wrapper:hover img) {
  transform: scale(1.05);
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.5s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

.animate-in {
  animation: modalIn 0.2s ease-out;
}
@keyframes modalIn {
  from { opacity: 0; transform: scale(0.96); }
  to   { opacity: 1; transform: scale(1); }
}
</style>
