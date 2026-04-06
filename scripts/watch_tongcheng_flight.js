import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const statePath = process.env.TONGCHENG_STORAGE_STATE || path.resolve('browser_state/tongcheng-storage.json');
const debugDir = path.resolve('runtime_data/flight_debug');

async function saveDebug(page, prefix) {
  fs.mkdirSync(debugDir, { recursive: true });
  const stamp = `${Date.now()}-${prefix}`;
  const htmlPath = path.join(debugDir, `${stamp}.html`);
  const pngPath = path.join(debugDir, `${stamp}.png`);
  fs.writeFileSync(htmlPath, await page.content(), 'utf8');
  await page.screenshot({ path: pngPath, fullPage: true });
  return { htmlPath, pngPath };
}

async function dumpLinks(page) {
  const links = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('a'))
      .map(a => ({ text: (a.innerText || '').trim(), href: a.href || '' }))
      .filter(x => x.text || x.href)
      .slice(0, 300);
  });
  return links;
}

async function tryClick(page, candidates) {
  for (const text of candidates) {
    const loc = page.locator(`text=${text}`).first();
    if (await loc.count()) {
      console.log('TRY CLICK:', text);
      try {
        await loc.click({ timeout: 3000 });
        await page.waitForTimeout(4000);
        return text;
      } catch (e) {
        console.log('CLICK FAILED:', text, String(e));
      }
    }
  }
  return null;
}

async function main() {
  const browser = await chromium.launch({ headless: false, slowMo: 400 });
  const context = fs.existsSync(statePath)
    ? await browser.newContext({ storageState: statePath })
    : await browser.newContext();
  const page = await context.newPage();

  console.log('OPEN: https://www.ly.com/');
  await page.goto('https://www.ly.com/', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(5000);

  console.log('HOME TITLE:', await page.title());
  console.log('HOME URL:', page.url());
  console.log('HOME TEXT:', (await page.locator('body').innerText()).slice(0, 3000));
  console.log('HOME DEBUG:', await saveDebug(page, 'home'));

  const clicked = await tryClick(page, ['国内机票', '机票', '国内机票 ', '机票 ']);
  console.log('CLICKED:', clicked);
  console.log('AFTER CLICK TITLE:', await page.title());
  console.log('AFTER CLICK URL:', page.url());
  console.log('AFTER CLICK TEXT:', (await page.locator('body').innerText()).slice(0, 5000));

  const links = await dumpLinks(page);
  console.log('LINKS JSON START');
  console.log(JSON.stringify(links, null, 2));
  console.log('LINKS JSON END');
  console.log('AFTER CLICK DEBUG:', await saveDebug(page, 'after-click'));
  console.log('按 Ctrl+C 退出，浏览器会保持打开。');

  await new Promise(() => {});
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
