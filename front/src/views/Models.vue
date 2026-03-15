<template>
  <main class="models-page">
    <div class="orb" style="width:500px;height:500px;background:radial-gradient(circle,rgba(99,102,241,0.12) 0%,transparent 70%);top:0;right:0;pointer-events:none;"></div>

    <div class="container">
      <!-- Header -->
      <div class="page-header">
        <span class="tag tag-purple">50+ 模型</span>
        <h1 class="page-title">AI 模型广场</h1>
        <p class="page-desc">汇聚全球顶级 AI 模型，覆盖文本、代码、图像、音频等多种能力，满足所有使用场景。</p>
      </div>

      <!-- Filters -->
      <div class="filters">
        <button v-for="cat in categories" :key="cat.id"
          class="filter-btn" :class="{ active: activeCategory === cat.id }"
          @click="activeCategory = cat.id">
          {{ cat.label }}
        </button>
      </div>

      <!-- Models Grid -->
      <div class="all-models-grid">
        <div v-for="m in filteredModels" :key="m.id" class="model-full-card card">
          <div class="mfc-header">
            <div class="mfc-avatar" :style="{ background: m.gradient }">{{ m.emoji }}</div>
            <div>
              <span class="mfc-provider">{{ m.provider }}</span>
              <h3 class="mfc-name">{{ m.name }}</h3>
            </div>
            <div class="mfc-badges">
              <span v-if="m.isNew" class="badge-new">NEW</span>
              <span v-if="m.isHot" class="badge-hot">HOT</span>
              <span class="tag tag-sm" :class="m.tagClass">{{ m.tag }}</span>
            </div>
          </div>

          <p class="mfc-desc">{{ m.desc }}</p>

          <!-- <div class="mfc-specs">
            <div class="spec"><span class="spec-label">上下文</span><span class="spec-val">{{ m.ctx }}</span></div>
            <div class="spec"><span class="spec-label">输入价格</span><span class="spec-val">{{ m.inputPrice }}</span></div>
            <div class="spec"><span class="spec-label">输出价格</span><span class="spec-val">{{ m.outputPrice }}</span></div>
          </div> -->

          <div class="mfc-caps">
            <span v-for="c in m.caps" :key="c" class="cap-chip">{{ c }}</span>
          </div>

          <!-- <div class="mfc-footer">
            <RouterLink to="/register" class="btn btn-primary" style="font-size:13px;padding:10px 20px">开始使用</RouterLink>
            <button class="btn btn-outline" style="font-size:13px;padding:10px 20px">查看文档</button>
          </div> -->
        </div>
      </div>
    </div>
  </main>
</template>

<script setup>
import { ref, computed } from 'vue'

const categories = [
  { id: 'all', label: '全部' },
  { id: 'text', label: '文本对话' },
  { id: 'code', label: '代码生成' },
  { id: 'multimodal', label: '多模态' },
  { id: 'reasoning', label: '深度推理' },
  { id: 'open', label: '开源模型' },
]

const activeCategory = ref('all')

