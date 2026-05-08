/**
 * 最终截图脚本 - 确保页面完全加载后再截图
 */

const { chromium } = require('playwright');

const FRONTEND_URL = 'http://localhost:3002';
const TEST_USERNAME = 'admin';
const TEST_PASSWORD = 'admin123';

async function login(page) {
    console.log('正在登录...');
    await page.goto(`${FRONTEND_URL}/login`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const usernameInput = page.locator('input[type="text"], input[name="username"], input[placeholder*="用户"], input').filter({ hasText: '' }).first();
    const passwordInput = page.locator('input[type="password"]').first();

    try {
        await usernameInput.fill(TEST_USERNAME);
        await passwordInput.fill(TEST_PASSWORD);

        const loginBtn = page.locator('button[type="submit"], button').filter({ hasText: /登录|登入/i }).first();
        if (await loginBtn.isVisible()) {
            await loginBtn.click();
        }
        await page.waitForTimeout(3000);
    } catch (e) {
        console.log('登录过程出现问题，继续...');
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

async function waitForAppReady(page) {
    // 等待 Vue 应用挂载
    await page.waitForSelector('#app', { timeout: 10000 });
    await page.waitForLoadState('domcontentloaded');

    // 等待一段时间让动态内容加载
    await page.waitForTimeout(3000);

    // 滚动页面触发懒加载
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(500);
}

async function takeScreenshots() {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
        viewport: { width: 1920, height: 1080 }
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
            { url: `${FRONTEND_URL}/player/22`, name: '05_player' },
            { url: `${FRONTEND_URL}/settings`, name: '06_settings' },
            { url: `${FRONTEND_URL}/downloads`, name: '07_downloads' },
            { url: `${FRONTEND_URL}/admin`, name: '08_admin' },
            { url: `${FRONTEND_URL}/dlna`, name: '09_dlna' },
            { url: `${FRONTEND_URL}/subscribe`, name: '10_subscribe' },
            { url: `${FRONTEND_URL}/emby`, name: '11_emby' },
        ];

        for (const p of pages) {
            console.log(`正在截取 ${p.name}...`);
            try {
                await page.goto(p.url, { timeout: 30000 });
                await waitForAppReady(page);
                await anonymizePage(page);
                await page.screenshot({
                    path: `screenshots/${p.name}.png`,
                    fullPage: true,
                    timeout: 30000
                });
                screenshots.push(`screenshots/${p.name}.png`);
            } catch (e) {
                console.log(`  截图 ${p.name} 失败: ${e.message}`);
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
        console.log('\n截图保存位置: screenshots/');
    })
    .catch(console.error);
