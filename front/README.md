# NexusAI Portal — Vue3 + Vite

一站式 AI 门户网站，对接 OpenWebUI，支持模型展示、登录注册、套餐购买。

## 快速启动

```bash
npm install
npm run dev
```

## 项目结构

```
src/
├── components/
│   ├── AppNav.vue        # 顶部导航栏（固定吸顶）
│   └── AppFooter.vue     # 页脚
├── views/
│   ├── Home.vue          # 首页（Hero + 模型展示 + 功能 + FAQ）
│   ├── Models.vue        # 模型广场（筛选 + 完整列表）
│   ├── Pricing.vue       # 定价方案（月付/年付切换 + 套餐对比）
│   ├── Login.vue         # 登录页
│   └── Register.vue      # 注册页
├── router/index.js       # 路由配置
├── styles/global.css     # 全局样式 + Design Token
└── main.js
```

## 对接 OpenWebUI

### 登录/注册 API
在 `Login.vue` 和 `Register.vue` 中找到 `handleLogin` / `handleRegister` 函数，替换注释处的 fetch 调用：

```js
// Login.vue handleLogin()
const res = await fetch('/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: form.value.email, password: form.value.password })
})
const data = await res.json()
// 登录成功后跳转到 OpenWebUI
window.location.href = 'http://your-openwebui-url'
```

### Vite 代理配置
`vite.config.js` 中已预配置代理，修改 target 为你的 OpenWebUI 地址：

```js
proxy: {
  '/api': {
    target: 'http://your-openwebui-url',
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, '')
  }
}
```

## 自定义品牌

1. **网站名称**：全局搜索替换 `NexusAI` 为你的品牌名
2. **颜色主题**：修改 `src/styles/global.css` 中的 CSS 变量
3. **模型列表**：修改 `Models.vue` 中的 `allModels` 数组
4. **定价方案**：修改 `Pricing.vue` 中的 `plans` 数组
5. **ICP 备案号**：修改 `AppFooter.vue` 底部

## 支付集成建议

- **支付宝/微信支付**：接入对应官方 SDK，在购买套餐时调用
- **套餐购买**：在 `Pricing.vue` 的"立即订阅"按钮添加跳转至支付页逻辑
- **额度系统**：建议自建后端记录用户 Token 消耗，或使用 OpenWebUI 内置额度管理

## 生产构建

```bash
npm run build    # 输出到 dist/
npm run preview  # 本地预览构建产物
```
