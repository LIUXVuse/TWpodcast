<script setup>
import { useData } from 'vitepress'

const { frontmatter } = useData()
</script>

<template>
  <div v-if="frontmatter.audioUrl" class="audio-player">
    <div class="player-header">
      <span class="player-icon">🎧</span>
      <span class="player-title">收聽本集 Podcast</span>
    </div>
    <audio controls preload="metadata" class="audio-element">
      <source :src="frontmatter.audioUrl" type="audio/mpeg">
      您的瀏覽器不支援音訊播放
    </audio>
    <div v-if="frontmatter.transcriptLink" class="player-links">
      <a :href="frontmatter.transcriptLink" class="transcript-link">
        📝 查看完整逐字稿
      </a>
    </div>
  </div>
</template>

<style scoped>
.audio-player {
  margin: 1.5rem 0;
  padding: 1.25rem;
  background: linear-gradient(135deg, var(--vp-c-bg-soft) 0%, var(--vp-c-bg-mute) 100%);
  border-radius: 12px;
  border: 1px solid var(--vp-c-divider);
}

.player-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
  font-weight: 600;
  color: var(--vp-c-text-1);
}

.player-icon {
  font-size: 1.25rem;
}

.player-title {
  font-size: 0.95rem;
}

.audio-element {
  width: 100%;
  height: 40px;
  border-radius: 8px;
}

.audio-element::-webkit-media-controls-panel {
  background: var(--vp-c-bg);
}

.player-links {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--vp-c-divider);
}

.transcript-link {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--vp-c-brand-1);
  text-decoration: none;
  font-size: 0.9rem;
  transition: color 0.2s;
}

.transcript-link:hover {
  color: var(--vp-c-brand-2);
  text-decoration: underline;
}
</style>
