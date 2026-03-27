const fs = require('fs');
const path = require('path');

const SOURCE_DIR = path.resolve(__dirname, '../../data/summaries');
const TARGET_DIR = path.resolve(__dirname, '../summaries');

// Ensure target directory exists
if (!fs.existsSync(TARGET_DIR)) {
    fs.mkdirSync(TARGET_DIR, { recursive: true });
}

// 1. Copy Files and Organize Data
console.log('📦 同步與整理摘要檔案...');
const allFiles = fs.readdirSync(SOURCE_DIR).filter(file => file.endsWith('.md'));

const files = allFiles.filter(file => file !== 'anchor_insights.md');

// Data structure to hold grouped episodes
const podcastGroups = {};

// Regex to parse filename: "ShowName" + "EPxxx" + "_summary.md"
// Example: "Money DJEP460_summary.md" -> Show: "Money DJ", Ep: "EP460"
const filenameRegex = /^(.*)(EP\d+)_summary\.md$/;

files.forEach(file => {
    const sourcePath = path.join(SOURCE_DIR, file);
    const targetPath = path.join(TARGET_DIR, file);

    // Copy file
    fs.copyFileSync(sourcePath, targetPath);

    // Parse filename
    const match = file.match(filenameRegex);

    let showName = 'Other';
    let epName = file.replace('.md', '');

    if (match) {
        showName = match[1].trim(); // "Money DJ"
        epName = match[2];          // "EP460"
    }

    if (!podcastGroups[showName]) {
        podcastGroups[showName] = [];
    }

    podcastGroups[showName].push({
        text: epName,
        link: `/summaries/${file}`,
        filename: file
    });
});

console.log(`✅ 已同步 ${files.length} 個檔案，共分為 ${Object.keys(podcastGroups).length} 個節目群組。`);

// 2. Generate Summaries Index Page (Clean Layout)
let indexContent = `# 節目摘要總覽\n\n`;
indexContent += `這裡依照節目分類，收錄了所有自動生成的 Podcast 摘要。\n\n`;

// Iterate through groups to build the page content
for (const [show, episodes] of Object.entries(podcastGroups)) {
    // Sort episodes (assuming EP number is sortable, but clear string sort is okay for now)
    // Reverse sort to show newest first? "EP464" > "EP460"
    episodes.sort((a, b) => b.text.localeCompare(a.text, undefined, { numeric: true }));

    indexContent += `## ${show}\n`;
    indexContent += `::: details 點擊展開集數列表 (${episodes.length} 集)\n`;
    episodes.forEach(ep => {
        // Fix: Encode URI to handle spaces in filenames
        const safeLink = encodeURI(ep.link);
        indexContent += `- [${ep.text}](${safeLink})\n`;
    });
    indexContent += `:::\n\n`;
}

fs.writeFileSync(path.join(TARGET_DIR, 'index.md'), indexContent);
console.log('📝 已更新 summaries/index.md (包含分類顯示)');

// 3. Generate Sidebar Config (Collapsible)
const sidebarItems = [];

for (const [show, episodes] of Object.entries(podcastGroups)) {
    // Sort for sidebar as well
    episodes.sort((a, b) => b.text.localeCompare(a.text, undefined, { numeric: true }));

    sidebarItems.push({
        text: show,
        collapsed: true, // Default to collapsed to save space
        items: episodes.map(ep => ({
            text: ep.text,
            link: ep.link
        }))
    });
}

const sidebarConfig = {
    '/summaries/': [
        {
            text: '節目列表',
            items: sidebarItems
        }
    ]
};

fs.writeFileSync(path.resolve(__dirname, '../.vitepress/sidebar.json'), JSON.stringify(sidebarConfig, null, 2));
console.log('✅ 已更新側邊欄設定 (自動折疊群組)');
