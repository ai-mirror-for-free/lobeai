<template>
  <main>
    <!-- Hero Section -->
    <section class="hero">
      <!-- Background orbs -->
      <div class="orb" style="width:600px;height:600px;background:radial-gradient(circle,rgba(99,102,241,0.15) 0%,transparent 70%);top:-200px;left:-100px;"></div>
      <div class="orb" style="width:500px;height:500px;background:radial-gradient(circle,rgba(56,189,248,0.1) 0%,transparent 70%);bottom:-100px;right:-50px;"></div>

      <!-- Grid lines -->
      <div class="hero-grid"></div>

      <div class="container hero-content">
        <div class="hero-badge">
          <span class="badge-dot"></span>
          <span>全新发布 — GPT-5、Claude 4.7、Gemini Ultra 现已上线</span>
        </div>

        <h1 class="hero-title">
          汇聚全球顶级<br/>
          <span class="gradient-text">AI 智能模型</span>
        </h1>

        <p class="hero-desc">
          一个账号，畅享 GPT-4、Claude、Gemini、DeepSeek 等数十款顶尖大模型。
          无需翻墙，按需付费，即刻开始你的 AI 之旅。
        </p>

        <div class="hero-actions">
          <RouterLink to="/login" class="btn btn-primary btn-lg">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 5l7 7-7 7M5 5l7 7-7 7"/></svg>
            立即体验
          </RouterLink>
          <RouterLink to="/models" class="btn btn-outline btn-lg">查看所有模型</RouterLink>
        </div>

        <div class="hero-stats">
          <div class="stat">
            <span class="stat-num">50+</span>
            <span class="stat-label">AI 模型</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat">
            <span class="stat-num">10万+</span>
            <span class="stat-label">活跃用户</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat">
            <span class="stat-num">99.9%</span>
            <span class="stat-label">服务可用性</span>
          </div>
        </div>
      </div>

      <!-- Floating model cards -->
      <div class="hero-visual">
        <div class="model-orbit">
          <div class="orbit-ring ring-1"></div>
          <div class="orbit-ring ring-2"></div>

          <div class="center-orb">
            <svg width="40" height="40" viewBox="0 0 28 28" fill="none">
              <path d="M14 2L25 8V20L14 26L3 20V8L14 2Z" stroke="url(#hg)" stroke-width="1.5" fill="rgba(99,102,241,0.2)"/>
              <path d="M14 8L19 11V17L14 20L9 17V11L14 8Z" fill="url(#hg)"/>
              <defs>
                <linearGradient id="hg" x1="3" y1="2" x2="25" y2="26" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#38bdf8"/><stop offset="1" stop-color="#a78bfa"/>
                </linearGradient>
              </defs>
            </svg>
          </div>

          <div v-for="(m, i) in orbitModels" :key="i" class="orbit-chip" :style="orbitStyle(i, orbitModels.length)">
            <span class="chip-icon">{{ m.icon }}</span>
            <span>{{ m.name }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Models Showcase -->
    <section class="section" id="models">
      <div class="container">
        <div class="section-header">
          <span class="tag tag-cyan">模型广场</span>
          <h2 class="section-title">接入业界最强 AI 模型</h2>
          <p class="section-desc">从文字创作到代码生成，从图像理解到多模态交互，所有顶级模型一键可达。</p>
        </div>

        <div class="models-grid">
          <div v-for="m in featuredModels" :key="m.id" class="model-card card">
            <div class="model-card-header">
              <div class="model-avatar" :style="{ background: m.gradient }">
                <span>{{ m.emoji }}</span>
              </div>
              <div class="model-meta">
                <span class="model-provider">{{ m.provider }}</span>
                <h3 class="model-name">{{ m.name }}</h3>
              </div>
              <span class="tag" :class="m.tagClass">{{ m.tag }}</span>
            </div>
            <p class="model-desc">{{ m.desc }}</p>
            <div class="model-caps">
              <span v-for="c in m.caps" :key="c" class="cap-chip">{{ c }}</span>
            </div>
            <div class="model-footer">
              <span class="model-ctx">{{ m.ctx }}</span>
              <RouterLink to="/register" class="btn btn-ghost" style="font-size:13px;padding:8px 14px">立即使用 →</RouterLink>
            </div>
          </div>
        </div>

        <div style="text-align:center;margin-top:48px">
          <RouterLink to="/models" class="btn btn-outline btn-lg">查看全部 50+ 模型</RouterLink>
        </div>
      </div>
    </section>

    <!-- Features Section -->
    <section class="section features-section" id="features">
      <div class="container">
        <div class="section-header">
          <span class="tag tag-purple">功能特性</span>
          <h2 class="section-title">为什么选择 NexusAI</h2>
        </div>

        <div class="features-grid">
          <div v-for="f in features" :key="f.title" class="feature-card card">
            <div class="feature-icon" :style="{ background: f.iconBg }">
              <span v-html="f.icon"></span>
            </div>
            <h3>{{ f.title }}</h3>
            <p>{{ f.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- CTA Pricing Preview -->
    <section class="section cta-section">
      <div class="container">
        <div class="cta-box">
          <div class="cta-orb"></div>
          <span class="tag tag-cyan" style="margin-bottom:24px">简单透明的定价</span>
          <h2 class="cta-title">按需付费，灵活选择</h2>
          <p class="cta-desc">从个人到企业，我们提供匹配每个场景的套餐方案。所有计划均包含免费额度，无隐藏收费。</p>
          <div class="cta-actions">
            <RouterLink to="/pricing" class="btn btn-primary btn-lg">查看定价方案</RouterLink>
            <!-- <RouterLink to="/register" class="btn btn-outline btn-lg">免费注册</RouterLink> -->
          </div>
        </div>
      </div>
    </section>

    <!-- FAQ Section -->
    <section class="section" id="faq">
      <div class="container">
        <div class="section-header">
          <span class="tag tag-green">常见问题</span>
          <h2 class="section-title">你可能想了解的</h2>
        </div>
        <div class="faq-list">
          <div v-for="(faq, i) in faqs" :key="i" class="faq-item" @click="toggleFaq(i)">
            <div class="faq-q">
              <span>{{ faq.q }}</span>
              <svg class="faq-arrow" :class="{ open: openFaq === i }" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
            </div>
            <div class="faq-a" :class="{ open: openFaq === i }">
              <p>{{ faq.a }}</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  </main>
</template>

<script setup>
import { ref } from 'vue'

const orbitModels = [
  { name: 'GPT-4o', icon: '🤖' },
  { name: 'Claude', icon: '🧠' },
  { name: 'Gemini', icon: '💫' },
  { name: 'DeepSeek', icon: '🔍' },
  { name: 'Llama', icon: '🦙' },
  { name: 'Mistral', icon: '⚡' },
]

function orbitStyle(index, total) {
  const angle = (index / total) * 360
  const rad = (angle * Math.PI) / 180
  const radius = 160
  const x = Math.cos(rad) * radius
  const y = Math.sin(rad) * radius
  return {
    transform: `translate(calc(-50% + ${x}px), calc(-50% + ${y}px))`,
    animationDelay: `${index * 0.5}s`
  }
}

const featuredModels = [
  {
    id: 1, provider: 'OpenAI', name: 'GPT-5',
    emoji: '🤖', gradient: 'linear-gradient(135deg,#10a37f,#1a7f64)',
    tag: '多模态', tagClass: 'tag-green',
    desc: '最强大的多模态模型，支持文字、图像、语音理解与生成，处理复杂任务游刃有余。',
    caps: ['文本生成', '图像理解', '代码', '推理'],
    ctx: '128K 上下文'
  },
  {
    id: 2, provider: 'Anthropic', name: 'Claude 4.7',
    emoji: '🧠', gradient: 'linear-gradient(135deg,#d97706,#92400e)',
    tag: '推理强', tagClass: 'tag-purple',
    desc: '专注于安全与深度推理，超长上下文处理能力卓越，适合文档分析与复杂逻辑任务。',
    caps: ['深度推理', '文档分析', '创作', '代码'],
    ctx: '200K 上下文'
  },
  {
    id: 3, provider: 'Google', name: 'Gemini 3.1 Pro',
    emoji: '💫', gradient: 'linear-gradient(135deg,#4285f4,#1a56db)',
    tag: '超长', tagClass: 'tag-cyan',
    desc: '谷歌最新旗舰模型，拥有超长上下文窗口，多语言能力出色，擅长数据分析与科学推理。',
    caps: ['超长上下文', '多语言', '数据分析', '代码'],
    ctx: '1M 上下文'
  },
  {
    id: 4, provider: 'DeepSeek', name: 'DeepSeek-V3',
    emoji: '🔍', gradient: 'linear-gradient(135deg,#6366f1,#4338ca)',
    tag: '开源', tagClass: 'tag-purple',
    desc: '国产顶级开源大模型，中文理解能力极强，数学与代码能力媲美顶级闭源模型。',
    caps: ['中文优化', '数学', '代码', '推理'],
    ctx: '64K 上下文'
  },
  {
    id: 5, provider: 'Meta', name: 'Llama 3.1 405B',
    emoji: '🦙', gradient: 'linear-gradient(135deg,#0284c7,#075985)',
    tag: '开源', tagClass: 'tag-cyan',
    desc: 'Meta 最大规模开源模型，4050亿参数，综合能力强大，支持多语言与代码生成。',
    caps: ['开源免费', '多语言', '代码', '对话'],
    ctx: '128K 上下文'
  },
  {
    id: 6, provider: 'Mistral AI', name: 'Mistral Large 2',
    emoji: '⚡', gradient: 'linear-gradient(135deg,#f97316,#c2410c)',
    tag: '欧洲', tagClass: 'tag-green',
    desc: '欧洲领先 AI 实验室出品，推理效率极高，特别适合企业级应用与 API 集成场景。',
    caps: ['高效推理', '函数调用', '代码', '多语言'],
    ctx: '128K 上下文'
  },
]

const features = [
  {
    icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>',
    iconBg: 'rgba(56,189,248,0.1)',
    title: '毫秒级响应',
    desc: '全球加速节点，多路由负载均衡，确保模型调用低延迟、高吞吐。'
  },
  {
    icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>',
    iconBg: 'rgba(167,139,250,0.1)',
    title: '隐私安全保障',
    desc: '对话内容不用于训练，端到端加密传输，合规存储，保护您的每一次交流。'
  },
  {
    icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
    iconBg: 'rgba(52,211,153,0.1)',
    title: '国内直连访问',
    desc: '无需 VPN，国内服务器直连，稳定可靠，随时随地访问顶尖境外模型。'
  },
  {
    icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>',
    iconBg: 'rgba(56,189,248,0.1)',
    title: '灵活计费方式',
    desc: '按量计费 + 套餐订阅双模式，满足个人到企业的多样化需求，费用透明可控。'
  },
  {
    icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
    iconBg: 'rgba(167,139,250,0.1)',
    title: 'OpenWebUI 对接',
    desc: '无缝集成 OpenWebUI，保留熟悉的交互界面，底层换装顶级模型，体验大幅提升。'
  },
  {
    icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    iconBg: 'rgba(52,211,153,0.1)',
    title: '7×24 技术支持',
    desc: '专属客服团队全天候在线，快速响应使用问题，企业用户享有专属 SLA 保障。'
  }
]

const openFaq = ref(null)
function toggleFaq(i) {
  openFaq.value = openFaq.value === i ? null : i
}

const faqs = [
  { q: '如何开始使用 NexusAI？', a: '注册账号后即可免费体验，无需信用卡。新用户赠送体验额度，可立即调用任意模型。升级订阅后获得更大额度和更快响应速度。' },
  { q: '支持哪些支付方式？', a: '支持支付宝、微信支付、银行卡等多种国内支付方式，也支持 USDT 等数字货币支付，方便灵活。' },
  { q: '数据隐私如何保障？', a: '所有对话均加密传输与存储，我们承诺不将用户对话数据用于模型训练。企业版支持私有化部署，数据完全自主可控。' },
  { q: '能否自定义对接到我的业务系统？', a: '支持 OpenAI 兼容格式的 API，可无缝替换现有 AI 服务，同时提供专属 SDK 与详细接入文档，技术团队全程协助对接。' },
  { q: '套餐额度用完后怎么办？', a: '套餐额度用完后自动切换至按量计费模式，不影响正常使用。也可随时升级套餐或购买额度包，续费操作简单便捷。' },
  { q: '是否提供企业定制方案？', a: '针对企业用户，我们提供专属定价、私有化部署、合规审计、批量账号管理等服务，欢迎联系商务团队洽谈。' },
]
</script>

<style scoped>
/* HERO */
.hero {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  overflow: hidden;
  padding: 120px 0 80px;
}
.hero-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
  background-size: 60px 60px;
  mask-image: radial-gradient(ellipse at center, black 30%, transparent 80%);
}
.hero-content {
  position: relative;
  z-index: 1;
  max-width: 600px;
}
.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: rgba(56,189,248,0.08);
  border: 1px solid rgba(56,189,248,0.2);
  border-radius: 999px;
  font-size: 13px;
  color: var(--accent-cyan);
  margin-bottom: 28px;
  animation: fadeUp 0.6s ease forwards;
}
.badge-dot {
  width: 7px; height: 7px;
  background: var(--accent-cyan);
  border-radius: 50%;
  animation: pulse-glow 2s ease infinite;
}
.hero-title {
  font-family: var(--font-display);
  font-size: clamp(42px, 5.5vw, 72px);
  font-weight: 800;
  line-height: 1.1;
  letter-spacing: -0.02em;
  margin-bottom: 24px;
  animation: fadeUp 0.7s 0.1s ease both;
}
.gradient-text {
  background: var(--gradient-text);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.hero-desc {
  font-size: 17px;
  color: var(--text-secondary);
  line-height: 1.75;
  margin-bottom: 36px;
  max-width: 520px;
  animation: fadeUp 0.7s 0.2s ease both;
}
.hero-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 52px;
  animation: fadeUp 0.7s 0.3s ease both;
}
.btn-lg { padding: 15px 30px; font-size: 15px; }
.hero-stats {
  display: flex;
  align-items: center;
  gap: 32px;
  animation: fadeUp 0.7s 0.4s ease both;
}
.stat { display: flex; flex-direction: column; gap: 4px; }
.stat-num {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 800;
  background: var(--gradient-text);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.stat-label { font-size: 13px; color: var(--text-muted); }
.stat-divider { width: 1px; height: 40px; background: var(--border); }

/* ORBIT VISUAL */
.hero-visual {
  position: absolute;
  right: -80px;
  top: 50%;
  transform: translateY(-50%);
  width: 500px;
  height: 500px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.model-orbit {
  position: relative;
  width: 380px;
  height: 380px;
}
.orbit-ring {
  position: absolute;
  border-radius: 50%;
  border: 1px solid rgba(99,102,241,0.15);
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  animation: spin-slow linear infinite;
}
.ring-1 { width: 320px; height: 320px; animation-duration: 20s; }
.ring-2 { width: 220px; height: 220px; animation-duration: 14s; animation-direction: reverse; border-color: rgba(56,189,248,0.12); }
.center-orb {
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  width: 72px; height: 72px;
  background: rgba(12,18,32,0.9);
  border: 1px solid rgba(99,102,241,0.3);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 0 40px rgba(99,102,241,0.3);
  animation: float 4s ease-in-out infinite;
}
.orbit-chip {
  position: absolute;
  top: 50%; left: 50%;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  background: rgba(12,18,32,0.95);
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  font-family: var(--font-display);
  white-space: nowrap;
  animation: float 4s ease-in-out infinite;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4);
}
.chip-icon { font-size: 14px; }

/* SECTION COMMON */
.section-header { text-align: center; margin-bottom: 64px; }
.section-title {
  font-family: var(--font-display);
  font-size: clamp(28px, 3.5vw, 44px);
  font-weight: 800;
  margin: 16px 0 12px;
  letter-spacing: -0.02em;
}
.section-desc { color: var(--text-secondary); font-size: 16px; max-width: 520px; margin: 0 auto; }

/* MODELS GRID */
.models-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}
.model-card { padding: 24px; display: flex; flex-direction: column; gap: 14px; }
.model-card-header { display: flex; align-items: center; gap: 12px; }
.model-avatar {
  width: 44px; height: 44px;
  border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}
.model-meta { flex: 1; }
.model-provider { font-size: 11px; color: var(--text-muted); font-weight: 500; display: block; }
.model-name { font-family: var(--font-display); font-size: 16px; font-weight: 700; }
.model-desc { color: var(--text-secondary); font-size: 13.5px; line-height: 1.6; flex: 1; }
.model-caps { display: flex; flex-wrap: wrap; gap: 6px; }
.cap-chip {
  padding: 4px 10px;
  background: rgba(255,255,255,0.05);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 11px;
  color: var(--text-secondary);
}
.model-footer { display: flex; align-items: center; justify-content: space-between; padding-top: 8px; border-top: 1px solid var(--border); }
.model-ctx { font-size: 12px; color: var(--text-muted); font-family: monospace; }

/* FEATURES */
.features-section { background: linear-gradient(180deg, transparent, rgba(8,13,20,0.8) 30%, rgba(8,13,20,0.8) 70%, transparent); }
.features-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.feature-card { padding: 28px; display: flex; flex-direction: column; gap: 14px; }
.feature-icon {
  width: 48px; height: 48px;
  border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center;
  color: var(--accent-cyan);
}
.feature-card h3 { font-family: var(--font-display); font-size: 17px; font-weight: 700; }
.feature-card p { color: var(--text-secondary); font-size: 14px; line-height: 1.7; }

/* CTA */
.cta-section { }
.cta-box {
  position: relative;
  text-align: center;
  padding: 80px 48px;
  background: var(--gradient-card);
  border: 1px solid rgba(99,102,241,0.2);
  border-radius: var(--radius-xl);
  overflow: hidden;
  display: flex; flex-direction: column; align-items: center;
}
.cta-orb {
  position: absolute;
  width: 500px; height: 500px;
  background: radial-gradient(circle, rgba(99,102,241,0.12) 0%, transparent 70%);
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  animation: pulse-glow 4s ease infinite;
}
.cta-title {
  position: relative;
  font-family: var(--font-display);
  font-size: clamp(28px, 3.5vw, 44px);
  font-weight: 800;
  margin-bottom: 16px;
}
.cta-desc {
  position: relative;
  color: var(--text-secondary);
  font-size: 16px;
  max-width: 500px;
  margin-bottom: 36px;
  line-height: 1.7;
}
.cta-actions {
  position: relative;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
}

/* FAQ */
.faq-list { max-width: 720px; margin: 0 auto; display: flex; flex-direction: column; gap: 12px; }
.faq-item {
  background: var(--gradient-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: var(--transition);
  overflow: hidden;
}
.faq-item:hover { border-color: var(--border-glow); }
.faq-q {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  font-weight: 500;
  font-size: 15px;
}
.faq-arrow { transition: transform 0.3s ease; flex-shrink: 0; color: var(--text-muted); }
.faq-arrow.open { transform: rotate(180deg); }
.faq-a { max-height: 0; overflow: hidden; transition: max-height 0.4s cubic-bezier(0.4,0,0.2,1); }
.faq-a.open { max-height: 200px; }
.faq-a p { padding: 0 24px 20px; color: var(--text-secondary); font-size: 14px; line-height: 1.8; }

/* Responsive */
@media (max-width: 1024px) {
  .hero-visual { display: none; }
  .models-grid, .features-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 640px) {
  .models-grid, .features-grid { grid-template-columns: 1fr; }
  .hero-stats { gap: 20px; }
  .cta-box { padding: 48px 24px; }
}
</style>
