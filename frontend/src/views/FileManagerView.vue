<template>
  <div class="file-manager">
    <!-- ── 顶部工具栏 ── -->
    <div class="fm-toolbar">
      <div class="fm-breadcrumb">
        <button class="fm-btn-icon" :disabled="!canGoBack" @click="goBack" title="返回">
          <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
        </button>
        <button class="fm-btn-icon" @click="goHome" title="媒体根目录">
          <svg viewBox="0 0 20 20" fill="currentColor"><path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z"/></svg>
        </button>
        <div class="fm-path-chips">
          <span
            v-for="(seg, i) in pathSegments"
            :key="i"
            class="fm-path-seg"
            :class="{ active: i === pathSegments.length - 1 }"
            @click="navigateToSegment(i)"
          >{{ seg.label }}</span>
        </div>
      </div>

      <div class="fm-toolbar-right">
        <!-- 搜索框 -->
        <div class="fm-search">
          <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clip-rule="evenodd"/></svg>
          <input v-model="searchQuery" placeholder="过滤文件名..." />
        </div>

        <!-- 视图切换 -->
        <div class="fm-view-toggle">
          <button :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'" title="列表视图">
            <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M3 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 10a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 15a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clip-rule="evenodd"/></svg>
          </button>
          <button :class="{ active: viewMode === 'grid' }" @click="viewMode = 'grid'" title="网格视图">
            <svg viewBox="0 0 20 20" fill="currentColor"><path d="M5 3a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2V5a2 2 0 00-2-2H5zM5 11a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2v-2a2 2 0 00-2-2H5zM11 5a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V5zM11 13a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"/></svg>
          </button>
        </div>

        <!-- 操作按钮 -->
        <div class="fm-actions">
          <button class="fm-btn fm-btn-primary" @click="showNewFolderModal = true">
            <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd"/></svg>
            新建文件夹
          </button>
          <button
            v-if="selectedFiles.length > 0"
            class="fm-btn fm-btn-secondary"
            @click="showBatchRenamePanel = true"
          >
            <svg viewBox="0 0 20 20" fill="currentColor"><path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z"/><path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd"/></svg>
            批量重命名 ({{ selectedFiles.length }})
          </button>
          <button
            v-if="selectedFiles.length > 0"
            class="fm-btn fm-btn-ai"
            @click="openAiRenamePanel"
          >
            <svg viewBox="0 0 20 20" fill="currentColor"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>
            AI 重命名
          </button>
          <button
            v-if="selectedFiles.length > 0"
            class="fm-btn fm-btn-danger"
            @click="confirmDeleteSelected"
          >
            <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>
            删除 ({{ selectedFiles.length }})
          </button>
        </div>
      </div>
    </div>

    <!-- ── 主内容区 ── -->
    <div class="fm-body">
      <!-- 左侧侧边栏：树形目录 -->
      <div class="fm-sidebar" :class="{ collapsed: sidebarCollapsed }">
        <!-- 侧边栏头部 -->
        <div class="fm-sidebar-header">
          <span v-if="!sidebarCollapsed" class="fm-sidebar-title">媒体库</span>
          <button class="fm-sidebar-collapse-btn" @click="sidebarCollapsed = !sidebarCollapsed" :title="sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'">
            <svg viewBox="0 0 20 20" fill="currentColor" :class="{ 'rotate-180': !sidebarCollapsed }">
              <path fill-rule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clip-rule="evenodd"/>
            </svg>
          </button>
        </div>

        <!-- 折叠时只显示图标 -->
        <template v-if="sidebarCollapsed">
          <div
            v-for="folder in mediaFolders"
            :key="folder"
            class="fm-sidebar-icon"
            :class="{ active: currentPath.startsWith(folder) }"
            @click="navigate(folder)"
            :title="folderLabel(folder)"
          >
            <svg viewBox="0 0 20 20" fill="currentColor"><path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg>
          </div>
        </template>

        <!-- 展开时显示树形目录 -->
        <template v-else>
          <!-- 媒体库根目录快捷访问 -->
          <div class="fm-sidebar-section">
            <div class="fm-sidebar-section-title">快速访问</div>
            <div
              v-for="folder in mediaFolders"
              :key="folder"
              class="fm-sidebar-item"
              :class="{ active: currentPath === folder }"
              @click="navigate(folder)"
              :title="folder"
            >
              <svg viewBox="0 0 20 20" fill="currentColor"><path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z"/></svg>
              <span>{{ folderLabel(folder) }}</span>
            </div>
          </div>

          <!-- 树形目录结构 -->
          <div class="fm-sidebar-section fm-sidebar-tree-section">
            <div class="fm-sidebar-section-title">目录树</div>
            <FileTree
              :root-paths="mediaFolders"
              :current-path="currentPath"
              @navigate="navigate"
            />
          </div>
        </template>
      </div>

      <!-- 文件列表区 -->
      <div class="fm-content" @click.self="clearSelection">
        <!-- 加载中 -->
        <div v-if="loading" class="fm-loading">
          <div class="fm-spinner"></div>
          <span>加载中...</span>
        </div>

        <!-- 错误提示 -->
        <div v-else-if="error" class="fm-error">
          <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>
          <span>{{ error }}</span>
          <button @click="loadDirectory(currentPath)">重试</button>
        </div>

        <!-- 空目录 -->
        <div v-else-if="filteredItems.length === 0" class="fm-empty">
          <svg viewBox="0 0 20 20" fill="currentColor"><path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg>
          <span>{{ searchQuery ? '没有匹配的文件' : '空目录' }}</span>
        </div>

        <!-- 列表视图 -->
        <template v-else-if="viewMode === 'list'">
          <div class="fm-list">
            <!-- 表头 -->
            <div class="fm-list-header">
              <div class="fm-list-col fm-col-check">
                <input
                  type="checkbox"
                  :checked="allSelected"
                  :indeterminate="someSelected"
                  @change="toggleSelectAll"
                />
              </div>
              <div class="fm-list-col fm-col-name" @click="sortBy('name')">
                名称 <span class="sort-icon" v-if="sortField === 'name'">{{ sortDir === 'asc' ? '↑' : '↓' }}</span>
              </div>
              <div class="fm-list-col fm-col-size" @click="sortBy('size')">
                大小 <span class="sort-icon" v-if="sortField === 'size'">{{ sortDir === 'asc' ? '↑' : '↓' }}</span>
              </div>
              <div class="fm-list-col fm-col-modified" @click="sortBy('modified')">
                修改时间 <span class="sort-icon" v-if="sortField === 'modified'">{{ sortDir === 'asc' ? '↑' : '↓' }}</span>
              </div>
              <div class="fm-list-col fm-col-actions">操作</div>
            </div>

            <!-- 文件行 -->
            <div
              v-for="item in filteredItems"
              :key="item.path"
              class="fm-list-row"
              :class="{
                selected: isSelected(item),
                'is-dir': item.is_dir,
                'is-media': isMediaFile(item.name),
              }"
              @click.exact="toggleSelect(item)"
              @dblclick="item.is_dir ? navigate(item.path) : openRenameInline(item)"
              @contextmenu.prevent="openContextMenu($event, item)"
            >
              <div class="fm-list-col fm-col-check">
                <input
                  type="checkbox"
                  :checked="isSelected(item)"
                  @click.stop
                  @change="toggleSelect(item)"
                />
              </div>
              <div class="fm-list-col fm-col-name">
                <div class="fm-item-name">
                  <!-- 图标 -->
                  <span class="fm-icon" :class="getIconClass(item)">
                    <svg v-if="item.is_dir" viewBox="0 0 20 20" fill="currentColor"><path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg>
                    <svg v-else-if="isMediaFile(item.name)" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm3 2h6v4H7V5zm8 8v2h1v-2h-1zm-2-2H7v4h6v-4zm2 0h1V9h-1v2zm1-4V5h-1v2h1zM5 5H4v2h1V5zM4 7H3v2h1V7zm0 2H3v2h1V9zm0 2H3v2h1v-2zm0 2H3v2h1v-2zm1 2v-2H5v2h1zm2 0v-2H7v2h1zm2 0v-2H9v2h1zm2 0v-2h-1v2h1z" clip-rule="evenodd"/></svg>
                    <svg v-else viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clip-rule="evenodd"/></svg>
                  </span>
                  <!-- 行内重命名 -->
                  <template v-if="inlineRenaming === item.path">
                    <input
                      ref="renameInputRef"
                      v-model="inlineRenameValue"
                      class="fm-rename-input"
                      @keydown.enter="submitInlineRename(item)"
                      @keydown.esc="cancelInlineRename"
                      @blur="cancelInlineRename"
                      @click.stop
                    />
                  </template>
                  <template v-else>
                    <span class="fm-name-text">{{ item.name }}</span>
                  </template>
                </div>
              </div>
              <div class="fm-list-col fm-col-size">{{ formatFileSize(item.size) }}</div>
              <div class="fm-list-col fm-col-modified">{{ formatModified(item.modified) }}</div>
              <div class="fm-list-col fm-col-actions" @click.stop>
                <div class="fm-row-actions">
                  <button title="重命名" @click="openRenameInline(item)">
                    <svg viewBox="0 0 20 20" fill="currentColor"><path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z"/></svg>
                  </button>
                  <button title="删除" class="danger" @click="confirmDelete(item)">
                    <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- 网格视图 -->
        <template v-else>
          <div class="fm-grid">
            <div
              v-for="item in filteredItems"
              :key="item.path"
              class="fm-grid-item"
              :class="{ selected: isSelected(item), 'is-dir': item.is_dir }"
              @click.exact="toggleSelect(item)"
              @dblclick="item.is_dir ? navigate(item.path) : openRenameInline(item)"
              @contextmenu.prevent="openContextMenu($event, item)"
            >
              <div class="fm-grid-icon">
                <svg v-if="item.is_dir" viewBox="0 0 24 24" fill="currentColor"><path d="M10 4H4c-1.11 0-2 .89-2 2v12a2 2 0 002 2h16a2 2 0 002-2V8c0-1.11-.89-2-2-2h-8l-2-2z"/></svg>
                <svg v-else-if="isMediaFile(item.name)" viewBox="0 0 24 24" fill="currentColor"><path d="M18 4l2 4h-3l-2-4h-2l2 4h-3l-2-4H8l2 4H7L5 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4h-4z"/></svg>
                <svg v-else viewBox="0 0 24 24" fill="currentColor"><path d="M6 2c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6H6zm7 7V3.5L18.5 9H13z"/></svg>
              </div>
              <div class="fm-grid-name" :title="item.name">{{ item.name }}</div>
              <div class="fm-grid-size">{{ item.is_dir ? '文件夹' : formatFileSize(item.size) }}</div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- ── 状态栏 ── -->
    <div class="fm-statusbar">
      <span>{{ filteredItems.length }} 个项目</span>
      <span v-if="selectedFiles.length > 0">已选 {{ selectedFiles.length }} 个</span>
      <span v-if="selectedFiles.length > 0 && selectedTotalSize > 0">
        总大小：{{ formatFileSize(selectedTotalSize) }}
      </span>
      <div class="fm-statusbar-right">
        <span v-if="currentPath" class="fm-path-display" :title="currentPath">{{ currentPath }}</span>
      </div>
    </div>

    <!-- ══ 右键菜单 ══ -->
    <teleport to="body">
      <div
        v-if="contextMenu.visible"
        class="fm-context-menu"
        :style="{ top: contextMenu.y + 'px', left: contextMenu.x + 'px' }"
        @mouseleave="closeContextMenu"
      >
        <div class="fm-ctx-item" @click="contextMenuAction('open')">
          <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd"/></svg>
          {{ contextMenu.item?.is_dir ? '进入目录' : '预览' }}
        </div>
        <div class="fm-ctx-item" @click="contextMenuAction('rename')">
          <svg viewBox="0 0 20 20" fill="currentColor"><path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z"/></svg>
          重命名
        </div>
        <div class="fm-ctx-sep"></div>
        <div class="fm-ctx-item danger" @click="contextMenuAction('delete')">
          <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>
          删除
        </div>
      </div>
    </teleport>

    <!-- ══ 新建文件夹 Modal ══ -->
    <teleport to="body">
      <div v-if="showNewFolderModal" class="fm-modal-overlay" @click.self="showNewFolderModal = false">
        <div class="fm-modal">
          <div class="fm-modal-title">新建文件夹</div>
          <input
            v-model="newFolderName"
            placeholder="文件夹名称"
            @keydown.enter="createFolder"
            @keydown.esc="showNewFolderModal = false"
            ref="newFolderInputRef"
          />
          <div class="fm-modal-actions">
            <button class="fm-btn fm-btn-secondary" @click="showNewFolderModal = false">取消</button>
            <button class="fm-btn fm-btn-primary" :disabled="!newFolderName.trim() || creatingFolder" @click="createFolder">
              {{ creatingFolder ? '创建中...' : '创建' }}
            </button>
          </div>
        </div>
      </div>
    </teleport>

    <!-- ══ 删除确认 Modal ══ -->
    <teleport to="body">
      <div v-if="deleteModal.visible" class="fm-modal-overlay" @click.self="deleteModal.visible = false">
        <div class="fm-modal fm-modal-danger">
          <div class="fm-modal-title">
            <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>
            确认删除
          </div>
          <div class="fm-modal-body">
            <p>将要删除：<strong>{{ deleteModal.items.map(i => i.name).join('、') }}</strong></p>
            <p v-if="deleteModal.hasDirs" class="fm-modal-warn">包含文件夹，请选择删除模式：</p>
            <label v-if="deleteModal.hasDirs" class="fm-modal-check">
              <input type="checkbox" v-model="deleteModal.force" />
              强制删除（递归删除所有子文件，<strong>不可恢复！</strong>）
            </label>
          </div>
          <div class="fm-modal-actions">
            <button class="fm-btn fm-btn-secondary" @click="deleteModal.visible = false">取消</button>
            <button class="fm-btn fm-btn-danger" :disabled="deleteModal.loading" @click="executeDelete">
              {{ deleteModal.loading ? '删除中...' : '确认删除' }}
            </button>
          </div>
        </div>
      </div>
    </teleport>

    <!-- ══ 批量重命名面板 ══ -->
    <teleport to="body">
      <div v-if="showBatchRenamePanel" class="fm-panel-overlay">
        <div class="fm-panel">
          <div class="fm-panel-header">
            <span>批量重命名</span>
            <button class="fm-btn-icon" @click="showBatchRenamePanel = false">✕</button>
          </div>
          <div class="fm-panel-body">
            <div class="fm-rename-rule">
              <div class="fm-form-row">
                <label>操作模式</label>
                <select v-model="batchRename.mode">
                  <option value="replace">查找替换</option>
                  <option value="prefix">添加前缀</option>
                  <option value="suffix">添加后缀</option>
                  <option value="regex">正则替换</option>
                </select>
              </div>
              <div class="fm-form-row" v-if="batchRename.mode === 'replace' || batchRename.mode === 'regex'">
                <label>查找</label>
                <input v-model="batchRename.find" :placeholder="batchRename.mode === 'regex' ? '正则表达式' : '查找文本'" />
              </div>
              <div class="fm-form-row" v-if="batchRename.mode === 'replace' || batchRename.mode === 'regex'">
                <label>替换为</label>
                <input v-model="batchRename.replace" placeholder="替换文本（留空则删除）" />
              </div>
              <div class="fm-form-row" v-if="batchRename.mode === 'prefix'">
                <label>前缀</label>
                <input v-model="batchRename.prefix" placeholder="添加前缀文字" />
              </div>
              <div class="fm-form-row" v-if="batchRename.mode === 'suffix'">
                <label>后缀</label>
                <input v-model="batchRename.suffix" placeholder="添加后缀（在扩展名前）" />
              </div>
            </div>

            <!-- 预览列表 -->
            <div class="fm-rename-preview">
              <div class="fm-rename-preview-header">预览（{{ batchRenamePreview.length }} 个文件）</div>
              <div class="fm-rename-preview-list">
                <div
                  v-for="item in batchRenamePreview"
                  :key="item.path"
                  class="fm-rename-preview-row"
                  :class="{ conflict: item.conflict }"
                >
                  <span class="old-name">{{ item.oldName }}</span>
                  <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M12.293 5.293a1 1 0 011.414 0l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-2.293-2.293a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>
                  <span class="new-name" :class="{ unchanged: item.newName === item.oldName }">{{ item.newName }}</span>
                  <span v-if="item.conflict" class="conflict-badge">冲突</span>
                </div>
              </div>
            </div>
          </div>
          <div class="fm-panel-footer">
            <button class="fm-btn fm-btn-secondary" @click="showBatchRenamePanel = false">取消</button>
            <button
              class="fm-btn fm-btn-primary"
              :disabled="batchRename.executing || batchRenamePreview.every(p => p.newName === p.oldName)"
              @click="executeBatchRename"
            >
              {{ batchRename.executing ? '重命名中...' : `执行重命名 (${batchRenamePreview.filter(p => p.newName !== p.oldName).length})` }}
            </button>
          </div>
        </div>
      </div>
    </teleport>

    <!-- ══ AI 重命名面板 ══ -->
    <teleport to="body">
      <div v-if="showAiRenamePanel" class="fm-panel-overlay">
        <div class="fm-panel fm-panel-ai">
          <div class="fm-panel-header">
            <span>✨ AI 智能重命名</span>
            <button class="fm-btn-icon" @click="showAiRenamePanel = false">✕</button>
          </div>

          <!-- 配置阶段 -->
          <div v-if="aiRename.step === 'config'" class="fm-panel-body">
            <div class="fm-ai-config">
              <div class="fm-form-row">
                <label>命名风格</label>
                <select v-model="aiRename.style">
                  <option value="media">媒体规范（Movie.Name.2023.1080p）</option>
                  <option value="clean">简洁可读（电影名 (2023)）</option>
                  <option value="original">尽量保留原名</option>
                </select>
              </div>
              <div class="fm-form-row">
                <label>语言偏好</label>
                <select v-model="aiRename.language">
                  <option value="zh">中文优先</option>
                  <option value="en">英文</option>
                </select>
              </div>
              <div class="fm-form-row">
                <label>补充提示</label>
                <input v-model="aiRename.extraHint" placeholder="可选：系列名称、年份、特别说明等" />
              </div>
              <div class="fm-ai-files">
                <div class="fm-ai-files-title">待处理文件（{{ selectedFiles.length }} 个）</div>
                <div class="fm-ai-files-list">
                  <div v-for="f in selectedFiles" :key="f.path" class="fm-ai-file-item">
                    {{ f.name }}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 结果阶段 -->
          <div v-else-if="aiRename.step === 'result'" class="fm-panel-body">
            <div v-if="aiRename.loading" class="fm-ai-loading">
              <div class="fm-spinner fm-spinner-ai"></div>
              <span>AI 分析中（{{ aiRename.progress }}/{{ selectedFiles.length }}）...</span>
            </div>
            <div v-else class="fm-ai-results">
              <div class="fm-ai-result-summary">
                使用模型：<strong>{{ aiRename.response?.model_used }}</strong>
                &nbsp;·&nbsp; 消耗 Token：{{ aiRename.response?.tokens_used }}
                &nbsp;·&nbsp; 成功：{{ aiRename.response?.success }} / 失败：{{ aiRename.response?.failed }}
              </div>
              <div
                v-for="candidate in aiRename.response?.candidates"
                :key="candidate.original_path"
                class="fm-ai-candidate"
                :class="{ 'has-error': candidate.error, 'has-conflict': candidate.exists }"
              >
                <div class="fm-ai-cand-row">
                  <div class="fm-ai-cand-check">
                    <input
                      type="checkbox"
                      :checked="aiRename.selected.has(candidate.original_path)"
                      :disabled="!!candidate.error"
                      @change="toggleAiCandidate(candidate)"
                    />
                  </div>
                  <div class="fm-ai-cand-names">
                    <span class="old-name">{{ candidate.original }}</span>
                    <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M12.293 5.293a1 1 0 011.414 0l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-2.293-2.293a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>
                    <span class="new-name">{{ candidate.suggested }}</span>
                  </div>
                  <div class="fm-ai-cand-meta">
                    <span
                      class="confidence-badge"
                      :class="candidate.confidence >= 0.8 ? 'high' : candidate.confidence >= 0.5 ? 'medium' : 'low'"
                    >{{ Math.round(candidate.confidence * 100) }}%</span>
                    <span v-if="candidate.exists" class="warning-badge">目标已存在</span>
                    <span v-if="candidate.error" class="error-badge">{{ candidate.error }}</span>
                  </div>
                </div>
                <div v-if="candidate.reason" class="fm-ai-cand-reason">{{ candidate.reason }}</div>
              </div>
            </div>
          </div>

          <div class="fm-panel-footer">
            <template v-if="aiRename.step === 'config'">
              <button class="fm-btn fm-btn-secondary" @click="showAiRenamePanel = false">取消</button>
              <button class="fm-btn fm-btn-ai" :disabled="aiRename.loading" @click="runAiRename">
                ✨ 开始 AI 分析
              </button>
            </template>
            <template v-else>
              <button class="fm-btn fm-btn-secondary" @click="aiRename.step = 'config'">重新配置</button>
              <button
                v-if="!aiRename.loading"
                class="fm-btn fm-btn-primary"
                :disabled="aiRename.selected.size === 0"
                @click="applyAiRename"
              >
                应用选中重命名（{{ aiRename.selected.size }}）
              </button>
            </template>
          </div>
        </div>
      </div>
    </teleport>

    <!-- ══ Toast 通知 ══ -->
    <teleport to="body">
      <div class="fm-toast-container">
        <transition-group name="fm-toast">
          <div
            v-for="toast in toasts"
            :key="toast.id"
            class="fm-toast"
            :class="toast.type"
          >
            <svg v-if="toast.type === 'success'" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/></svg>
            <svg v-else-if="toast.type === 'error'" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>
            <svg v-else viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/></svg>
            <span>{{ toast.message }}</span>
          </div>
        </transition-group>
      </div>
    </teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import {
  adminApi,
  formatFileSize,
  formatModified,
  isMediaFile,
  getFileExt,
  type FileItem,
  type AIRenameCandidate,
  type AIRenameResponse,
} from '@/api/admin'
import FileTree from '@/components/FileTree.vue'

