<template>
  <nav class="nav" :class="{ scrolled: isScrolled }">
    <div class="container nav-inner">
      <!-- Logo -->
      <RouterLink to="/" class="logo">
        <div class="logo-icon">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <path d="M14 2L25 8V20L14 26L3 20V8L14 2 25 8Z" stroke="url(#logoGrad)" stroke-width="1.5" fill="rgba(99,102,241,0.15)"/>
            <path d="M14 8L19 11V17L14 20L9 17V11L14 8Z" fill="url(#logoGrad)"/>
            <defs>
              <linearGradient id="logoGrad" x1="3" y1="2" x2="25" y2="26" gradientUnits="userSpaceOnUse">
                <stop stop-color="#38bdf8"/>
                <stop offset="1" stop-color="#a78bfa"/>
              </linearGradient>
            </defs>
          </svg>
        </div>
        <span class="logo-text">NexusAI</span>
      </RouterLink>

      <!-- Desktop Nav -->
      <ul class="nav-links">
        <li><RouterLink to="/models" class="nav-link">模型广场</RouterLink></li>
        <li><RouterLink to="/pricing" class="nav-link">定价方案</RouterLink></li>
        <li><a href="#features" class="nav-link">功能特性</a></li>
        <li><a href="#faq" class="nav-link">常见问题</a></li>
      </ul>

      <!-- Actions -->
      <div class="nav-actions">
        <!-- 如果用户已登录，显示个人主页链接 -->
        <template v-if="userStore.state.isLoggedIn">
          <RouterLink to="/profile" class="btn btn-ghost">个人中心</RouterLink>
          <button @click="handleLogout" class="btn btn-primary">退出登录</button>
        </template>
        <template v-else>
          <RouterLink to="/login" class="btn btn-ghost">登录</RouterLink>
          <!-- <RouterLink to="/login" class="btn btn-primary">开始体验</RouterLink> -->
        </template>
      </div>

      <!-- Mobile Menu Toggle -->
      <button class="mobile-toggle" @click="mobileOpen = !mobileOpen" aria-label="Menu">
        <span :class="{ open: mobileOpen }"></span>
        <span :class="{ open: mobileOpen }"></span>
        <span :class="{ open: mobileOpen }"></span>
      </button>
    </div>

    <!-- Mobile Menu -->
    <div class="mobile-menu" :class="{ open: mobileOpen }">
      <RouterLink to="/models" class="mobile-link" @click="mobileOpen=false">模型广场</RouterLink>
      <RouterLink to="/pricing" class="mobile-link" @click="mobileOpen=false">定价方案</RouterLink>
      <a href="#features" class="mobile-link" @click="mobileOpen=false">功能特性</a>
      <a href="#faq" class="mobile-link" @click="mobileOpen=false">常见问题</a>
      
      <template v-if="userStore.state.isLoggedIn">
        <RouterLink to="/profile" class="mobile-link" @click="mobileOpen=false">个人中心</RouterLink>
        <div class="mobile-actions">
          <button @click="handleLogoutAndCloseMenu" class="btn btn-primary" style="width:100%;justify-content:center">退出登录</button>
        </div>
      </template>
      <template v-else>
        <div class="mobile-actions">
          <RouterLink to="/login" class="btn btn-outline" style="width:100%;justify-content:center" @click="mobileOpen=false">登录</RouterLink>
          <!-- <RouterLink to="/register" class="btn btn-primary" style="width:100%;justify-content:center" @click="mobileOpen=false">开始体验</RouterLink> -->
        </div>
      </template>
    </div>
  </nav>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const isScrolled = ref(false)
const mobileOpen = ref(false)
const router = useRouter()
const userStore = useUserStore()

function handleScroll() {
  isScrolled.value = window.scrollY > 20
}

function handleLogout() {
  userStore.logout()
  router.push('/')
}

function handleLogoutAndCloseMenu() {
  handleLogout()
  mobileOpen.value = false
}

onMounted(() => {
  window.addEventListener('scroll', handleScroll)
  // 在实际应用中，这里应该检查用户的认证状态
  // 例如从localStorage、Vuex store或API检查认证状态
})
onUnmounted(() => window.removeEventListener('scroll', handleScroll))
</script>

<style scoped>
.nav {
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: 1000;
  transition: var(--transition);
  padding: 16px 0;
}
.nav.scrolled {
  background: rgba(2, 4, 9, 0.85);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
  padding: 12px 0;
}

.nav-inner {
  display: flex;
  align-items: center;
  gap: 32px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  flex-shrink: 0;
}
.logo-icon { display: flex; align-items: center; }
.logo-text {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 800;
  background: var(--gradient-text);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 4px;
  list-style: none;
  margin-left: auto;
}
.nav-link {
  padding: 8px 16px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  border-radius: var(--radius-sm);
  transition: var(--transition);
}
.nav-link:hover, .nav-link.router-link-active {
  color: var(--text-primary);
  background: rgba(255,255,255,0.06);
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.mobile-toggle {
  display: none;
  flex-direction: column;
  gap: 5px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  margin-left: auto;
}
.mobile-toggle span {
  display: block;
  width: 22px;
  height: 2px;
  background: var(--text-primary);
  border-radius: 2px;
  transition: var(--transition);
}
.mobile-toggle span:nth-child(1).open { transform: rotate(45deg) translate(5px, 5px); }
.mobile-toggle span:nth-child(2).open { opacity: 0; }
.mobile-toggle span:nth-child(3).open { transform: rotate(-45deg) translate(5px, -5px); }

.mobile-menu {
  display: none;
  flex-direction: column;
  padding: 16px 24px 24px;
  border-top: 1px solid var(--border);
  background: rgba(2, 4, 9, 0.95);
  backdrop-filter: blur(20px);
}
.mobile-menu.open { display: flex; }
.mobile-link {
  padding: 14px 0;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 16px;
  border-bottom: 1px solid var(--border);
  transition: var(--transition);
}
.mobile-link:hover { color: var(--text-primary); }
.mobile-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 20px;
}

@media (max-width: 768px) {
  .nav-links, .nav-actions { display: none; }
  .mobile-toggle { display: flex; }
}
</style>