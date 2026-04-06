import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const statePath = process.env.TONGCHENG_STORAGE_STATE || path.resolve('browser_state/tongcheng-storage.json');
const debugDir = path.resolve('runtime_data/flight_debug');

function short(s, n = 500) {
  if (!s) return '';
  return String(s).slice(0, n);
}

async function main() {
  const browser = await chromium.launch({ headless: false, slowMo: 300 });
  const context = fs.existsSync(statePath)
    ? await browser.newContext({ storageState: statePath })
    : await browser.newContext();
  const page = await context.newPage();

  const events = [];

  page.on('request', async (req) => {
    const url = req.url();
    if (/flight|flights|air|query|search|itinerary|intlflight|domestic/i.test(url)) {
      events.push({
        type: 'request',
        method: req.method(),
        url,
        headers: req.headers(),
        postData: short(req.postData(), 2000),
        ts: new Date().toISOString(),
      });
    }
  });

  page.on('response', async (res) => {
    const url = res.url();
    if (/flight|flights|air|query|search|itinerary|intlflight|domestic/i.test(url)) {
      let body = '';
      try {
        const ct = res.headers()['content-type'] || '';
        if (/json|text|javascript/.test(ct)) {
          body = short(await res.text(), 2000);
        }
      } catch {}
      events.push({
        type: 'response',
        status: res.status(),
        url,
        headers: res.headers(),
        body,
        ts: new Date().toISOString(),
      });
    }
  });

  console.log('打开同程机票首页，请你手动完成一次搜索。完成后回到终端按回车。');
  await page.goto('https://www.ly.com/flights/home', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(4000);

  process.stdin.resume();
  await new Promise((resolve) => process.stdin.once('data', resolve));

  fs.mkdirSync(debugDir, { recursive: true });
  const stamp = `${Date.now()}-capture`;
  const htmlPath = path.join(debugDir, `${stamp}.html`);
  const pngPath = path.join(debugDir, `${stamp}.png`);
  const jsonPath = path.join(debugDir, `${stamp}.json`);
  fs.writeFileSync(htmlPath, await page.content(), 'utf8');
  await page.screenshot({ path: pngPath, fullPage: true });
  fs.writeFileSync(jsonPath, JSON.stringify({
    finalUrl: page.url(),
    title: await page.title(),
    bodyText: (await page.locator('body').innerText()).slice(0, 10000),
    events,
  }, null, 2), 'utf8');

  console.log('FINAL URL:', page.url());
  console.log('TITLE:', await page.title());
  console.log('HTML:', htmlPath);
  console.log('PNG:', pngPath);
  console.log('JSON:', jsonPath);

  await browser.close();
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
