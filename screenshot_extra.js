/**
 * 补充截图脚本 - 截取更多功能页面
 */

const { chromium } = require('playwright');

const FRONTEND_URL = 'http://localhost:3002';
const TEST_USERNAME = 'admin';
const TEST_PASSWORD = 'admin123';

async function login(page) {
    console.log('正在登录...');
    await page.goto(`${FRONTEND_URL}/login`);
    await page.waitForLoadState('networkidle');

    const usernameInput = page.locator('input[type="text"], input[name="username"], input[placeholder*="用户"]').first();
    const passwordInput = page.locator('input[type="password"]').first();

    if (await usernameInput.isVisible()) {
        await usernameInput.fill(TEST_USERNAME);
        await passwordInput.fill(TEST_PASSWORD);

        const loginBtn = page.locator('button[type="submit"], button:has-text("登录")').first();
        if (await loginBtn.isVisible()) {
            await loginBtn.click();
        }
        await page.waitForTimeout(2000);
    }
}

async function anonymizePage(page) {
    await page.evaluate(() => {
        const sensitivePatterns = [
            /api[_-]?key/i, /secret/i, /token/i, /password/i, /cookie/i, /auth/i,
        ];

        const textNodes = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
        const nodesToReplace = [];

        while (textNodes.nextNode()) {
            const node = textNodes.currentNode;
            const text = node.textContent;
            for (const pattern of sensitivePatterns) {
                if (pattern.test(text) && text.length < 100) {
                    nodesToReplace.push({ node, replacement: '[已脱敏]' });
                    break;
                }
            }
        }

        nodesToReplace.forEach(({node, replacement}) => {
            if (node.textContent.trim()) {
                node.textContent = replacement;
            }
        });

        document.querySelectorAll('*[class*="email"], *[class*="mail"]').forEach(el => {
            if (el.textContent.includes('@')) {
                el.textContent = '[已脱敏邮箱]';
            }
        });

        console.log('脱敏完成');
    });
}

async function takeScreenshots() {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
    const page = await context.newPage();

    const screenshots = [];

    try {
        await login(page);

        const pages = [
            { url: FRONTEND_URL, name: '06_home' },
            { url: `${FRONTEND_URL}/library`, name: '07_library_detail' },
            { url: `${FRONTEND_URL}/browse`, name: '08_browse' },
            { url: `${FRONTEND_URL}/downloads`, name: '09_downloads' },
            { url: `${FRONTEND_URL}/admin`, name: '10_admin' },
            { url: `${FRONTEND_URL}/emby`, name: '11_emby' },
            { url: `${FRONTEND_URL}/dlna`, name: '12_dlna' },
            { url: `${FRONTEND_URL}/subscribe`, name: '13_subscribe' },
        ];

        for (const p of pages) {
            console.log(`正在截取 ${p.name}...`);
            await page.goto(p.url);
            await page.waitForLoadState('networkidle');
            await page.waitForTimeout(2000);
            await anonymizePage(page);
            await page.screenshot({ path: `screenshots/${p.name}.png`, fullPage: false });
            screenshots.push(`screenshots/${p.name}.png`);
        }

        console.log('\n补充截图完成！');

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
