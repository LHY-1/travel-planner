import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const statePath = process.env.TONGCHENG_STORAGE_STATE || path.resolve('browser_state/tongcheng-storage.json');
const headless = process.env.TONGCHENG_HEADLESS === '1';

async function main() {
  const [city, date] = process.argv.slice(2);
  if (!city || !date) {
    console.error('Usage: node scripts/search_tongcheng_hotels.js <city> <date>');
    process.exit(2);
  }

  const hasState = fs.existsSync(statePath);
  const browser = await chromium.launch({ headless });
  const context = hasState
    ? await browser.newContext({ storageState: statePath })
    : await browser.newContext();
  const page = await context.newPage();

  const results = {
    query: { city, date },
    fetchedAt: new Date().toISOString(),
    source: 'tongcheng-browser',
    loggedInState: hasState,
    hotels: []
  };

  try {
    await page.goto('https://www.ly.com/', { waitUntil: 'domcontentloaded', timeout: 30000 });
    results.pageTitle = await page.title();
    console.log(JSON.stringify(results, null, 2));
  } catch (err) {
    results.error = String(err);
    console.log(JSON.stringify(results, null, 2));
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

main();
