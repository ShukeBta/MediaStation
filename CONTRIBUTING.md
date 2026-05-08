# 贡献指南

感谢您对 MediaStation 项目的兴趣！我们欢迎各种形式的贡献。

## 📋 如何贡献

### 报告 Bug

1. 在 GitHub Issues 中搜索是否已有相同的 bug 报告
2. 如果没有，创建一个新的 Issue
3. 使用 Bug Report 模板，提供详细信息：
   - 问题描述
   - 复现步骤
   - 预期行为 vs 实际行为
   - 环境信息（OS、Python/Node 版本等）
   - 截图或日志

### 功能建议

1. 在 GitHub Issues 中搜索是否已有相同建议
2. 创建一个新的 Feature Request
3. 详细描述：
   - 解决的问题或需求
   - 建议的解决方案
   - 可能的替代方案

### 提交代码

1. **Fork 仓库**
   ```bash
   git clone https://github.com/ShukeBta/MediaStation.git
   cd MediaStation
   ```

2. **创建分支**
   ```bash
   git checkout -b feature/your-feature-name
   # 或
   git checkout -b fix/your-bug-fix
   ```

3. **进行开发**
   ```bash
   # 后端开发
   cd backend
   pip install -r requirements.txt
   
   # 前端开发
   cd frontend
   npm install
   ```

4. **提交更改**
   ```bash
   git add .
   git commit -m 'Add: 添加新功能描述'
   git push origin feature/your-feature-name
   ```

5. **创建 Pull Request**
   - 使用清晰的标题和描述
   - 关联相关的 Issue
   - 等待代码审查

## 📐 代码规范

### Python (后端)

- 遵循 PEP 8 规范
- 使用类型提示 (Type Hints)
- 编写 Docstrings
- 单元测试覆盖

```python
def example_function(param: str, options: dict = None) -> bool:
    """
    函数简短描述。
    
    Args:
        param: 参数说明
        options: 可选配置
        
    Returns:
        执行结果
        
    Raises:
        ValueError: 当参数无效时
    """
    if not param:
        raise ValueError("参数不能为空")
    return True
```

### TypeScript (前端)

- 遵循 ESLint 规则
- 使用强类型
- 组件使用 Composition API
- 清晰的命名约定

```typescript
interface User {
  id: number;
  name: string;
  email: string;
}

export function getUserById(id: number): Promise<User> {
  return api.get(`/users/${id}`);
}
```

### Vue 组件

- 使用 `<script setup>` 语法
- Props 定义类型
- Emits 定义类型
- 良好的注释

```vue
<script setup lang="ts">
interface Props {
  title: string;
  count?: number;
}

const props = withDefaults(defineProps<Props>(), {
  count: 0
});

const emit = defineEmits<{
  (e: 'update', value: number): void;
}>();
</script>
```

## 🧪 测试

### 运行测试

```bash
# 后端测试
cd backend
pytest tests/ -v

# 前端测试
cd frontend
npm run test
```

### 编写测试

- 新功能必须有对应的测试
- Bug 修复必须有回归测试
- 测试覆盖关键业务逻辑

## 🔍 代码审查

审查清单：

- [ ] 代码是否符合项目规范
- [ ] 是否有适当的注释和文档
- [ ] 是否有单元测试
- [ ] 是否有性能问题
- [ ] 是否有安全隐患
- [ ] 更改是否向后兼容

## 📝 提交信息规范

使用语义化提交信息：

```
feat: 新功能
fix: 错误修复
docs: 文档更新
style: 代码格式（不影响功能）
refactor: 重构
perf: 性能优化
test: 测试相关
chore: 构建/工具变更
```

示例：
```
feat: 添加 MTeam API 支持

- 实现 OAuth 登录
- 添加资源搜索功能
- 实现自动订阅下载

Closes #123
```

## 🐛 开发流程

1. **克隆并安装**
   ```bash
   git clone https://github.com/ShukeBta/MediaStation.git
   cd MediaStation
   ```

2. **设置开发环境**
   ```bash
   # 后端
   cd backend
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   
   # 前端
   cd frontend
   npm install
   ```

3. **运行开发服务器**
   ```bash
   # 后端
   cd backend
   uvicorn app.main:app --reload --port 3002
   
   # 前端 (新终端)
   cd frontend
   npm run dev
   ```

4. **进行更改并测试**

5. **提交 Pull Request**

## ❓ 问题？

如果您有任何问题：

- 📧 发送邮件至：support@mediastation.dev
- 💬 提交 GitHub Issue

## 📜 许可证

通过贡献代码，您同意您的代码将在 BSL 1.1 许可证下发布。
