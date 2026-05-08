/**
 * 完整功能截图脚本 - 登录后截取所有功能页面
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const FRONTEND_URL = 'http://localhost:3002';
const TEST_USERNAME = 'admin';
const TEST_PASSWORD = 'admin123';
const OUTPUT_DIR = 'screenshots';

// 确保截图目录存在
if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

async function login(page) {
    console.log('正在登录...');
    await page.goto(`${FRONTEND_URL}/login`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const usernameInput = page.locator('input').first();
    const passwordInput = page.locator('input[type="password"]').first();

    try {
        await usernameInput.fill(TEST_USERNAME);
        await passwordInput.fill(TEST_PASSWORD);
        await page.waitForTimeout(500);
        await page.keyboard.press('Enter');
        await page.waitForTimeout(3000);
        console.log('登录完成');
        return true;
    } catch (e) {
        console.log('登录失败:', e.message);
        return false;
    }
}

async function anonymizePage(page) {
    await page.evaluate(() => {
        const sensitivePatterns = [
            /api[_-]?key/i, /secret/i, /token/i, /password/i, /cookie/i, /auth/i,
            /eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g,
            /sk-[A-Za-z0-9_-]+/g,
        ];

        const textNodes = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
        const nodesToReplace = [];

        while (textNodes.nextNode()) {
            const node = textNodes.currentNode;
            const text = node.textContent;

            for (const pattern of sensitivePatterns) {
                if (pattern.test(text)) {
                    nodesToReplace.push({ node, replacement: '[已脱敏]' });
                    break;
                }
            }
        }

        nodesToReplace.forEach(({node, replacement}) => {
            if (node.textContent.trim().length > 0 && node.textContent.length < 200) {
                node.textContent = replacement;
            }
        });

        document.querySelectorAll('*[class*="email"], *[class*="mail"]').forEach(el => {
            if (el.textContent.includes('@') && el.textContent.length < 100) {
                el.textContent = '[已脱敏邮箱]';
            }
        });
    });
}

async function screenshot(page, url, name, waitTime = 3000) {
    console.log(`正在截取 ${name}...`);
    try {
        await page.goto(url, { timeout: 30000, waitUntil: 'networkidle' });
        await page.waitForSelector('#app', { timeout: 10000 });
        await page.waitForTimeout(waitTime);
        await page.evaluate(() => document.body.style.opacity = '1');
        await anonymizePage(page);

        const filePath = path.join(OUTPUT_DIR, `${name}.png`);
        await page.screenshot({
            path: filePath,
            fullPage: false,
            timeout: 30000
        });
        console.log(`  ✓ ${name} 截图成功`);
        return filePath;
    } catch (e) {
        console.log(`  ✗ ${name} 截图失败: ${e.message}`);
        return null;
    }
}

async function clickAndScreenshot(page, selector, name) {
    console.log(`正在点击并截取 ${name}...`);
    try {
        await page.click(selector);
        await page.waitForTimeout(2000);
        await anonymizePage(page);

        const filePath = path.join(OUTPUT_DIR, `${name}.png`);
        await page.screenshot({
            path: filePath,
            fullPage: false,
            timeout: 30000
        });
        console.log(`  ✓ ${name} 截图成功`);
        return filePath;
    } catch (e) {
        console.log(`  ✗ ${name} 截图失败: ${e.message}`);
        return null;
    }
}

async function main() {
    let browser;
    try {
        browser = await chromium.launch({
            headless: true,
            args: ['--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage']
        });
    } catch (e) {
        console.log('无法启动浏览器:', e.message);
        return [];
    }

    const context = await browser.newContext({
        viewport: { width: 1920, height: 1080 },
        userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    });
    const page = await context.newPage();
    const screenshots = [];

    try {
        // 登录
        const loggedIn = await login(page);
        if (!loggedIn) {
            console.log('登录失败，无法继续截图');
            return [];
        }

        // ============ 主导航页面 ============
        const mainPages = [
            { url: FRONTEND_URL, name: '01_dashboard' },
            { url: `${FRONTEND_URL}/discover`, name: '02_discover' },
            { url: `${FRONTEND_URL}/media`, name: '03_media_library' },
            { url: `${FRONTEND_URL}/poster-wall`, name: '04_poster_wall' },
            { url: `${FRONTEND_URL}/favorites`, name: '05_favorites' },
            { url: `${FRONTEND_URL}/history`, name: '06_watch_history' },
            { url: `${FRONTEND_URL}/downloads`, name: '07_downloads' },
            { url: `${FRONTEND_URL}/subscriptions`, name: '08_subscriptions' },
            { url: `${FRONTEND_URL}/sites`, name: '09_sites' },
            { url: `${FRONTEND_URL}/ai-assistant`, name: '10_ai_assistant' },
            { url: `${FRONTEND_URL}/profiles-management`, name: '11_profiles_management' },
            { url: `${FRONTEND_URL}/storage`, name: '12_storage' },
            { url: `${FRONTEND_URL}/files`, name: '13_file_manager' },
            { url: `${FRONTEND_URL}/strm`, name: '14_strm' },
        ];

        for (const p of mainPages) {
            const result = await screenshot(page, p.url, p.name);
            if (result) screenshots.push(result);
        }

        // ============ 设置页面及各个Tab ============
        await screenshot(page, `${FRONTEND_URL}/settings`, '15_settings_general');

        // 点击各个设置Tab
        const settingsTabs = [
            { selector: 'text=API配置', name: '16_settings_api' },
            { selector: 'text=媒体库', name: '17_settings_libraries' },
            { selector: 'text=下载设置', name: '18_settings_download' },
            { selector: 'text=定时任务', name: '19_settings_scheduler' },
            { selector: 'text=通知设置', name: '20_settings_notify' },
            { selector: 'text=账户', name: '21_settings_account' },
            { selector: 'text=用户管理', name: '22_settings_users' },
            { selector: 'text=系统', name: '23_settings_system' },
            { selector: 'text=刮削', name: '24_settings_scrape' },
            { selector: 'text=成人内容', name: '25_settings_adult' },
            { selector: 'text=许可证', name: '26_settings_license' },
        ];

        for (const tab of settingsTabs) {
            const result = await clickAndScreenshot(page, tab.selector, tab.name);
            if (result) screenshots.push(result);
        }

        // ============ 其他功能页面 ============
        const otherPages = [
            { url: `${FRONTEND_URL}/search`, name: '27_search' },
            { url: `${FRONTEND_URL}/playlist`, name: '28_playlist' },
            { url: `${FRONTEND_URL}/dlna`, name: '29_dlna' },
            { url: `${FRONTEND_URL}/profile`, name: '30_profile' },
        ];

        for (const p of otherPages) {
            const result = await screenshot(page, p.url, p.name);
            if (result) screenshots.push(result);
        }

        console.log('\n========================================');
        console.log(`截图完成！共 ${screenshots.length} 张截图`);
        console.log('========================================');

    } catch (error) {
        console.error('截图过程中出错:', error.message);
    } finally {
        await browser.close();
    }

    return screenshots;
}

main()
    .then(files => {
        console.log('\n已保存的截图:');
        files.forEach(f => console.log('  -', f));
    })
    .catch(console.error);
