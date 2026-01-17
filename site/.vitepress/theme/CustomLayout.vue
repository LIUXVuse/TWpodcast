<script setup>
import DefaultTheme from 'vitepress/theme'
import AudioPlayer from './components/AudioPlayer.vue'
import { useData } from 'vitepress'

const { Layout } = DefaultTheme
const { frontmatter } = useData()
</script>

<template>
  <Layout>
    <template #doc-before>
      <AudioPlayer v-if="frontmatter.audioUrl" />
    </template>
  </Layout>
</template>