// ── State ──────────────────────────────────────────────────────────────────

const sidebarCollapsed = ref(false)
const currentPath = ref('')
const items = ref<FileItem[]>([])
const loading = ref(false)
const error = ref('')
const mediaFolders = ref<string[]>([])
const history = ref<string[]>([])
const selectedFiles = ref<FileItem[]>([])
const viewMode = ref<'list' | 'grid'>('list')
const searchQuery = ref('')
const sortField = ref<'name' | 'size' | 'modified'>('name')
const sortDir = ref<'asc' | 'desc'>('asc')

// 行内重命名
const inlineRenaming = ref('')
const inlineRenameValue = ref('')
const renameInputRef = ref<HTMLInputElement | null>(null)
const newFolderInputRef = ref<HTMLInputElement | null>(null)

// 新建文件夹
const showNewFolderModal = ref(false)
const newFolderName = ref('')
const creatingFolder = ref(false)

// 删除
const deleteModal = ref({
  visible: false,
  items: [] as FileItem[],
  hasDirs: false,
  force: false,
  loading: false,
})

// 批量重命名
const showBatchRenamePanel = ref(false)
const batchRename = ref({
  mode: 'replace' as 'replace' | 'prefix' | 'suffix' | 'regex',
  find: '',
  replace: '',
  prefix: '',
  suffix: '',
  executing: false,
})

