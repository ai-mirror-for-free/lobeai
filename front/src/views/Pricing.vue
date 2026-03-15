<template>
  <main class="pricing-page">
    <div class="orb" style="width:600px;height:600px;background:radial-gradient(circle,rgba(56,189,248,0.1) 0%,transparent 70%);top:-100px;left:50%;transform:translateX(-50%);pointer-events:none;"></div>

    <div class="container">
      <div class="page-header">
        <span class="tag tag-cyan">灵活定价</span>
        <h1 class="page-title">选择适合你的方案</h1>
        <p class="page-desc">从个人探索到企业部署，总有一款适合你。所有计划均包含免费额度，无隐藏费用。</p>

        <!-- Billing Toggle -->
        <div class="billing-toggle">
          <button :class="{ active: billing === 'monthly' }" @click="billing = 'monthly'">月付</button>
          <button :class="{ active: billing === 'yearly' }" @click="billing = 'yearly'">
            年付
            <span class="save-badge">省20%</span>
          </button>
        </div>
      </div>

      <!-- Plans Grid -->
      <div class="plans-grid">
        <div v-for="plan in plans" :key="plan.id"
          class="plan-card"
          :class="{ popular: plan.popular }">

          <div v-if="plan.popular" class="popular-badge">
            <span>⭐ 最受欢迎</span>
          </div>

          <div class="plan-header">
            <div class="plan-icon" :style="{ background: plan.iconBg }">{{ plan.icon }}</div>
            <div>
              <h3 class="plan-name">{{ plan.name }}</h3>
              <p class="plan-subtitle">{{ plan.subtitle }}</p>
            </div>
          </div>

          <div class="plan-price">
            <span class="price-currency">¥</span>
            <span class="price-amount">{{ billing === 'monthly' ? plan.monthlyPrice : plan.yearlyPrice }}</span>
            <span class="price-period">/月</span>
          </div>
          <p v-if="billing === 'yearly' && plan.monthlyPrice !== '0'" class="price-billed">按年计费，每年 ¥{{ plan.yearlyTotal }}</p>

          <RouterLink to="/register" class="plan-btn btn" :class="plan.popular ? 'btn-primary' : 'btn-outline'">
            {{ plan.cta }}
          </RouterLink>

          <div class="plan-divider"></div>

          <ul class="plan-features">
            <li v-for="f in plan.features" :key="f.text" class="plan-feature" :class="{ disabled: !f.included }">
              <svg v-if="f.included" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="check-icon"><polyline points="20 6 9 17 4 12"/></svg>
              <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="x-icon"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              <span>{{ f.text }}</span>
            </li>
          </ul>
        </div>
      </div>

      <!-- Token Packs -->
      <div class="addon-section">
        <div class="section-header" style="margin-bottom:40px">
          <span class="tag tag-purple">按量计费</span>
          <h2 class="section-title" style="font-size:32px">额度包充值</h2>
          <p class="section-desc">一次性购买，永久有效。结合套餐使用，享受最大化性价比。</p>
        </div>
        <div class="packs-grid">
          <div v-for="pack in tokenPacks" :key="pack.id" class="pack-card card">
            <div class="pack-header">
              <span class="pack-icon">{{ pack.icon }}</span>
              <span v-if="pack.badge" class="pack-badge">{{ pack.badge }}</span>
            </div>
            <div class="pack-tokens">{{ pack.tokens }}</div>
            <div class="pack-desc">{{ pack.desc }}</div>
            <div class="pack-price">¥{{ pack.price }}</div>
            <RouterLink to="/register" class="btn btn-outline" style="width:100%;justify-content:center;font-size:13px;padding:10px">立即购买</RouterLink>
          </div>
        </div>
      </div>

      <!-- Comparison Table -->
      <div class="comparison-section">
        <div class="section-header" style="margin-bottom:40px">
          <h2 class="section-title" style="font-size:32px">方案详细对比</h2>
        </div>
        <div class="comparison-table">
          <div class="ct-header">
            <div class="ct-feature-col">功能</div>
            <div v-for="plan in plans" :key="plan.id" class="ct-plan-col" :class="{ popular: plan.popular }">
              {{ plan.name }}
            </div>
          </div>
          <div v-for="row in comparisonRows" :key="row.feature" class="ct-row">
            <div class="ct-feature-col">{{ row.feature }}</div>
            <div v-for="(val, i) in row.values" :key="i" class="ct-plan-col" :class="{ popular: plans[i].popular }">
              <svg v-if="val === true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
              <svg v-else-if="val === false" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              <span v-else>{{ val }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Enterprise CTA -->
      <div class="enterprise-cta">
        <div class="enterprise-inner">
          <span class="enterprise-icon">🏢</span>
          <div>
            <h3>需要企业定制方案？</h3>
            <p>私有化部署、专属 SLA、合规审计、批量账号管理，联系我们获取专属报价。</p>
          </div>
          <a href="mailto:enterprise@nexusai.com" class="btn btn-primary" style="flex-shrink:0">联系商务</a>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup>
import { ref } from 'vue'

const billing = ref('monthly')

const plans = [
  {
    id: 'free', name: '基础版', subtitle: '探索 AI 的第一步', icon: '🌱', iconBg: 'rgba(52,211,153,0.15)',
    monthlyPrice: '30', yearlyPrice: '0', yearlyTotal: '0',
    cta: '立即订阅', popular: false,
    features: [
      { text: '每日 20 次免费对话', included: true },
      { text: '访问 GPT-4o mini、Claude Haiku', included: true },
      { text: '最大 8K 上下文长度', included: true },
      { text: '社区技术支持', included: true },
      { text: '高级模型访问权限', included: false },
      // { text: 'API 调用权限', included: false },
      { text: '优先响应速度', included: false },
    ]
  },
  {
    id: 'pro', name: '专业版', subtitle: '适合个人用户和创作者', icon: '⚡', iconBg: 'rgba(56,189,248,0.15)',
    monthlyPrice: '68', yearlyPrice: '54', yearlyTotal: '648',
    cta: '立即订阅', popular: true,
    features: [
      { text: '无限次对话', included: true },
      { text: '访问所有顶级模型', included: true },
      { text: '最大 200K 上下文长度', included: true },
      { text: '每月 500 万 Token 额度', included: true },
      // { text: 'API 调用权限（10万次/月）', included: true },
      { text: '优先响应速度', included: true },
      { text: '企业级 SLA', included: false },
    ]
  },
  {
    id: 'team', name: '至尊版', subtitle: '适合小团队协作', icon: '👥', iconBg: 'rgba(167,139,250,0.15)',
    monthlyPrice: '198', yearlyPrice: '158', yearlyTotal: '1896',
    cta: '立即订阅', popular: false,
    features: [
      { text: '访问所有顶级模型', included: true },
      { text: '最大 200K 上下文长度', included: true },
      { text: '每月 2000 万 Token 额度', included: true },
      // { text: 'API 调用权限（无限制）', included: true },
      { text: '优先响应速度', included: true },
      { text: '企业级 SLA', included: true },
    ]
  },
]

const tokenPacks = [
  { id:1, icon:'💎', tokens:'100 万 Token', desc:'适合轻量日常使用', price:'9.9', badge: null },
  { id:2, icon:'🚀', tokens:'500 万 Token', desc:'高频用户推荐', price:'39', badge:'省20%' },
  { id:3, icon:'⚡', tokens:'2000 万 Token', desc:'开发者与团队首选', price:'139', badge:'省30%' },
  { id:4, icon:'🏆', tokens:'1 亿 Token', desc:'大规模业务专属', price:'599', badge:'省40%' },
]

const comparisonRows = [
  { feature: '每日对话次数', values: ['20次', '无限', '无限'] },
  { feature: '月度 Token 额度', values: ['有限', '500万', '2000万'] },
  { feature: 'GPT-4o / Claude 3.7', values: [false, true, true] },
  { feature: 'o1 推理模型', values: [false, true, true] },
  { feature: '上下文长度', values: ['8K', '200K', '200K'] },
  { feature: 'API 访问权限', values: [false, true, true] },
  { feature: '优先响应速度', values: [false, true, true] },
  { feature: '团队协作功能', values: [false, false, true] },
  { feature: '专属客服支持', values: [false, false, true] },
]
</script>

<style scoped>
.pricing-page {
  padding-top: 100px;
  padding-bottom: 100px;
  position: relative;
  overflow: hidden;
}
.page-header { text-align: center; padding: 60px 0 56px; }
.page-title {
  font-family: var(--font-display);
  font-size: clamp(32px, 4vw, 52px);
  font-weight: 800;
  margin: 16px 0 12px;
  letter-spacing: -0.02em;
}
.page-desc { color: var(--text-secondary); font-size: 16px; max-width: 480px; margin: 0 auto 32px; }

.billing-toggle {
  display: inline-flex;
  background: rgba(255,255,255,0.05);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 4px;
  gap: 4px;
}
.billing-toggle button {
  padding: 9px 20px;
  border-radius: var(--radius-sm);
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: var(--transition);
  display: flex; align-items: center; gap: 8px;
  font-family: var(--font-body);
}
.billing-toggle button.active { background: rgba(255,255,255,0.1); color: var(--text-primary); }
.save-badge {
  padding: 2px 8px;
  background: linear-gradient(135deg, #34d399, #059669);
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
}

.plans-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
  margin-bottom: 80px;
  align-items: start;
}

.plan-card {
  background: var(--gradient-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: 32px;
  position: relative;
  transition: var(--transition);
}
.plan-card:hover { border-color: var(--border-glow); box-shadow: 0 8px 40px rgba(56,189,248,0.06); }
.plan-card.popular {
  border-color: rgba(99,102,241,0.4);
  background: linear-gradient(135deg, rgba(99,102,241,0.08) 0%, rgba(12,18,32,0.95) 100%);
  box-shadow: 0 0 40px rgba(99,102,241,0.15);
}
.popular-badge {
  position: absolute;
  top: -14px; left: 50%;
  transform: translateX(-50%);
  background: var(--gradient-accent);
  color: #fff;
  padding: 6px 20px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  font-family: var(--font-display);
  white-space: nowrap;
  box-shadow: 0 4px 16px rgba(99,102,241,0.4);
}

.plan-header { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }
.plan-icon { width: 44px; height: 44px; border-radius: var(--radius-sm); display: flex; align-items: center; justify-content: center; font-size: 22px; }
.plan-name { font-family: var(--font-display); font-size: 18px; font-weight: 700; }
.plan-subtitle { font-size: 12px; color: var(--text-muted); margin-top: 2px; }

.plan-price { display: flex; align-items: baseline; gap: 4px; margin-bottom: 4px; }
.price-currency { font-size: 22px; font-weight: 700; color: var(--text-secondary); align-self: flex-start; margin-top: 8px; }
.price-amount { font-family: var(--font-display); font-size: 52px; font-weight: 800; line-height: 1; }
.price-period { font-size: 14px; color: var(--text-muted); }
.price-billed { font-size: 12px; color: var(--text-muted); margin-bottom: 24px; }

.plan-btn { width: 100%; justify-content: center; margin-top: 24px; margin-bottom: 24px; }
.plan-divider { height: 1px; background: var(--border); margin-bottom: 24px; }
.plan-features { list-style: none; display: flex; flex-direction: column; gap: 12px; }
.plan-feature { display: flex; align-items: center; gap: 10px; font-size: 14px; }
.plan-feature.disabled { color: var(--text-muted); }
.check-icon { color: var(--accent-green); flex-shrink: 0; }
.x-icon { color: var(--text-muted); flex-shrink: 0; }

/* Token packs */
.addon-section { margin-bottom: 80px; }
.packs-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.pack-card { padding: 24px; display: flex; flex-direction: column; gap: 10px; }
.pack-header { display: flex; align-items: center; justify-content: space-between; }
.pack-icon { font-size: 28px; }
.pack-badge {
  padding: 3px 10px; border-radius: 999px;
  background: linear-gradient(135deg, #34d399, #059669);
  color: #fff; font-size: 11px; font-weight: 700;
}
.pack-tokens { font-family: var(--font-display); font-size: 20px; font-weight: 700; }
.pack-desc { font-size: 13px; color: var(--text-secondary); }
.pack-price { font-family: var(--font-display); font-size: 28px; font-weight: 800; background: var(--gradient-text); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }

/* Comparison table */
.comparison-section { margin-bottom: 80px; }
.comparison-table { border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; }
.ct-header, .ct-row { display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; }
.ct-header {
  background: rgba(255,255,255,0.04);
  border-bottom: 1px solid var(--border);
  padding: 16px 24px;
  font-size: 13px;
  font-weight: 700;
  font-family: var(--font-display);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}
.ct-row { padding: 0 24px; border-bottom: 1px solid var(--border); }
.ct-row:last-child { border-bottom: none; }
.ct-feature-col, .ct-plan-col {
  padding: 14px 0;
  display: flex;
  align-items: center;
  font-size: 14px;
}
.ct-plan-col { justify-content: center; color: var(--text-secondary); font-size: 13px; }
.ct-plan-col.popular { color: var(--text-primary); }

/* Enterprise */
.enterprise-cta {
  background: var(--gradient-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: 40px 48px;
}
.enterprise-inner { display: flex; align-items: center; gap: 24px; flex-wrap: wrap; }
.enterprise-icon { font-size: 48px; flex-shrink: 0; }
.enterprise-inner div { flex: 1; }
.enterprise-inner h3 { font-family: var(--font-display); font-size: 22px; font-weight: 700; margin-bottom: 8px; }
.enterprise-inner p { color: var(--text-secondary); font-size: 14px; }

@media (max-width: 900px) {
  .plans-grid { grid-template-columns: 1fr; max-width: 400px; margin: 0 auto 80px; }
  .packs-grid { grid-template-columns: repeat(2, 1fr); }
  .ct-header, .ct-row { grid-template-columns: 2fr 1fr 1fr; }
  .ct-header > *:nth-child(3), .ct-row > *:nth-child(3) { display: none; }
}
@media (max-width: 600px) {
  .packs-grid { grid-template-columns: 1fr; }
  .enterprise-inner { flex-direction: column; text-align: center; }
}
</style>
