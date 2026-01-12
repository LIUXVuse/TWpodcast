import { defineConfig } from 'vitepress'

export default defineConfig({
    title: "Podcast 摘要",
    description: "財經 Podcast 的 AI 智慧摘要與逐字稿",
    base: "/TWpodcast/",
    cleanUrls: true,
    appearance: 'dark',

    themeConfig: {
        logo: { text: '🎙️ 財經 Podcast' },
        siteTitle: 'Podcast 摘要庫',

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

        nav: [
            { text: '首頁', link: '/' },
            { text: '所有摘要', link: '/summaries/' }
        ],

        sidebar: require('./sidebar.json'),

        socialLinks: [
            { icon: 'github', link: 'https://github.com/LIUXVuse/TWpodcast' }
        ],

        footer: {
            message: 'Powered by AI & VitePress.',
            copyright: 'Copyright © 2024 RSS Podcast Project'
        },

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
