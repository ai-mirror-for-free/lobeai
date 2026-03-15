<template>
  <div class="profile-container">
    <!-- 背景装饰 -->
    <div class="orb orb-blue" style="top: 10%; left: 10%;"></div>
    <div class="orb orb-purple" style="top: 30%; right: 10%;"></div>
    
    <div class="container">
      <div class="profile-header">
        <h1 class="page-title">个人中心</h1>
        <p class="page-subtitle">管理您的账户和订阅服务</p>
      </div>

      <div class="profile-grid">
        <!-- 用户信息卡片 -->
        <div class="card profile-info-card">
          <div class="card-header">
            <h2 class="card-title">账户信息</h2>
          </div>
          <div class="card-body">
            <div class="avatar-section">
              <div class="avatar">
                <span>{{ userInfo.initials }}</span>
              </div>
              <div class="user-details">
                <h3 class="user-name">{{ userInfo.name }}</h3>
                <p class="user-email">{{ userInfo.email }}</p>
              </div>
            </div>
            
            <div class="account-stats">
              <div class="stat-item">
                <span class="stat-label">注册时间</span>
                <span class="stat-value">{{ userInfo.registerDate }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">账户状态</span>
                <span class="stat-value stat-status-active">正常</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 套餐信息卡片 -->
        <div class="card subscription-card">
          <div class="card-header">
            <h2 class="card-title">当前套餐</h2>
          </div>
          <div class="card-body">
            <div class="subscription-badge">
              <span :class="['tag', 'tag-' + subscriptionInfo.planType]">
                {{ subscriptionInfo.planName }}
              </span>
            </div>
            
            <div class="subscription-details">
              <div class="detail-item">
                <span class="detail-label">到期时间</span>
                <span class="detail-value">{{ subscriptionInfo.expiryDate }}</span>
              </div>
              
              <div class="countdown-section">
                <div class="countdown-title">剩余时间</div>
                <div 
                  :class="[
                    'countdown-value', 
                    subscriptionInfo.daysLeft <= 7 ? 'countdown-warning' : ''
                  ]"
                >
                  {{ subscriptionInfo.daysLeft }} 天
                </div>
              </div>
            </div>
            
            <div class="subscription-status" v-if="!subscriptionInfo.isActive">
              <span class="status-message">您的套餐已过期，请及时续费</span>
            </div>
            
            <div class="subscription-actions">
              <button @click="goToOpenWebUI" class="btn btn-primary">
                访问 OpenWebUI
              </button>
              <RouterLink to="/renewal" class="btn btn-outline">
                续费套餐
              </RouterLink>
              <RouterLink to="/buy-new" class="btn btn-outline">
                购买新套餐
              </RouterLink>
            </div>
          </div>
        </div>

      </div>
    </div>
    
    <!-- 悬浮客服按钮 -->
    <div class="floating-support">
      <div class="support-dropdown" :class="{ 'active': isSupportDropdownVisible }">
        <a :href="supportOptions[0].link" target="_blank" class="dropdown-item">
          <div class="dropdown-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M20 2H4C2.9 2 2 2.9 2 4V22L6 18H20C21.1 18 22 17.1 22 16V4C22 2.9 21.1 2 20 2ZM20 16H5.17L4 17.17V4H20V16Z" fill="var(--accent-green)"/>
              <path d="M12 6C11.45 6 11 6.45 11 7C11 7.55 11.45 8 12 8C12.55 8 13 7.55 13 7C13 6.45 12.55 6 12 6ZM15 8C14.45 8 14 8.45 14 9C14 9.55 14.45 10 15 10C15.55 10 16 9.55 16 9C16 8.45 15.55 8 15 8ZM9 8C8.45 8 8 8.45 8 9C8 9.55 8.45 10 9 10C9.55 10 10 9.55 10 9C10 8.45 9.55 8 9 8Z" fill="var(--accent-green)"/>
            </svg>
          </div>
          <span>{{ supportOptions[0].title }}</span>
        </a>
        <a :href="supportOptions[1].link" target="_blank" class="dropdown-item">
          <div class="dropdown-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM10 17L5 12L6.41 10.59L10 14.17L17.59 6.58L19 8L10 17Z" fill="var(--accent-blue)"/>
            </svg>
          </div>
          <span>{{ supportOptions[1].title }}</span>
        </a>
      </div>
      <button class="support-toggle" @click="toggleSupportDropdown">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2Z" fill="var(--accent-cyan)"/>
          <path d="M11 17V11H13V17H11ZM11 9V7H13V9H11Z" fill="white"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const isSupportDropdownVisible = ref(false)

// 使用计算属性来响应式地获取用户信息
const userInfo = computed(() => userStore.state.userInfo)
const subscriptionInfo = computed(() => userStore.state.subscriptionInfo)

// 客服支持选项
const supportOptions = [
  {
    title: '在线客服',
    desc: '工作日 9:00-18:00 提供服务',
    link: '#contact' // 替换为实际链接
  },
  {
    title: 'QQ群',
    desc: '加入技术支持群获取帮助',
    link: '#qqgroup' // 替换为实际链接
  }
]

const toggleSupportDropdown = () => {
  isSupportDropdownVisible.value = !isSupportDropdownVisible.value
}

// 新增函数：跳转到OpenWebUI
const goToOpenWebUI = () => {
  const token = userStore.getToken();
  if (token) {
    // 构造带token的重定向URL
    const openWebUIUrl = 'https://chat.yang-sjq.cn/sso'; // 替换为实际的OpenWebUI地址
    const redirectUrl = `${openWebUIUrl}?token=${encodeURIComponent(token)}`;
    window.open(redirectUrl, '_blank');
  } else {
    alert('用户未登录或缺少访问令牌');
  }
}
</script>

