/**
 * 有头模式截图脚本 - 使用可见浏览器
 */

const { chromium } = require('playwright');

const FRONTEND_URL = 'http://localhost:3002';
const TEST_USERNAME = 'admin';
const TEST_PASSWORD = 'admin123';

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
    } catch (e) {
        console.log('登录过程出现问题:', e.message);
    }
}

async function anonymizePage(page) {
    await page.evaluate(() => {
        const sensitivePatterns = [
            /api[_-]?key/i, /secret/i, /token/i, /password/i, /cookie/i, /auth/i,
            /eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g,
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

        console.log('脱敏完成');
    });
}

async function takeScreenshots() {
    let browser;
    try {
        browser = await chromium.launch({
            headless: true, // 尝试无头模式，但配置更长的等待时间
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
        await login(page);

        const pages = [
            { url: FRONTEND_URL, name: '01_dashboard' },
            { url: `${FRONTEND_URL}/library`, name: '02_library' },
            { url: `${FRONTEND_URL}/browse`, name: '03_browse' },
            { url: `${FRONTEND_URL}/media/22`, name: '04_media_detail' },
            { url: `${FRONTEND_URL}/settings`, name: '05_settings' },
            { url: `${FRONTEND_URL}/dlna`, name: '06_dlna' },
        ];

        for (const p of pages) {
            console.log(`正在截取 ${p.name}...`);
            try {
                await page.goto(p.url, { timeout: 30000, waitUntil: 'networkidle' });

                // 等待 Vue 应用挂载
                await page.waitForSelector('#app', { timeout: 10000 });
                await page.waitForTimeout(3000);

                // 强制渲染
                await page.evaluate(() => document.body.style.opacity = '1');

                await anonymizePage(page);

                await page.screenshot({
                    path: `screenshots/${p.name}.png`,
                    fullPage: false,
                    timeout: 30000
                });
                screenshots.push(`screenshots/${p.name}.png`);
                console.log(`  ✓ ${p.name} 截图成功`);
            } catch (e) {
                console.log(`  ✗ ${p.name} 截图失败: ${e.message}`);
            }
        }

        console.log('\n截图完成！');

    } catch (error) {
        console.error('截图过程中出错:', error.message);
    } finally {
        await browser.close();
    }

    return screenshots;
}

takeScreenshots()
    .then(files => {
        console.log('\n已保存的截图:');
        files.forEach(f => console.log('  -', f));
    })
    .catch(console.error);
