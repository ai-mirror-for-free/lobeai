<template>
  <footer class="footer">
    <div class="container">
      <div class="footer-grid">
        <!-- Brand -->
        <div class="footer-brand">
          <div class="logo" style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
              <path d="M14 2L25 8V20L14 26L3 20V8L14 2Z" stroke="url(#fg)" stroke-width="1.5" fill="rgba(99,102,241,0.15)"/>
              <path d="M14 8L19 11V17L14 20L9 17V11L14 8Z" fill="url(#fg)"/>
              <defs>
                <linearGradient id="fg" x1="3" y1="2" x2="25" y2="26" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#38bdf8"/><stop offset="1" stop-color="#a78bfa"/>
                </linearGradient>
              </defs>
            </svg>
            <span style="font-family:var(--font-display);font-size:20px;font-weight:800;background:var(--gradient-text);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">NexusAI</span>
          </div>
          <p class="footer-desc">下一代 AI 智能平台，汇聚全球顶级模型，赋能每一个创想。</p>
          <div class="social-links">
            <a href="#" class="social-btn" aria-label="GitHub">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>
            </a>
            <a href="#" class="social-btn" aria-label="Twitter/X">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
            </a>
            <a href="#" class="social-btn" aria-label="Discord">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03z"/></svg>
            </a>
          </div>
        </div>

        <!-- Links -->
        <div class="footer-col">
          <h4>产品</h4>
          <ul>
            <li><RouterLink to="/models">模型广场</RouterLink></li>
            <li><RouterLink to="/pricing">定价方案</RouterLink></li>
            <li><a href="#">API 文档</a></li>
            <li><a href="#">更新日志</a></li>
          </ul>
        </div>
        <div class="footer-col">
          <h4>支持</h4>
          <ul>
            <li><a href="#">帮助中心</a></li>
            <li><a href="#">联系我们</a></li>
            <li><a href="#">服务状态</a></li>
            <li><a href="#">社区论坛</a></li>
          </ul>
        </div>
        <div class="footer-col">
          <h4>关于</h4>
          <ul>
            <li><a href="#">关于我们</a></li>
            <li><a href="#">隐私政策</a></li>
            <li><a href="#">服务条款</a></li>
            <li><a href="#">合规信息</a></li>
          </ul>
        </div>
      </div>

      <div class="footer-bottom">
        <p>© 2025 NexusAI. 保留所有权利。</p>
        <p>ICP备XXXXXXXX号</p>
      </div>
    </div>
  </footer>
</template>

<style scoped>
.footer {
  background: var(--bg-secondary);
  border-top: 1px solid var(--border);
  padding: 72px 0 32px;
  margin-top: auto;
}
.footer-grid {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr;
  gap: 48px;
  margin-bottom: 48px;
}
.footer-desc {
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.7;
  max-width: 260px;
  margin-bottom: 24px;
}
.social-links { display: flex; gap: 12px; }
.social-btn {
  width: 38px;
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255,255,255,0.05);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  transition: var(--transition);
}
.social-btn:hover {
  color: var(--text-primary);
  background: rgba(255,255,255,0.1);
  border-color: var(--border-glow);
}
.footer-col h4 {
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 20px;
}
.footer-col ul { list-style: none; display: flex; flex-direction: column; gap: 12px; }
.footer-col a {
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  transition: var(--transition);
}
.footer-col a:hover { color: var(--text-primary); }
.footer-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 32px;
  border-top: 1px solid var(--border);
  color: var(--text-muted);
  font-size: 13px;
}
@media (max-width: 900px) {
  .footer-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 500px) {
  .footer-grid { grid-template-columns: 1fr; }
  .footer-bottom { flex-direction: column; gap: 8px; text-align: center; }
}
</style>