// AI 重命名
const showAiRenamePanel = ref(false)
const aiRename = ref({
  step: 'config' as 'config' | 'result',
  style: 'media' as 'media' | 'clean' | 'original',
  language: 'zh' as 'zh' | 'en',
  extraHint: '',
  loading: false,
  progress: 0,
  response: null as AIRenameResponse | null,
  selected: new Set<string>(),
})

// 右键菜单
const contextMenu = ref({ visible: false, x: 0, y: 0, item: null as FileItem | null })

// Toast
const toasts = ref<Array<{ id: number; type: 'success' | 'error' | 'info'; message: string }>>([])
let toastId = 0

// ── Computed ───────────────────────────────────────────────────────────────

const filteredItems = computed(() => {
  let list = items.value
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(i => i.name.toLowerCase().includes(q))
  }
  return [...list].sort((a, b) => {
    // 文件夹始终排在前面
    if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1
    let cmp = 0
    if (sortField.value === 'name') cmp = a.name.localeCompare(b.name)
    else if (sortField.value === 'size') cmp = (a.size || 0) - (b.size || 0)
    else if (sortField.value === 'modified') cmp = (a.modified || '').localeCompare(b.modified || '')
    return sortDir.value === 'asc' ? cmp : -cmp
  })
})

const pathSegments = computed(() => {
  if (!currentPath.value) return []
  const parts = currentPath.value.replace(/\\/g, '/').split('/')
  return parts
    .filter(Boolean)
    .map((label, i, arr) => ({
      label,
      path: '/' + arr.slice(0, i + 1).join('/'),
    }))
})

