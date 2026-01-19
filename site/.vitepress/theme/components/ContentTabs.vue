<script setup>
import { computed } from 'vue'
import { useRoute } from 'vitepress'

const route = useRoute()

// 判斷當前是摘要頁
const isSummaryPage = computed(() => route.path.includes('/summaries/'))
</script>

<template>
  <div v-if="isSummaryPage" class="content-tabs">
    <!-- 只顯示摘要標籤 -->
    <div class="tab-buttons">
      <a 
        class="tab-btn active"
        href="javascript:void(0)"
      >
        📋 摘要
      </a>
    </div>
  </div>
</template>

<style scoped>
.content-tabs {
  margin-bottom: 1.5rem;
  border-bottom: 1px solid var(--vp-c-divider);
  padding-bottom: 0;
}

.tab-buttons {
  display: flex;
  gap: 0;
}

.tab-btn {
  padding: 0.75rem 1.5rem;
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--vp-c-text-2);
  text-decoration: none;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
  cursor: pointer;
}

.tab-btn.active {
  color: var(--vp-c-brand-1);
  border-bottom-color: var(--vp-c-brand-1);
}
</style>