<style scoped>
.profile-container {
  min-height: 100vh;
  padding-top: 100px;
  padding-bottom: 60px;
  position: relative;
}

.profile-header {
  text-align: center;
  margin-bottom: 40px;
}

.page-title {
  font-size: 2.5rem;
  font-weight: 700;
  margin-bottom: 12px;
  background: var(--gradient-text);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.page-subtitle {
  color: var(--text-secondary);
  font-size: 1.1rem;
}

.profile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.card {
  padding: 32px;
  display: flex;
  flex-direction: column;
}

.card-header {
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
}

.card-title {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text-primary);
}

.card-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 用户信息卡片样式 */
.profile-info-card {
  grid-column: span 1;
}

.avatar-section {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 20px;
}

.avatar {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--gradient-accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: 700;
  color: white;
}

.user-details h3 {
  font-size: 1.5rem;
  margin-bottom: 6px;
}

.user-details p {
  color: var(--text-secondary);
  margin: 0;
}

.account-stats {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stat-item {
  display: flex;
  flex-direction: column;
}

.stat-label {
  color: var(--text-secondary);
  font-size: 0.9rem;
  margin-bottom: 6px;
}

.stat-value {
  color: var(--text-primary);
  font-weight: 500;
  font-size: 1.1rem;
}

.stat-status-active {
  color: var(--accent-green);
}

/* 套餐信息卡片样式 */
.subscription-card {
  grid-column: span 1;
}

.subscription-badge {
  margin-bottom: 20px;
}

.subscription-details {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-bottom: 24px;
  flex: 1;
}

.detail-item {
  display: flex;
  flex-direction: column;
}

.detail-label {
  color: var(--text-secondary);
  font-size: 0.9rem;
  margin-bottom: 6px;
}

.detail-value {
  color: var(--text-primary);
  font-weight: 500;
  font-size: 1.1rem;
}

.countdown-section {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}

.countdown-title {
  color: var(--text-secondary);
  font-size: 0.9rem;
  margin-bottom: 6px;
}

.countdown-value {
  color: var(--text-primary);
  font-weight: 700;
  font-size: 1.8rem;
}

.countdown-warning {
  color: var(--accent-cyan);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.6; }
  100% { opacity: 1; }
}

.subscription-status {
  padding: 12px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: var(--radius-md);
  margin-bottom: 20px;
  text-align: center;
}

.status-message {
  color: #ef4444;
  font-weight: 500;
}

.subscription-actions {
  display: flex;
  gap: 16px;
  margin-top: auto;
}

/* 快捷入口卡片样式 */
.quick-access-card {
  grid-column: span 2;
}

.quick-access-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
}

.access-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  transition: var(--transition);
  text-decoration: none;
  color: inherit;
}

.access-card:hover {
  border-color: var(--border-glow);
  transform: translateY(-4px);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
}

.access-icon {
  margin-bottom: 16px;
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.access-icon-openwebui {
  background: rgba(56, 189, 248, 0.1);
}

.access-icon-api {
  background: rgba(167, 139, 250, 0.1);
}

.access-title {
  color: var(--text-primary);
  font-size: 1.2rem;
  font-weight: 600;
  margin-bottom: 8px;
}

.access-desc {
  color: var(--text-secondary);
  font-size: 0.95rem;
}

/* 客服支持卡片样式 */
/* 悬浮客服按钮样式 */
.floating-support {
  position: fixed;
  bottom: 30px;
  right: 30px;
  z-index: 1000;
}

.support-toggle {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  background: var(--bg-card);
  border: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transition: var(--transition);
  color: var(--text-secondary);
}

.support-toggle:hover {
  transform: scale(1.1);
  box-shadow: 0 6px 25px rgba(56, 189, 248, 0.6);
}

.support-dropdown {
  position: absolute;
  bottom: 70px;
  right: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  opacity: 0;
  visibility: hidden;
  transform: translateY(10px);
  transition: all 0.3s ease;
  width: 220px;
}

.support-dropdown.active {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  text-decoration: none;
  transition: var(--transition);
  backdrop-filter: blur(10px);
}

.dropdown-item:hover {
  background: var(--bg-card-hover);
  border-color: var(--border-glow);
  transform: translateX(-5px);
}

.dropdown-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(56, 189, 248, 0.1);
}

@media (min-width: 993px) {
  .profile-grid {
    grid-template-columns: 1fr 1fr; /* 两列布局 */
  }
  
  .profile-info-card,
  .subscription-card {
    grid-column: span 1; /* 每个卡片占据一列 */
  }
}

@media (max-width: 992px) {
  .profile-grid {
    grid-template-columns: 1fr;
  }
  
  .profile-info-card,
  .subscription-card {
    grid-column: span 1;
  }
  
  .subscription-details {
    flex-direction: column;
    gap: 20px;
  }
  
  .account-stats {
    flex-direction: column;
    gap: 16px;
  }
  
  .subscription-actions {
    flex-direction: column;
  }
}

@media (max-width: 768px) {
  .page-title {
    font-size: 2rem;
  }
  
  .card {
    padding: 24px;
  }
  
  .avatar-section {
    flex-direction: column;
    text-align: center;
  }
  
  .floating-support {
    bottom: 20px;
    right: 20px;
  }
  
  .support-dropdown {
    width: 200px;
  }
}
</style>