<template>
  <main class="auth-page">
    <div class="orb" style="width:500px;height:500px;background:radial-gradient(circle,rgba(56,189,248,0.12) 0%,transparent 70%);top:-100px;right:-150px;pointer-events:none;"></div>

    <div class="auth-container">
      <!-- Left Panel -->
      <div class="auth-left">
        <RouterLink to="/" class="auth-logo">
          <svg width="32" height="32" viewBox="0 0 28 28" fill="none">
            <path d="M14 2L25 8V20L14 26L3 20V8L14 2Z" stroke="url(#rlg)" stroke-width="1.5" fill="rgba(99,102,241,0.15)"/>
            <path d="M14 8L19 11V17L14 20L9 17V11L14 8Z" fill="url(#rlg)"/>
            <defs>
              <linearGradient id="rlg" x1="3" y1="2" x2="25" y2="26" gradientUnits="userSpaceOnUse">
                <stop stop-color="#38bdf8"/><stop offset="1" stop-color="#a78bfa"/>
              </linearGradient>
            </defs>
          </svg>
          <span>NexusAI</span>
        </RouterLink>

        <div class="auth-left-content">
          <h2>加入 NexusAI</h2>
          <p>免费注册，立享体验额度。无需信用卡，30秒快速开始。</p>

          <div class="perks">
            <div v-for="perk in perks" :key="perk.text" class="perk-item">
              <span class="perk-icon">{{ perk.icon }}</span>
              <span>{{ perk.text }}</span>
            </div>
          </div>
        </div>

        <div class="stats-row">
          <div v-for="s in stats" :key="s.label" class="mini-stat">
            <span class="mini-stat-num">{{ s.num }}</span>
            <span class="mini-stat-label">{{ s.label }}</span>
          </div>
        </div>
      </div>

      <!-- Right Panel -->
      <div class="auth-right">
        <div class="auth-form-wrap">
          <h1 class="auth-title">创建账号</h1>
          <p class="auth-subtitle">已有账号？<RouterLink to="/login" class="auth-link">立即登录</RouterLink></p>

          <!-- <div class="oauth-btns">
            <button class="oauth-btn">
              <svg width="18" height="18" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
              使用 Google 注册
            </button>
          </div> -->

          <div class="divider"><span>或使用邮箱注册</span></div>

          <form @submit.prevent="handleRegister" class="auth-form">
            <div class="form-row">
              <div class="form-group">
                <label>姓名</label>
                <input v-model="form.name" type="text" class="input-field" placeholder="你的名字" required />
              </div>
              <div class="form-group">
                <label>手机号（可选）</label>
                <input v-model="form.phone" type="tel" class="input-field" placeholder="+86 138..." />
              </div>
            </div>
            <div class="form-group">
              <label>邮箱地址</label>
              <input v-model="form.email" type="email" class="input-field" placeholder="your@email.com" required />
            </div>
            <div class="form-group">
              <label>设置密码</label>
              <div class="password-wrap">
                <input v-model="form.password" :type="showPwd ? 'text' : 'password'" class="input-field" placeholder="至少 8 位，包含字母和数字" required />
                <button type="button" class="pwd-toggle" @click="showPwd = !showPwd">
                  <svg v-if="!showPwd" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                  <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                </button>
              </div>
              <!-- Password strength -->
              <div class="pwd-strength" v-if="form.password">
                <div v-for="i in 4" :key="i" class="strength-bar" :class="{ active: pwdStrength >= i, [`level-${pwdStrength}`]: true }"></div>
                <span class="strength-label" :class="`text-level-${pwdStrength}`">{{ strengthLabel }}</span>
              </div>
            </div>

            <!-- Invite Code -->
            <div class="form-group">
              <label>邀请码（可选）</label>
              <input v-model="form.invite" type="text" class="input-field" placeholder="输入邀请码享额外奖励" />
            </div>

            <label class="checkbox-wrap">
              <input type="checkbox" v-model="agreed" required />
              <span class="checkmark"></span>
              <span>我已阅读并同意 <a href="#" class="auth-link">服务条款</a> 和 <a href="#" class="auth-link">隐私政策</a></span>
            </label>

            <div v-if="error" class="error-msg">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              {{ error }}
            </div>

            <button type="submit" class="btn btn-primary submit-btn" :disabled="loading || !agreed">
              <span v-if="loading" class="loading-dot"></span>
              {{ loading ? '注册中...' : '免费创建账号' }}
            </button>
          </form>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const form = ref({ name: '', phone: '', email: '', password: '', invite: '' })