const allModels = [
  { id:1, provider:'OpenAI', name:'GPT-5', emoji:'🤖', gradient:'linear-gradient(135deg,#10a37f,#1a7f64)', tag:'多模态', tagClass:'tag-green', desc:'OpenAI 最强旗舰，支持文字图像音频，综合能力第一梯队。', ctx:'128K', inputPrice:'¥0.035/1K', outputPrice:'¥0.105/1K', caps:['文本','图像','语音','代码'], categories:['text','multimodal','code'], isHot:true },
  { id:2, provider:'OpenAI', name:'GPT-4o mini', emoji:'⚡', gradient:'linear-gradient(135deg,#10a37f,#047857)', tag:'轻量', tagClass:'tag-green', desc:'GPT-4o 的精简版，速度快，价格低，适合高频调用场景。', ctx:'128K', inputPrice:'¥0.0021/1K', outputPrice:'¥0.0084/1K', caps:['文本','代码','快速'], categories:['text','code'] },
  { id:3, provider:'Anthropic', name:'Claude 4.6 opus', emoji:'🧮', gradient:'linear-gradient(135deg,#2563eb,#1e40af)', tag:'推理', tagClass:'tag-cyan', desc:'专为复杂推理设计，数学、科学、代码问题处理能力超强。', ctx:'200K', inputPrice:'¥0.105/1K', outputPrice:'¥0.42/1K', caps:['深度推理','数学','科学','代码'], categories:['reasoning'], isNew:true },
  { id:4, provider:'Anthropic', name:'Claude 4.6 Sonnet', emoji:'🧠', gradient:'linear-gradient(135deg,#d97706,#92400e)', tag:'推理强', tagClass:'tag-purple', desc:'Anthropic 旗舰模型，深度推理卓越，长文档处理能力第一。', ctx:'200K', inputPrice:'¥0.022/1K', outputPrice:'¥0.11/1K', caps:['推理','文档','创作','代码'], categories:['text','reasoning'], isHot:true },
  { id:5, provider:'Anthropic', name:'Claude 4.5 Haiku', emoji:'📝', gradient:'linear-gradient(135deg,#b45309,#78350f)', tag:'快速', tagClass:'tag-green', desc:'Claude 系列最快最轻量模型，低成本高效率，适合批量处理。', ctx:'200K', inputPrice:'¥0.0056/1K', outputPrice:'¥0.028/1K', caps:['快速','轻量','文本'], categories:['text'] },
  { id:6, provider:'Google', name:'Gemini 1.5 Pro', emoji:'💫', gradient:'linear-gradient(135deg,#4285f4,#1a56db)', tag:'超长', tagClass:'tag-cyan', desc:'谷歌旗舰，100万token上下文，多模态能力出众。', ctx:'1M', inputPrice:'¥0.025/1K', outputPrice:'¥0.075/1K', caps:['超长上下文','多模态','多语言'], categories:['text','multimodal'] },
  { id:7, provider:'Google', name:'Gemini 2.0 Flash', emoji:'🚀', gradient:'linear-gradient(135deg,#1967d2,#0d47a1)', tag:'最新', tagClass:'tag-cyan', desc:'谷歌最新一代模型，速度更快，能力更强，性价比极佳。', ctx:'1M', inputPrice:'¥0.0021/1K', outputPrice:'¥0.0084/1K', caps:['快速','多模态','代码'], categories:['text','multimodal','code'], isNew:true },
  { id:8, provider:'DeepSeek', name:'DeepSeek-V3', emoji:'🔍', gradient:'linear-gradient(135deg,#6366f1,#4338ca)', tag:'开源', tagClass:'tag-purple', desc:'顶级国产开源大模型，中文理解与数学能力媲美闭源模型。', ctx:'64K', inputPrice:'¥0.002/1K', outputPrice:'¥0.008/1K', caps:['中文','数学','代码','推理'], categories:['text','code','open'], isHot:true },
  { id:9, provider:'DeepSeek', name:'DeepSeek-R1', emoji:'🎯', gradient:'linear-gradient(135deg,#7c3aed,#5b21b6)', tag:'推理', tagClass:'tag-purple', desc:'DeepSeek 推理专项模型，复杂逻辑推理能力媲美 o1。', ctx:'64K', inputPrice:'¥0.004/1K', outputPrice:'¥0.016/1K', caps:['深度推理','数学','代码'], categories:['reasoning','code'], isNew:true },
  { id:10, provider:'Meta', name:'Llama 3.1 405B', emoji:'🦙', gradient:'linear-gradient(135deg,#0284c7,#075985)', tag:'开源', tagClass:'tag-cyan', desc:'Meta 最大参数量开源模型，综合能力强大，可私有化部署。', ctx:'128K', inputPrice:'¥0.009/1K', outputPrice:'¥0.009/1K', caps:['开源','多语言','代码','对话'], categories:['text','code','open'] },
  { id:11, provider:'Meta', name:'Llama 3.2 Vision', emoji:'👁️', gradient:'linear-gradient(135deg,#0369a1,#0c4a6e)', tag:'视觉', tagClass:'tag-cyan', desc:'支持图像理解的多模态 Llama，开源视觉模型首选。', ctx:'128K', inputPrice:'¥0.011/1K', outputPrice:'¥0.011/1K', caps:['图像理解','开源','多模态'], categories:['multimodal','open'] },
  { id:12, provider:'Mistral AI', name:'Mistral Large 2', emoji:'⚡', gradient:'linear-gradient(135deg,#f97316,#c2410c)', tag:'欧洲', tagClass:'tag-green', desc:'欧洲最强商用模型，函数调用能力极强，企业级应用首选。', ctx:'128K', inputPrice:'¥0.028/1K', outputPrice:'¥0.084/1K', caps:['推理','函数调用','代码','多语言'], categories:['text','code'] },
]

