// .vitepress/theme/index.js
import DefaultTheme from 'vitepress/theme'
import './custom.css'
import CustomLayout from './CustomLayout.vue'
import AudioPlayer from './components/AudioPlayer.vue'

export default {
    extends: DefaultTheme,
    Layout: CustomLayout,
    enhanceApp({ app }) {
        // 註冊全域組件
        app.component('AudioPlayer', AudioPlayer)
    }
}
