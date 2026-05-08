/**
 * 登录后截图脚本 - 确保登录成功后再截取所有功能页面
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
    await page.waitForTimeout(3000);

    // 填写用户名
    const usernameInput = page.locator('input[type="text"]');
    if (await usernameInput.isVisible().catch(() => false)) {
        await usernameInput.fill(TEST_USERNAME);
    } else {
        // 如果找不到type=text的input，尝试第一个input
        await page.locator('input').first().fill(TEST_USERNAME);
    }
    await page.waitForTimeout(500);

    // 填写密码
    const passwordInput = page.locator('input[type="password"]');
    await passwordInput.fill(TEST_PASSWORD);
    await page.waitForTimeout(500);

    // 点击登录按钮 (submit类型，文本是"登 录")
    const loginButton = page.locator('button[type="submit"]');
    await loginButton.click();

    // 等待登录完成
    try {
        // 等待按钮文字变为"登录中..."后再变为其他状态
        await page.waitForTimeout(5000);

        // 等待跳转到首页
        await page.waitForFunction(() => {
            return !window.location.pathname.includes('/login');
        }, { timeout: 15000 });

        // 再等待页面完全加载
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(3000);

        console.log('登录成功！当前URL:', await page.url());
        return true;
    } catch (e) {
        console.log('登录可能失败或超时:', e.message);
        console.log('当前URL:', await page.url());

        // 打印页面内容帮助调试
        const html = await page.content();
        console.log('页面包含登录按钮:', html.includes('登 录'));
        console.log('页面包含错误信息:', html.includes('error') || html.includes('失败'));

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

async function screenshot(page, url, name, waitTime = 4000) {
    console.log(`正在截取 ${name}...`);
    try {
        await page.goto(url, { timeout: 30000, waitUntil: 'networkidle' });

        // 检查是否被重定向到登录页
        const currentUrl = await page.url();
        if (currentUrl.includes('/login')) {
            console.log(`  ⚠ ${name} 被重定向到登录页，可能未登录成功`);
            return null;
        }

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
            await browser.close();
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

        // ============ 设置页面 ============
        const settingsResult = await screenshot(page, `${FRONTEND_URL}/settings`, '15_settings_general');
        if (settingsResult) {
            screenshots.push(settingsResult);

            // 尝试点击各个设置Tab
            const settingsTabs = [
                { text: 'API', name: '16_settings_api' },
                { text: '媒体库', name: '17_settings_libraries' },
                { text: '下载', name: '18_settings_download' },
                { text: '定时', name: '19_settings_scheduler' },
                { text: '通知', name: '20_settings_notify' },
                { text: '账户', name: '21_settings_account' },
                { text: '用户', name: '22_settings_users' },
                { text: '系统', name: '23_settings_system' },
                { text: '刮削', name: '24_settings_scrape' },
                { text: '成人', name: '25_settings_adult' },
                { text: '许可', name: '26_settings_license' },
            ];

            for (const tab of settingsTabs) {
                try {
                    console.log(`正在点击并截取 ${tab.name}...`);
                    const tabButton = page.locator(`button:has-text("${tab.text}")`).first();
                    if (await tabButton.isVisible().catch(() => false)) {
                        await tabButton.click();
                        await page.waitForTimeout(2000);
                        await anonymizePage(page);

                        const filePath = path.join(OUTPUT_DIR, `${tab.name}.png`);
                        await page.screenshot({
                            path: filePath,
                            fullPage: false,
                            timeout: 30000
                        });
                        screenshots.push(filePath);
                        console.log(`  ✓ ${tab.name} 截图成功`);
                    }
                } catch (e) {
                    console.log(`  ✗ ${tab.name} 截图失败: ${e.message}`);
                }
            }
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