const showPwd = ref(false)
const agreed = ref(false)
const loading = ref(false)
const error = ref('')

const perks = [
  { icon: '🎁', text: '新用户注册即送 50 万 Token 体验额度' },
  { icon: '⚡', text: '立即访问 GPT-4o、Claude、Gemini' },
  { icon: '🔒', text: '数据加密保护，隐私安全保障' },
  { icon: '🌍', text: '国内直连，无需 VPN，随时可用' },
  { icon: '💳', text: '免费计划永久有效，无需信用卡' },
]

const stats = [
  { num: '10万+', label: '注册用户' },
  { num: '50+', label: 'AI 模型' },
  { num: '99.9%', label: '可用率' },
]

const pwdStrength = computed(() => {
  const pwd = form.value.password
  if (!pwd) return 0
  let score = 0
  if (pwd.length >= 8) score++
  if (/[A-Z]/.test(pwd)) score++
  if (/[0-9]/.test(pwd)) score++
  if (/[^A-Za-z0-9]/.test(pwd)) score++
  return score
})
const strengthLabel = computed(() => ['', '弱', '一般', '强', '非常强'][pwdStrength.value])

async function handleRegister() {
  loading.value = true
  error.value = ''
  try {
    // TODO: Connect to your OpenWebUI registration API
    // const res = await fetch('/api/auth/register', { method: 'POST', body: JSON.stringify(form.value) })
    await new Promise(r => setTimeout(r, 1500))
    router.push('/login')
  } catch (e) {
    error.value = '注册失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex; align-items: center; justify-content: center;
  padding: 80px 24px;
  position: relative; overflow: hidden;
}
.auth-container {
  display: grid;
  grid-template-columns: 1fr 1.2fr;
  width: 100%; max-width: 1000px;
  background: var(--gradient-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  overflow: hidden;
  box-shadow: 0 40px 100px rgba(0,0,0,0.5);
}
.auth-left {
  background: linear-gradient(135deg, rgba(56,189,248,0.08), rgba(99,102,241,0.05));
  border-right: 1px solid var(--border);
  padding: 48px;
  display: flex; flex-direction: column; gap: 40px;
}
.auth-logo {
  display: flex; align-items: center; gap: 10px;
  text-decoration: none;
  font-family: var(--font-display); font-size: 20px; font-weight: 800;
  background: var(--gradient-text);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.auth-left-content { flex: 1; }
.auth-left-content h2 { font-family: var(--font-display); font-size: 28px; font-weight: 800; margin-bottom: 12px; }
.auth-left-content p { color: var(--text-secondary); font-size: 15px; line-height: 1.7; margin-bottom: 28px; }
.perks { display: flex; flex-direction: column; gap: 14px; }
.perk-item { display: flex; align-items: center; gap: 12px; font-size: 14px; color: var(--text-secondary); }
.perk-icon { font-size: 20px; width: 24px; flex-shrink: 0; }
.stats-row { display: flex; gap: 0; background: rgba(255,255,255,0.04); border: 1px solid var(--border); border-radius: var(--radius-md); overflow: hidden; }
.mini-stat { flex: 1; padding: 16px; text-align: center; display: flex; flex-direction: column; gap: 4px; }
.mini-stat:not(:last-child) { border-right: 1px solid var(--border); }
.mini-stat-num { font-family: var(--font-display); font-size: 20px; font-weight: 800; background: var(--gradient-text); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.mini-stat-label { font-size: 11px; color: var(--text-muted); }

.auth-right { padding: 48px; display: flex; align-items: center; justify-content: center; }
.auth-form-wrap { width: 100%; max-width: 400px; }
.auth-title { font-family: var(--font-display); font-size: 28px; font-weight: 800; margin-bottom: 8px; }
.auth-subtitle { font-size: 14px; color: var(--text-secondary); margin-bottom: 24px; }
.auth-link { color: var(--accent-cyan); text-decoration: none; font-weight: 500; }

.oauth-btns { margin-bottom: 20px; }
.oauth-btn {
  width: 100%; padding: 12px;
  background: rgba(255,255,255,0.05); border: 1px solid var(--border); border-radius: var(--radius-md);
  color: var(--text-primary); font-size: 14px; font-weight: 500; cursor: pointer;
  transition: var(--transition); display: flex; align-items: center; justify-content: center; gap: 10px;
  font-family: var(--font-body);
}
.oauth-btn:hover { background: rgba(255,255,255,0.09); }

.divider { position: relative; text-align: center; margin: 4px 0 18px; }
.divider::before { content: ''; position: absolute; top: 50%; left: 0; right: 0; height: 1px; background: var(--border); }
.divider span { position: relative; background: var(--bg-card); padding: 0 12px; font-size: 12px; color: var(--text-muted); }

.auth-form { display: flex; flex-direction: column; gap: 14px; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.form-group { display: flex; flex-direction: column; gap: 7px; }
.form-group label { font-size: 13px; font-weight: 500; color: var(--text-secondary); }
.password-wrap { position: relative; }
.pwd-toggle { position: absolute; right: 14px; top: 50%; transform: translateY(-50%); background: none; border: none; color: var(--text-muted); cursor: pointer; padding: 4px; transition: var(--transition); }
.pwd-toggle:hover { color: var(--text-primary); }

.pwd-strength { display: flex; align-items: center; gap: 6px; margin-top: 8px; }
.strength-bar { flex: 1; height: 3px; background: var(--border); border-radius: 2px; transition: var(--transition); }
.strength-bar.active.level-1 { background: #ef4444; }
.strength-bar.active.level-2 { background: #f97316; }
.strength-bar.active.level-3 { background: #eab308; }
.strength-bar.active.level-4 { background: #34d399; }
.strength-label { font-size: 11px; white-space: nowrap; }
.text-level-1 { color: #ef4444; }
.text-level-2 { color: #f97316; }
.text-level-3 { color: #eab308; }
.text-level-4 { color: #34d399; }

.checkbox-wrap {
  display: flex; align-items: flex-start; gap: 10px; cursor: pointer;
  font-size: 13px; color: var(--text-secondary); line-height: 1.5;
}
.checkbox-wrap input { display: none; }
.checkmark {
  width: 18px; height: 18px; min-width: 18px;
  background: rgba(255,255,255,0.05); border: 1px solid var(--border); border-radius: 4px;
  display: flex; align-items: center; justify-content: center; transition: var(--transition);
}
.checkbox-wrap input:checked + .checkmark { background: var(--accent-blue); border-color: var(--accent-blue); }
.checkbox-wrap input:checked + .checkmark::after { content: '✓'; font-size: 11px; color: #fff; font-weight: 700; }

.error-msg {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 16px; background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.2);
  border-radius: var(--radius-sm); font-size: 13px; color: #f87171;
}
.submit-btn { width: 100%; justify-content: center; padding: 14px; font-size: 15px; }
.submit-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.loading-dot {
  width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff;
  border-radius: 50%; animation: spin-slow 0.7s linear infinite;
}

@media (max-width: 768px) {
  .auth-container { grid-template-columns: 1fr; }
  .auth-left { display: none; }
  .form-row { grid-template-columns: 1fr; }
}
</style>
