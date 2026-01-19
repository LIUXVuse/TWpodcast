<script setup>
import { ref, computed, onMounted } from 'vue'
import { useData, useRoute } from 'vitepress'

const { frontmatter } = useData()
const route = useRoute()

// Tab 狀態
const activeTab = ref('summary')

// 逐字稿內容
const transcriptContent = ref('')
const transcriptLoading = ref(false)

// 計算逐字稿連結
const transcriptPath = computed(() => {
  if (frontmatter.value.transcriptLink) {
    return frontmatter.value.transcriptLink
  }
  // 從當前路徑推算逐字稿路徑
  const currentPath = route.path
  if (currentPath.includes('/summaries/')) {
    return currentPath.replace('/summaries/', '/transcripts/').replace('_summary', '_transcript')
  }
  return ''
})

const summaryPath = computed(() => {
  const currentPath = route.path
  if (currentPath.includes('/transcripts/')) {
    return currentPath.replace('/transcripts/', '/summaries/').replace('_transcript', '_summary')
  }
  return ''
})

// 判斷當前是摘要頁還是逐字稿頁
const isSummaryPage = computed(() => route.path.includes('/summaries/'))
const isTranscriptPage = computed(() => route.path.includes('/transcripts/'))
</script>

<template>
  <div v-if="isSummaryPage || isTranscriptPage" class="content-tabs">
    <!-- Tab 切換按鈕 -->
    <div class="tab-buttons">
      <a 
        v-if="isSummaryPage"
        class="tab-btn active"
        href="javascript:void(0)"
      >
        📋 摘要
      </a>
      <a 
        v-else
        class="tab-btn"
        :href="summaryPath"
      >
        📋 摘要
      </a>
      
      <a 
        v-if="isTranscriptPage"
        class="tab-btn active"
        href="javascript:void(0)"
      >
        📝 逐字稿
      </a>
      <!-- 只在摘要頁且逐字稿存在時才顯示連結 -->
      <a 
        v-else-if="isSummaryPage && frontmatter.hasTranscript"
        class="tab-btn"
        :href="transcriptPath"
      >
        📝 逐字稿
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

.tab-btn:hover:not(.disabled) {
  color: var(--vp-c-brand-1);
  background: var(--vp-c-bg-soft);
}

.tab-btn.active {
  color: var(--vp-c-brand-1);
  border-bottom-color: var(--vp-c-brand-1);
}

.tab-btn.disabled {
  color: var(--vp-c-text-3);
  cursor: not-allowed;
  opacity: 0.6;
}
</style>