const canGoBack = computed(() => history.value.length > 0)

const allSelected = computed(
  () => filteredItems.value.length > 0 && filteredItems.value.every(i => isSelected(i)),
)
const someSelected = computed(
  () => !allSelected.value && filteredItems.value.some(i => isSelected(i)),
)

const selectedTotalSize = computed(() =>
  selectedFiles.value.reduce((sum, f) => sum + (f.size || 0), 0),
)

const batchRenamePreview = computed(() => {
  return selectedFiles.value.map(f => {
    let newName = f.name
    const ext = getFileExt(f.name)
    const stem = ext ? f.name.slice(0, f.name.length - ext.length - 1) : f.name

    try {
      if (batchRename.value.mode === 'replace' && batchRename.value.find) {
        newName = f.name.replaceAll(batchRename.value.find, batchRename.value.replace)
      } else if (batchRename.value.mode === 'prefix' && batchRename.value.prefix) {
        newName = batchRename.value.prefix + f.name
      } else if (batchRename.value.mode === 'suffix' && batchRename.value.suffix) {
        newName = ext ? `${stem}${batchRename.value.suffix}.${ext}` : f.name + batchRename.value.suffix
      } else if (batchRename.value.mode === 'regex' && batchRename.value.find) {
        const regex = new RegExp(batchRename.value.find, 'g')
        newName = f.name.replace(regex, batchRename.value.replace)
      }
    } catch {
      newName = f.name // 正则错误时保持原名
    }

    return {
      path: f.path,
      oldName: f.name,
      newName,
      conflict: false, // 后端会检查
    }
  })
})

// ── Methods ────────────────────────────────────────────────────────────────

