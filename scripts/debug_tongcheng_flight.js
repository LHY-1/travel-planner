import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const statePath = process.env.TONGCHENG_STORAGE_STATE || path.resolve('browser_state/tongcheng-storage.json');
const headless = process.env.TONGCHENG_HEADLESS === '1';
const debugDir = path.resolve('runtime_data/flight_debug');

async function main() {
  const [fromCity, toCity, date, explicitUrl] = process.argv.slice(2);
  if (!fromCity || !toCity || !date) {
    console.error('Usage: node scripts/debug_tongcheng_flight.js <fromCity> <toCity> <date> [url]');
    process.exit(2);
  }

  const browser = await chromium.launch({ headless });
  const context = fs.existsSync(statePath)
    ? await browser.newContext({ storageState: statePath })
    : await browser.newContext();
  const page = await context.newPage();
  const url = explicitUrl || `https://www.ly.com/flights/itinerary/oneway/?from=${encodeURIComponent(fromCity)}&to=${encodeURIComponent(toCity)}&date=${date}&fromairport=&toairport=`;
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(5000);
  fs.mkdirSync(debugDir, { recursive: true });
  const stamp = `${Date.now()}-debug`;
  const htmlPath = path.join(debugDir, `${stamp}.html`);
  const pngPath = path.join(debugDir, `${stamp}.png`);
  fs.writeFileSync(htmlPath, await page.content(), 'utf8');
  await page.screenshot({ path: pngPath, fullPage: true });
  console.log('TITLE:', await page.title());
  console.log('URL:', page.url());
  console.log('HTML:', htmlPath);
  console.log('PNG:', pngPath);
  const txt = await page.locator('body').innerText();
  console.log(txt.slice(0, 10000));
  await browser.close();
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
