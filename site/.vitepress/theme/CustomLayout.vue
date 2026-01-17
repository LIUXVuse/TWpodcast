<script setup>
import DefaultTheme from 'vitepress/theme'
import AudioPlayer from './components/AudioPlayer.vue'
import ContentTabs from './components/ContentTabs.vue'
import { useData } from 'vitepress'

const { Layout } = DefaultTheme
const { frontmatter } = useData()
</script>

<template>
  <Layout>
    <template #doc-before>
      <!-- 播放器 -->
      <AudioPlayer v-if="frontmatter.audioUrl" />
      <!-- Tab 切換 -->
      <ContentTabs />
    </template>
  </Layout>
</template>
