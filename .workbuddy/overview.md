# MediaStation — 本次会话总结

## 完成内容

### 1. 部署预览
- 发现服务残留在旧进程（PID），使用 PowerShell `Get-NetTCPConnection` + `Stop-Process` 清理
- 重建前端（零错误），同步静态文件到 `backend/static/`，重启后端于 http://localhost:3001
- 验证所有核心 API 正常（认证、媒体库、调度器、配置接口）

### 2. 用户管理功能（新增）

#### 后端
| 文件 | 改动 |
|------|------|
| `user/schemas.py` | 新增 `ChangePasswordRequest`、`UpdateProfileRequest` |
| `user/service.py` | 新增 `change_password()`（验证旧密码）、`update_profile()` |
| `user/router.py` | 新增 `POST /api/auth/change-password`、`PATCH /api/auth/profile` |

#### 前端
| 文件 | 改动 |
|------|------|
| `api/auth.ts` | 新增 `changePassword`、`updateProfile`、`userApi`（完整 CRUD） |
| `components/settings/AccountTab.vue` | **全新**：账号信息、头像上传（base64）、修改密码（眼睛切换可见性） |
| `components/settings/UsersTab.vue` | **全新**：用户列表、创建/编辑/启用禁用/删除，保护自己不被删 |
| `views/SettingsView.vue` | 重构为动态 tabs（管理员专属 tab 按角色过滤），默认 Tab 改为「我的账号」 |

## 当前服务状态
- **URL**: http://localhost:3001
- **账号**: admin / admin123
- **PID**: 25284 (python/uvicorn)
- **后端路由**: 67 条

## 下一步建议
1. 站点资源搜索页（手动搜索 + 一键下载）
2. 下载完成后自动入库扫描 + TMDb 刮削 + 通知推送
3. 仪表盘增强（活跃下载列表、最近观看记录、正在转码任务）
