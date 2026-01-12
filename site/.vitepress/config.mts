import { defineConfig } from 'vitepress'

export default defineConfig({
    title: "Podcast 摘要",
    description: "財經 Podcast 的 AI 智慧摘要與逐字稿",
    cleanUrls: true,
    appearance: 'dark', // 預設深色模式

    themeConfig: {
        logo: { text: '🎙️ 財經 Podcast' },
        siteTitle: 'Podcast 摘要庫',

        // 本地搜尋設定
        search: {
            provider: 'local',
            options: {
                translations: {
                    button: {
                        buttonText: '搜尋',
                        buttonAriaLabel: '搜尋'
                    },
                    modal: {
                        noResultsText: '找不到相關內容',
                        resetButtonTitle: '清除搜尋條件',
                        footer: {
                            selectText: '選擇',
                            navigateText: '切換',
                            closeText: '關閉'
                        }
                    }
                }
            }
        },

        // 導覽列：移除 About，全中文
        nav: [
            { text: '首頁', link: '/' },
            { text: '所有摘要', link: '/summaries/' }
        ],

        // 側邊欄：從 JSON 載入
        sidebar: require('./sidebar.json'),

        socialLinks: [
            // 如果沒有要放 GitHub 連結可以移除，或是換成您的
            { icon: 'github', link: 'https://github.com/your-repo' }
        ],

        footer: {
            message: 'Powered by AI & VitePress.',
            copyright: 'Copyright © 2024 RSS Podcast Project'
        },

        // UI 中文化
        outline: {
            level: [2, 3],
            label: '本頁目錄'
        },
        docFooter: {
            prev: '上一集',
            next: '下一集'
        },
        darkModeSwitchLabel: '深色模式',
        sidebarMenuLabel: '選單',
        returnToTopLabel: '回到頂部',
        langMenuLabel: '語言'
    },

    markdown: {
        lineNumbers: true,
    }
})