const filteredModels = computed(() => {
  if (activeCategory.value === 'all') return allModels
  return allModels.filter(m => m.categories.includes(activeCategory.value))
})
</script>

<style scoped>
.models-page {
  padding-top: 100px;
  padding-bottom: 100px;
  position: relative;
  overflow: hidden;
}
.page-header {
  text-align: center;
  padding: 60px 0 48px;
}
.page-title {
  font-family: var(--font-display);
  font-size: clamp(32px, 4vw, 52px);
  font-weight: 800;
  margin: 16px 0 12px;
  letter-spacing: -0.02em;
}
.page-desc { color: var(--text-secondary); font-size: 16px; max-width: 500px; margin: 0 auto; }

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 40px;
  justify-content: center;
}
.filter-btn {
  padding: 9px 20px;
  border-radius: 999px;
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-secondary);
  font-size: 13.5px;
  font-weight: 500;
  cursor: pointer;
  transition: var(--transition);
  font-family: var(--font-body);
}
.filter-btn:hover { color: var(--text-primary); border-color: rgba(255,255,255,0.15); background: rgba(255,255,255,0.04); }
.filter-btn.active { background: var(--gradient-accent); color: #fff; border-color: transparent; box-shadow: 0 0 20px rgba(99,102,241,0.3); }

.all-models-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}
.model-full-card { padding: 24px; display: flex; flex-direction: column; gap: 14px; }
.mfc-header { display: flex; align-items: center; gap: 12px; }
.mfc-avatar {
  width: 48px; height: 48px;
  border-radius: var(--radius-md);
  display: flex; align-items: center; justify-content: center;
  font-size: 24px; flex-shrink: 0;
}
.mfc-provider { font-size: 11px; color: var(--text-muted); display: block; }
.mfc-name { font-family: var(--font-display); font-size: 16px; font-weight: 700; }
.mfc-badges { display: flex; gap: 6px; align-items: center; margin-left: auto; flex-shrink: 0; flex-wrap: wrap; justify-content: flex-end; }
.badge-new {
  padding: 3px 8px; border-radius: 4px; font-size: 10px; font-weight: 700;
  background: linear-gradient(135deg, #38bdf8, #6366f1); color: #fff; font-family: var(--font-display);
}
.badge-hot {
  padding: 3px 8px; border-radius: 4px; font-size: 10px; font-weight: 700;
  background: linear-gradient(135deg, #f97316, #ef4444); color: #fff; font-family: var(--font-display);
}
.tag-sm { font-size: 10px; padding: 3px 8px; }
.mfc-desc { color: var(--text-secondary); font-size: 13px; line-height: 1.65; flex: 1; }
.mfc-specs {
  display: flex; gap: 0;
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}
.spec { flex: 1; padding: 10px 14px; display: flex; flex-direction: column; gap: 3px; }
.spec:not(:last-child) { border-right: 1px solid var(--border); }
.spec-label { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
.spec-val { font-size: 12px; font-family: monospace; color: var(--accent-cyan); font-weight: 600; }
.mfc-caps { display: flex; flex-wrap: wrap; gap: 6px; }
.cap-chip {
  padding: 4px 10px;
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 11px;
  color: var(--text-secondary);
}
.mfc-footer { display: flex; gap: 10px; padding-top: 4px; }

@media (max-width: 1024px) { .all-models-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 600px) { .all-models-grid { grid-template-columns: 1fr; } }
</style>
