/**
 * Рендер картинки для соцсетей: images/og-cover.jpg, 1200x630.
 *
 * ВКонтакте, Telegram и Facebook не принимают SVG в og:image, поэтому обложку
 * готовим растром заранее и кладём в репозиторий. Перезапускать нужно только
 * если поменялся логотип или подпись в tools/og-template.html.
 *
 * Запуск:  node tools/make-og.js
 * Требует: npm i playwright && npx playwright install chromium
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const ROOT = path.resolve(__dirname, '..');
const TEMPLATE = path.join(ROOT, 'tools', 'og-template.html');
const OUT = path.join(ROOT, 'images', 'og-cover.jpg');

(async () => {
    fs.mkdirSync(path.dirname(OUT), { recursive: true });

    const browser = await chromium.launch();
    const page = await browser.newPage({
        viewport: { width: 1200, height: 630 },
        deviceScaleFactor: 1,
    });

    await page.goto('file://' + TEMPLATE, { waitUntil: 'networkidle' });
    // JPEG: у обложки градиентный фон, PNG на нём весит втрое больше без выигрыша
    await page.screenshot({ path: OUT, type: 'jpeg', quality: 92 });
    await browser.close();

    const kb = (fs.statSync(OUT).size / 1024).toFixed(1);
    console.log(`images/og-cover.jpg — 1200x630, ${kb} KB`);
})();
