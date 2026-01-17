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
            { text: '節目列表', link: '/podcasts/' }
        ],

        sidebar: require('./sidebar.json'),

        socialLinks: [
            { icon: 'github', link: 'https://github.com/LIUXVuse/TWpodcast' },
            {
                icon: {
                    svg: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>'
                },
                link: 'https://t.me/twpodcast'
            }
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
