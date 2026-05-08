/**
 * 脱敏截图脚本
 * 对 MediaStation 应用进行截图，对敏感信息进行脱敏处理
 */

const { chromium } = require('playwright');

const BACKEND_URL = 'http://localhost:3001';
const FRONTEND_URL = 'http://localhost:3002';

// 管理员测试账号（用于截图）
const TEST_USERNAME = 'admin';
const TEST_PASSWORD = 'admin123';

async function login(page) {
    console.log('正在登录...');
    await page.goto(`${FRONTEND_URL}/login`);

    // 等待页面加载
    await page.waitForLoadState('networkidle');

    // 填写登录表单
    const usernameInput = page.locator('input[type="text"], input[name="username"], input[placeholder*="用户"]').first();
    const passwordInput = page.locator('input[type="password"]').first();

    if (await usernameInput.isVisible()) {
        await usernameInput.fill(TEST_USERNAME);
        await passwordInput.fill(TEST_PASSWORD);

        // 点击登录按钮
        const loginBtn = page.locator('button[type="submit"], button:has-text("登录")').first();
        if (await loginBtn.isVisible()) {
            await loginBtn.click();
        }

        // 等待登录完成
        await page.waitForTimeout(2000);
    }
}

async function anonymizePage(page) {
    // 脱敏处理：隐藏或替换敏感信息
    await page.evaluate(() => {
        // 隐藏API keys和tokens
        const sensitivePatterns = [
            /api[_-]?key/i,
            /secret/i,
            /token/i,
            /password/i,
            /cookie/i,
            /auth/i,
        ];

        // 查找并替换敏感文本
        const textNodes = document.createTreeWalker(
            document.body,
            NodeFilter.SHOW_TEXT,
            null,
            false
        );

        const nodesToReplace = [];
        while (textNodes.nextNode()) {
            const node = textNodes.currentNode;
            const text = node.textContent;

            // 检查是否包含敏感关键词
            for (const pattern of sensitivePatterns) {
                if (pattern.test(text) && text.length < 100) {
                    nodesToReplace.push({
                        node: node,
                        replacement: '[已脱敏]'
                    });
                    break;
                }
            }
        }

        nodesToReplace.forEach(({node, replacement}) => {
            if (node.textContent.trim()) {
                node.textContent = replacement;
            }
        });

        // 隐藏邮箱
        document.querySelectorAll('*[class*="email"], *[class*="mail"]').forEach(el => {
            if (el.textContent.includes('@')) {
                el.textContent = '[已脱敏邮箱]';
            }
        });

        // 隐藏IP地址（除了127.0.0.1和localhost）
        document.querySelectorAll('*').forEach(el => {
            const text = el.textContent;
            const ipRegex = /\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b/g;
            if (ipRegex.test(text) && !text.includes('127.0.0.1') && !text.includes('localhost')) {
                el.textContent = el.textContent.replace(ipRegex, '[已脱敏IP]');
            }
        });

        // 隐藏cookie值
        document.querySelectorAll('*[class*="cookie"], *[class*="Cookie"]').forEach(el => {
            if (el.textContent.length > 20) {
                el.textContent = '[已脱敏Cookie]';
            }
        });

        console.log('页面脱敏完成');
    });
}

async function takeScreenshots() {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
        viewport: { width: 1920, height: 1080 }
    });
    const page = await context.newPage();

    const screenshots = [];

    try {
        // 1. 登录
        await login(page);
        await page.waitForTimeout(1000);

        // 2. 首页/仪表盘
        console.log('正在截取首页...');
        await page.goto(FRONTEND_URL);
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(2000);
        await anonymizePage(page);
        await page.screenshot({ path: 'screenshots/01_dashboard.png', fullPage: false });
        screenshots.push('screenshots/01_dashboard.png');

        // 3. 媒体库页面
        console.log('正在截取媒体库...');
        await page.goto(`${FRONTEND_URL}/library`);
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(2000);
        await anonymizePage(page);
        await page.screenshot({ path: 'screenshots/02_library.png', fullPage: false });
        screenshots.push('screenshots/02_library.png');

        // 4. 媒体详情页
        console.log('正在截取媒体详情...');
        await page.goto(`${FRONTEND_URL}/media/22`);
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(2000);
        await anonymizePage(page);
        await page.screenshot({ path: 'screenshots/03_media_detail.png', fullPage: false });
        screenshots.push('screenshots/03_media_detail.png');

        // 5. 设置页面
        console.log('正在截取设置页面...');
        await page.goto(`${FRONTEND_URL}/settings`);
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(2000);
        await anonymizePage(page);
        await page.screenshot({ path: 'screenshots/04_settings.png', fullPage: false });
        screenshots.push('screenshots/04_settings.png');

        // 6. 播放页面
        console.log('正在截取播放页面...');
        await page.goto(`${FRONTEND_URL}/player/22`);
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(2000);
        await anonymizePage(page);
        await page.screenshot({ path: 'screenshots/05_player.png', fullPage: false });
        screenshots.push('screenshots/05_player.png');

        console.log('\n截图完成！');
        console.log('截图保存位置: screenshots/');

    } catch (error) {
        console.error('截图过程中出错:', error.message);
    } finally {
        await browser.close();
    }

    return screenshots;
}

// 运行
const fs = require('fs');
if (!fs.existsSync('screenshots')) {
    fs.mkdirSync('screenshots', { recursive: true });
}

takeScreenshots()
    .then(files => {
        console.log('\n已保存的截图:');
        files.forEach(f => console.log('  -', f));
    })
    .catch(console.error);