async function loadDirectory(path: string) {
  loading.value = true
  error.value = ''
  try {
    const res = await adminApi.browseFiles(path)
    currentPath.value = res.data.data.current
    items.value = res.data.data.items
    selectedFiles.value = []
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function loadMediaFolders() {
  try {
    const res = await adminApi.getMediaFolders()
    mediaFolders.value = res.data.data || []
    if (mediaFolders.value.length > 0 && !currentPath.value) {
      await loadDirectory(mediaFolders.value[0])
    }
  } catch {
    mediaFolders.value = []
  }
}

function navigate(path: string) {
  if (currentPath.value) history.value.push(currentPath.value)
  loadDirectory(path)
}

function goBack() {
  const prev = history.value.pop()
  if (prev) loadDirectory(prev)
}

function goHome() {
  history.value = []
  if (mediaFolders.value.length > 0) loadDirectory(mediaFolders.value[0])
}

function navigateToSegment(idx: number) {
  if (pathSegments.value[idx]) {
    navigate(pathSegments.value[idx].path)
  }
}

function folderLabel(path: string): string {
  return path.replace(/\\/g, '/').split('/').filter(Boolean).pop() || path
}

// ── 选择 ──

function isSelected(item: FileItem) {
  return selectedFiles.value.some(f => f.path === item.path)
}

function toggleSelect(item: FileItem) {
  const idx = selectedFiles.value.findIndex(f => f.path === item.path)
  if (idx >= 0) selectedFiles.value.splice(idx, 1)
  else selectedFiles.value.push(item)
}

function toggleSelectAll() {
  if (allSelected.value) {
    selectedFiles.value = []
  } else {
    selectedFiles.value = [...filteredItems.value]
  }
}

function clearSelection() {
  selectedFiles.value = []
}

// ── 排序 ──

function sortBy(field: 'name' | 'size' | 'modified') {
  if (sortField.value === field) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortDir.value = 'asc'
  }
}

// ── 图标 ──

function getIconClass(item: FileItem) {
  if (item.is_dir) return 'icon-folder'
  if (isMediaFile(item.name)) return 'icon-media'
  const ext = getFileExt(item.name)
  if (['srt', 'ass', 'ssa'].includes(ext)) return 'icon-subtitle'
  if (['jpg', 'jpeg', 'png', 'webp'].includes(ext)) return 'icon-image'
  return 'icon-file'
}

// ── 行内重命名 ──

function openRenameInline(item: FileItem) {
  inlineRenaming.value = item.path
  inlineRenameValue.value = item.name
  nextTick(() => {
    renameInputRef.value?.focus()
    renameInputRef.value?.select()
  })
}

function cancelInlineRename() {
  inlineRenaming.value = ''
  inlineRenameValue.value = ''
}

async function submitInlineRename(item: FileItem) {
  const newName = inlineRenameValue.value.trim()
  if (!newName || newName === item.name) {
    cancelInlineRename()
    return
  }
  try {
    if (item.is_dir) {
      await adminApi.renameFolder(item.path, newName)
    } else {
      await adminApi.renameFile(item.path, newName)
    }
    cancelInlineRename()
    await loadDirectory(currentPath.value)
    showToast('success', `已重命名为 ${newName}`)
  } catch (e: any) {
    showToast('error', e.response?.data?.detail || '重命名失败')
    cancelInlineRename()
  }
}

// ── 新建文件夹 ──

watch(showNewFolderModal, (val) => {
  if (val) {
    newFolderName.value = ''
    nextTick(() => newFolderInputRef.value?.focus())
  }
})

async function createFolder() {
  const name = newFolderName.value.trim()
  if (!name) return
  creatingFolder.value = true
  const fullPath = currentPath.value.replace(/\\/g, '/').replace(/\/$/, '') + '/' + name
  try {
    await adminApi.createFolder(fullPath)
    showNewFolderModal.value = false
    await loadDirectory(currentPath.value)
    showToast('success', `文件夹「${name}」创建成功`)
  } catch (e: any) {
    showToast('error', e.response?.data?.detail || '创建文件夹失败')
  } finally {
    creatingFolder.value = false
  }
}

// ── 删除 ──

function confirmDelete(item: FileItem) {
  deleteModal.value = {
    visible: true,
    items: [item],
    hasDirs: item.is_dir,
    force: false,
    loading: false,
  }
}

function confirmDeleteSelected() {
  deleteModal.value = {
    visible: true,
    items: [...selectedFiles.value],
    hasDirs: selectedFiles.value.some(f => f.is_dir),
    force: false,
    loading: false,
  }
}

async function executeDelete() {
  deleteModal.value.loading = true
  let success = 0
  let fail = 0

  for (const item of deleteModal.value.items) {
    try {
      if (item.is_dir) {
        await adminApi.deleteFolder(item.path, deleteModal.value.force)
      } else {
        await adminApi.deleteFile(item.path)
      }
      success++
    } catch (e: any) {
      fail++
      console.error(`删除失败 ${item.path}:`, e)
    }
  }

  deleteModal.value.visible = false
  deleteModal.value.loading = false

  if (success > 0) showToast('success', `成功删除 ${success} 个文件`)
  if (fail > 0) showToast('error', `${fail} 个文件删除失败`)

  await loadDirectory(currentPath.value)
}

// ── 批量重命名 ──

async function executeBatchRename() {
  const ops = batchRenamePreview.value
    .filter(p => p.newName !== p.oldName)
    .map(p => ({ path: p.path, new_name: p.newName }))

  if (ops.length === 0) return
  batchRename.value.executing = true

  try {
    const res = await adminApi.batchRename({ operations: ops, mode: 'execute' })
    const data = res.data
    showBatchRenamePanel.value = false
    await loadDirectory(currentPath.value)

    if (data.success_count > 0) showToast('success', `成功重命名 ${data.success_count} 个文件`)
    if (data.error_count > 0) showToast('error', `${data.error_count} 个文件重命名失败`)
  } catch (e: any) {
    showToast('error', e.response?.data?.detail || '批量重命名失败')
  } finally {
    batchRename.value.executing = false
  }
}

// ── AI 重命名 ──

function openAiRenamePanel() {
  aiRename.value.step = 'config'
  aiRename.value.response = null
  aiRename.value.selected = new Set()
  showAiRenamePanel.value = true
}

async function runAiRename() {
  aiRename.value.step = 'result'
  aiRename.value.loading = true
  aiRename.value.progress = 0

  try {
    const res = await adminApi.aiRename({
      paths: selectedFiles.value.map(f => f.path),
      style: aiRename.value.style,
      language: aiRename.value.language,
      extra_hint: aiRename.value.extraHint || undefined,
    })
    aiRename.value.response = res.data.data
    // 默认勾选置信度 >= 0.5 且无错误的建议
    aiRename.value.selected = new Set(
      res.data.data.candidates
        .filter(c => !c.error && c.confidence >= 0.5 && c.suggested !== c.original)
        .map(c => c.original_path),
    )
  } catch (e: any) {
    const msg = e.response?.status === 503
      ? 'AI 服务未配置，请在系统设置中配置 API Key'
      : (e.response?.data?.detail || 'AI 分析失败')
    showToast('error', msg)
    aiRename.value.step = 'config'
  } finally {
    aiRename.value.loading = false
  }
}

function toggleAiCandidate(candidate: AIRenameCandidate) {
  const set = new Set(aiRename.value.selected)
  if (set.has(candidate.original_path)) set.delete(candidate.original_path)
  else set.add(candidate.original_path)
  aiRename.value.selected = set
}

async function applyAiRename() {
  if (!aiRename.value.response) return
  const ops = aiRename.value.response.candidates
    .filter(c => aiRename.value.selected.has(c.original_path))
    .map(c => ({ path: c.original_path, new_name: c.suggested }))

  if (ops.length === 0) return

  try {
    const res = await adminApi.batchRename({ operations: ops, mode: 'execute' })
    const data = res.data
    showAiRenamePanel.value = false
    await loadDirectory(currentPath.value)

    if (data.success_count > 0) showToast('success', `AI 重命名成功 ${data.success_count} 个文件`)
    if (data.error_count > 0) showToast('error', `${data.error_count} 个文件重命名失败`)
  } catch (e: any) {
    showToast('error', e.response?.data?.detail || '应用 AI 重命名失败')
  }
}

// ── 右键菜单 ──

function openContextMenu(e: MouseEvent, item: FileItem) {
  contextMenu.value = { visible: true, x: e.clientX, y: e.clientY, item }
}

function closeContextMenu() {
  contextMenu.value.visible = false
}

function contextMenuAction(action: string) {
  const item = contextMenu.value.item
  closeContextMenu()
  if (!item) return
  if (action === 'open') {
    if (item.is_dir) navigate(item.path)
  } else if (action === 'rename') {
    openRenameInline(item)
  } else if (action === 'delete') {
    confirmDelete(item)
  }
}

// 点击其他区域关闭右键菜单
function handleGlobalClick() {
  if (contextMenu.value.visible) closeContextMenu()
}

// ── Toast ──

function showToast(type: 'success' | 'error' | 'info', message: string, duration = 3000) {
  const id = ++toastId
  toasts.value.push({ id, type, message })
  setTimeout(() => {
    const idx = toasts.value.findIndex(t => t.id === id)
    if (idx >= 0) toasts.value.splice(idx, 1)
  }, duration)
}

// ── Lifecycle ──────────────────────────────────────────────────────────────

onMounted(() => {
  loadMediaFolders()
  document.addEventListener('click', handleGlobalClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleGlobalClick)
})
</script>

<style scoped>
/* ═══════════════════════════════════════════════════════════
   文件管理器主布局
═══════════════════════════════════════════════════════════ */
.file-manager {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--color-bg, #0f1117);
  color: var(--color-text, #e2e8f0);
  font-family: system-ui, -apple-system, sans-serif;
  user-select: none;
}

/* ── 工具栏 ── */
.fm-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: var(--color-surface, #1a1f2e);
  border-bottom: 1px solid rgba(255,255,255,0.08);
  flex-shrink: 0;
}

.fm-breadcrumb {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
  min-width: 0;
}

.fm-path-chips {
  display: flex;
  align-items: center;
  gap: 2px;
  overflow: hidden;
}

.fm-path-seg {
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 13px;
  color: rgba(255,255,255,0.5);
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
}
.fm-path-seg:hover { color: rgba(255,255,255,0.9); background: rgba(255,255,255,0.05); }
.fm-path-seg.active { color: rgba(255,255,255,0.9); }
.fm-path-seg:not(:last-child)::after { content: ' /'; color: rgba(255,255,255,0.2); }

.fm-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

/* ── 搜索框 ── */
.fm-search {
  display: flex;
  align-items: center;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px;
  padding: 4px 10px;
  gap: 6px;
}
.fm-search svg { width: 14px; height: 14px; opacity: 0.5; flex-shrink: 0; }
.fm-search input {
  background: none;
  border: none;
  outline: none;
  color: inherit;
  font-size: 13px;
  width: 160px;
}
.fm-search input::placeholder { color: rgba(255,255,255,0.3); }

/* ── 视图切换 ── */
.fm-view-toggle {
  display: flex;
  background: rgba(255,255,255,0.05);
  border-radius: 6px;
  overflow: hidden;
}
.fm-view-toggle button {
  display: flex;
  align-items: center;
  padding: 5px 8px;
  background: none;
  border: none;
  color: rgba(255,255,255,0.4);
  cursor: pointer;
  transition: all 0.15s;
}
.fm-view-toggle button.active { color: #60a5fa; background: rgba(96,165,250,0.15); }
.fm-view-toggle button svg { width: 16px; height: 16px; }

/* ── 按钮 ── */
.fm-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: 7px;
  border: none;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.fm-btn svg { width: 14px; height: 14px; }
.fm-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.fm-btn-primary { background: #3b82f6; color: white; }
.fm-btn-primary:hover:not(:disabled) { background: #2563eb; }

.fm-btn-secondary { background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.8); }
.fm-btn-secondary:hover:not(:disabled) { background: rgba(255,255,255,0.12); }

.fm-btn-danger { background: rgba(239,68,68,0.2); color: #f87171; }
.fm-btn-danger:hover:not(:disabled) { background: rgba(239,68,68,0.3); }

.fm-btn-ai {
  background: linear-gradient(135deg, #7c3aed, #2563eb);
  color: white;
}
.fm-btn-ai:hover:not(:disabled) { filter: brightness(1.1); }

.fm-btn-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  background: none;
  border: none;
  border-radius: 6px;
  color: rgba(255,255,255,0.5);
  cursor: pointer;
  transition: all 0.15s;
}
.fm-btn-icon:hover:not(:disabled) { background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.9); }
.fm-btn-icon:disabled { opacity: 0.3; cursor: not-allowed; }
.fm-btn-icon svg { width: 16px; height: 16px; }

/* ── 操作按钮组 ── */
.fm-actions { display: flex; gap: 6px; align-items: center; }

/* ═══════════════════════════════════════════════════════════
   主体（侧边栏 + 内容）
═══════════════════════════════════════════════════════════ */
.fm-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* ── 侧边栏 ── */
.fm-sidebar {
  width: 220px;
  flex-shrink: 0;
  background: rgba(0,0,0,0.2);
  border-right: 1px solid rgba(255,255,255,0.06);
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
}
.fm-sidebar.collapsed {
  width: 44px;
}

.fm-sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 8px 4px;
  flex-shrink: 0;
}

.fm-sidebar-title {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(255,255,255,0.3);
  padding: 0 4px;
  white-space: nowrap;
  overflow: hidden;
}

.fm-sidebar-collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 5px;
  border: none;
  background: transparent;
  color: rgba(255,255,255,0.3);
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.15s;
}
.fm-sidebar-collapse-btn:hover { background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.7); }
.fm-sidebar-collapse-btn svg { width: 14px; height: 14px; transition: transform 0.2s; }
.fm-sidebar-collapse-btn svg.rotate-180 { transform: rotate(180deg); }

.fm-sidebar-section {
  padding: 4px 8px;
}

.fm-sidebar-section-title {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: rgba(255,255,255,0.2);
  padding: 4px 4px 4px;
  margin-top: 4px;
}

.fm-sidebar-tree-section {
  flex: 1;
  overflow: hidden;
  padding-top: 0;
}

.fm-sidebar-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  margin: 3px auto;
  border-radius: 7px;
  color: rgba(255,255,255,0.5);
  cursor: pointer;
  transition: all 0.15s;
}
.fm-sidebar-icon svg { width: 18px; height: 18px; }
.fm-sidebar-icon:hover { background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.9); }
.fm-sidebar-icon.active { background: rgba(59,130,246,0.15); color: #60a5fa; }

.fm-sidebar-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 7px;
  font-size: 12.5px;
  color: rgba(255,255,255,0.6);
  cursor: pointer;
  transition: all 0.15s;
  overflow: hidden;
}
.fm-sidebar-item span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fm-sidebar-item svg { width: 14px; height: 14px; flex-shrink: 0; }
.fm-sidebar-item:hover { background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.9); }
.fm-sidebar-item.active { background: rgba(59,130,246,0.15); color: #60a5fa; }

/* ── 内容区 ── */
.fm-content {
  flex: 1;
  overflow: auto;
  padding: 0;
  position: relative;
}

/* ── 加载 / 错误 / 空 ── */
.fm-loading, .fm-error, .fm-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 200px;
  color: rgba(255,255,255,0.4);
  font-size: 14px;
}
.fm-error { color: #f87171; }
.fm-error button {
  padding: 5px 14px;
  background: rgba(239,68,68,0.2);
  border: 1px solid rgba(239,68,68,0.3);
  border-radius: 6px;
  color: #f87171;
  cursor: pointer;
  font-size: 13px;
}
.fm-error svg, .fm-empty svg { width: 40px; height: 40px; opacity: 0.4; }

.fm-spinner {
  width: 32px; height: 32px;
  border: 2px solid rgba(255,255,255,0.1);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ═══════════════════════════════════════════════════════════
   列表视图
═══════════════════════════════════════════════════════════ */
.fm-list { width: 100%; }

.fm-list-header {
  display: grid;
  grid-template-columns: 36px 1fr 90px 140px 90px;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  background: rgba(0,0,0,0.2);
  position: sticky;
  top: 0;
  z-index: 10;
}

.fm-list-col {
  padding: 4px 10px;
  font-size: 12px;
  color: rgba(255,255,255,0.4);
}
.fm-col-check { padding: 4px 10px; display: flex; align-items: center; }
.fm-col-name { cursor: pointer; }
.fm-col-size { cursor: pointer; }
.fm-col-modified { cursor: pointer; }
.fm-col-actions { }

.sort-icon { font-size: 10px; margin-left: 2px; }

.fm-list-row {
  display: grid;
  grid-template-columns: 36px 1fr 90px 140px 90px;
  align-items: center;
  padding: 2px 0;
  border-bottom: 1px solid rgba(255,255,255,0.03);
  cursor: pointer;
  transition: background 0.1s;
}
.fm-list-row:hover { background: rgba(255,255,255,0.04); }
.fm-list-row.selected { background: rgba(59,130,246,0.1); }
.fm-list-row.selected:hover { background: rgba(59,130,246,0.15); }

.fm-item-name {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow: hidden;
}

.fm-icon { display: flex; flex-shrink: 0; }
.fm-icon svg { width: 18px; height: 18px; }
.icon-folder svg { color: #fbbf24; }
.icon-media svg { color: #a78bfa; }
.icon-subtitle svg { color: #34d399; }
.icon-image svg { color: #f472b6; }
.icon-file svg { color: rgba(255,255,255,0.4); }

.fm-name-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  color: rgba(255,255,255,0.85);
}
.fm-list-row.is-dir .fm-name-text { color: rgba(255,255,255,0.95); font-weight: 500; }

.fm-rename-input {
  background: rgba(255,255,255,0.08);
  border: 1px solid #3b82f6;
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 13px;
  color: inherit;
  outline: none;
  min-width: 200px;
}

.fm-list-col.fm-col-size,
.fm-list-col.fm-col-modified {
  font-size: 12px;
  color: rgba(255,255,255,0.4);
}

.fm-row-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.15s;
}
.fm-list-row:hover .fm-row-actions { opacity: 1; }
.fm-row-actions button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px; height: 26px;
  border: none;
  background: rgba(255,255,255,0.06);
  border-radius: 5px;
  color: rgba(255,255,255,0.5);
  cursor: pointer;
  transition: all 0.15s;
}
.fm-row-actions button:hover { background: rgba(255,255,255,0.12); color: rgba(255,255,255,0.9); }
.fm-row-actions button.danger:hover { background: rgba(239,68,68,0.2); color: #f87171; }
.fm-row-actions button svg { width: 13px; height: 13px; }

/* ═══════════════════════════════════════════════════════════
   网格视图
═══════════════════════════════════════════════════════════ */
.fm-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 8px;
  padding: 16px;
}

.fm-grid-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 12px 8px 8px;
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.05);
  cursor: pointer;
  transition: all 0.15s;
}
.fm-grid-item:hover { background: rgba(255,255,255,0.05); border-color: rgba(255,255,255,0.1); }
.fm-grid-item.selected { background: rgba(59,130,246,0.12); border-color: rgba(59,130,246,0.4); }

.fm-grid-icon svg { width: 40px; height: 40px; }
.fm-grid-item.is-dir .fm-grid-icon svg { color: #fbbf24; }
.fm-grid-item:not(.is-dir) .fm-grid-icon svg { color: #a78bfa; }

.fm-grid-name {
  font-size: 11px;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 100%;
  color: rgba(255,255,255,0.8);
}
.fm-grid-size { font-size: 10px; color: rgba(255,255,255,0.3); }

/* ═══════════════════════════════════════════════════════════
   状态栏
═══════════════════════════════════════════════════════════ */
.fm-statusbar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 5px 16px;
  background: var(--color-surface, #1a1f2e);
  border-top: 1px solid rgba(255,255,255,0.06);
  font-size: 12px;
  color: rgba(255,255,255,0.4);
  flex-shrink: 0;
}
.fm-statusbar-right { margin-left: auto; }
.fm-path-display {
  max-width: 400px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: monospace;
}

/* ═══════════════════════════════════════════════════════════
   右键菜单
═══════════════════════════════════════════════════════════ */
.fm-context-menu {
  position: fixed;
  z-index: 9999;
  background: #1e2535;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 10px;
  padding: 4px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.5);
  min-width: 150px;
}
.fm-ctx-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  color: rgba(255,255,255,0.8);
  cursor: pointer;
  transition: background 0.1s;
}
.fm-ctx-item:hover { background: rgba(255,255,255,0.06); }
.fm-ctx-item.danger { color: #f87171; }
.fm-ctx-item.danger:hover { background: rgba(239,68,68,0.1); }
.fm-ctx-item svg { width: 15px; height: 15px; }
.fm-ctx-sep { height: 1px; background: rgba(255,255,255,0.07); margin: 3px 8px; }

/* ═══════════════════════════════════════════════════════════
   Modal
═══════════════════════════════════════════════════════════ */
.fm-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  backdrop-filter: blur(4px);
  z-index: 9000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.fm-modal {
  background: #1e2535;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 14px;
  padding: 24px;
  min-width: 340px;
  max-width: 480px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.6);
}

.fm-modal-title {
  font-size: 16px;
  font-weight: 600;
  color: rgba(255,255,255,0.9);
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.fm-modal-danger .fm-modal-title { color: #f87171; }
.fm-modal-title svg { width: 20px; height: 20px; }

.fm-modal input {
  width: 100%;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 14px;
  color: inherit;
  outline: none;
  box-sizing: border-box;
  margin-bottom: 8px;
}
.fm-modal input:focus { border-color: #3b82f6; }

.fm-modal-body {
  font-size: 14px;
  color: rgba(255,255,255,0.7);
  line-height: 1.6;
  margin-bottom: 16px;
}
.fm-modal-body p { margin: 0 0 8px; }
.fm-modal-body strong { color: rgba(255,255,255,0.9); }
.fm-modal-warn { color: #fbbf24; }
.fm-modal-check {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}
.fm-modal-check input { width: auto; margin: 0; }

.fm-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

/* ═══════════════════════════════════════════════════════════
   面板 (侧滑面板)
═══════════════════════════════════════════════════════════ */
.fm-panel-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  backdrop-filter: blur(4px);
  z-index: 8000;
  display: flex;
  align-items: stretch;
  justify-content: flex-end;
}

.fm-panel {
  width: 600px;
  max-width: 90vw;
  background: #1a1f2e;
  border-left: 1px solid rgba(255,255,255,0.08);
  display: flex;
  flex-direction: column;
  box-shadow: -20px 0 60px rgba(0,0,0,0.4);
}

.fm-panel-ai { width: 700px; }

.fm-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  font-size: 15px;
  font-weight: 600;
  flex-shrink: 0;
}

.fm-panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.fm-panel-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid rgba(255,255,255,0.06);
  flex-shrink: 0;
}

/* ── 批量重命名面板 ── */
.fm-rename-rule { margin-bottom: 16px; }

.fm-form-row {
  display: grid;
  grid-template-columns: 80px 1fr;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.fm-form-row label { font-size: 13px; color: rgba(255,255,255,0.5); }
.fm-form-row input, .fm-form-row select {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 7px;
  padding: 6px 10px;
  font-size: 13px;
  color: inherit;
  outline: none;
}
.fm-form-row input:focus, .fm-form-row select:focus { border-color: #3b82f6; }
.fm-form-row select option { background: #1a1f2e; }

.fm-rename-preview { }
.fm-rename-preview-header {
  font-size: 12px;
  color: rgba(255,255,255,0.4);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.fm-rename-preview-list { display: flex; flex-direction: column; gap: 4px; }
.fm-rename-preview-row {
  display: grid;
  grid-template-columns: 1fr 20px 1fr auto;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: rgba(255,255,255,0.03);
  border-radius: 6px;
  font-size: 12px;
}
.fm-rename-preview-row.conflict { background: rgba(239,68,68,0.06); }
.fm-rename-preview-row svg { width: 14px; height: 14px; color: rgba(255,255,255,0.3); }
.fm-rename-preview-row .old-name { color: rgba(255,255,255,0.6); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fm-rename-preview-row .new-name { color: #60a5fa; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fm-rename-preview-row .new-name.unchanged { color: rgba(255,255,255,0.3); }
.conflict-badge { background: rgba(239,68,68,0.2); color: #f87171; padding: 1px 6px; border-radius: 4px; font-size: 11px; flex-shrink: 0; }

/* ── AI 重命名面板 ── */
.fm-ai-config { display: flex; flex-direction: column; gap: 8px; }
.fm-ai-files { margin-top: 16px; }
.fm-ai-files-title { font-size: 12px; color: rgba(255,255,255,0.4); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.06em; }
.fm-ai-files-list {
  max-height: 200px;
  overflow-y: auto;
  background: rgba(0,0,0,0.2);
  border-radius: 8px;
  padding: 6px;
}
.fm-ai-file-item {
  padding: 4px 8px;
  font-size: 12px;
  color: rgba(255,255,255,0.5);
  font-family: monospace;
}

.fm-ai-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 60px 0;
  color: rgba(255,255,255,0.5);
}
.fm-spinner-ai {
  width: 40px; height: 40px;
  border-color: rgba(139,92,246,0.2);
  border-top-color: #8b5cf6;
}

.fm-ai-result-summary {
  font-size: 12px;
  color: rgba(255,255,255,0.4);
  margin-bottom: 12px;
  padding: 8px 12px;
  background: rgba(255,255,255,0.03);
  border-radius: 6px;
}
.fm-ai-result-summary strong { color: rgba(255,255,255,0.7); }

.fm-ai-results { display: flex; flex-direction: column; gap: 6px; }

.fm-ai-candidate {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 8px;
  padding: 10px 12px;
  transition: border-color 0.15s;
}
.fm-ai-candidate:hover { border-color: rgba(255,255,255,0.1); }
.fm-ai-candidate.has-error { border-color: rgba(239,68,68,0.2); }
.fm-ai-candidate.has-conflict { border-color: rgba(251,191,36,0.25); }

.fm-ai-cand-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.fm-ai-cand-check input { cursor: pointer; }
.fm-ai-cand-names {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 20px 1fr;
  align-items: center;
  gap: 6px;
  overflow: hidden;
}
.fm-ai-cand-names svg { width: 14px; height: 14px; color: rgba(255,255,255,0.3); flex-shrink: 0; }
.fm-ai-cand-names .old-name {
  font-size: 12px;
  color: rgba(255,255,255,0.5);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fm-ai-cand-names .new-name {
  font-size: 12px;
  color: #60a5fa;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fm-ai-cand-meta {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
}
.confidence-badge {
  padding: 2px 7px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}
.confidence-badge.high { background: rgba(52,211,153,0.15); color: #34d399; }
.confidence-badge.medium { background: rgba(251,191,36,0.15); color: #fbbf24; }
.confidence-badge.low { background: rgba(239,68,68,0.15); color: #f87171; }
.warning-badge { background: rgba(251,191,36,0.15); color: #fbbf24; padding: 2px 7px; border-radius: 10px; font-size: 11px; }
.error-badge { background: rgba(239,68,68,0.15); color: #f87171; padding: 2px 7px; border-radius: 10px; font-size: 11px; max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fm-ai-cand-reason { font-size: 11px; color: rgba(255,255,255,0.35); margin-top: 5px; padding-left: 26px; }

/* ═══════════════════════════════════════════════════════════
   Toast
═══════════════════════════════════════════════════════════ */
.fm-toast-container {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 99999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}
.fm-toast {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 10px;
  font-size: 13px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4);
  pointer-events: auto;
}
.fm-toast svg { width: 16px; height: 16px; flex-shrink: 0; }
.fm-toast.success { background: #0f4c3a; border: 1px solid #34d399; color: #6ee7b7; }
.fm-toast.error { background: #4c0f0f; border: 1px solid #f87171; color: #fca5a5; }
.fm-toast.info { background: #1e3a5f; border: 1px solid #60a5fa; color: #93c5fd; }

.fm-toast-enter-active, .fm-toast-leave-active { transition: all 0.25s ease; }
.fm-toast-enter-from { opacity: 0; transform: translateX(20px); }
.fm-toast-leave-to { opacity: 0; transform: translateX(20px); }

/* ── Checkbox 样式 ── */
input[type="checkbox"] {
  width: 14px;
  height: 14px;
  cursor: pointer;
  accent-color: #3b82f6;
}
</style>
