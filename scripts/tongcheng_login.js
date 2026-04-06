import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const statePath = process.env.TONGCHENG_STORAGE_STATE || path.resolve('browser_state/tongcheng-storage.json');
const headless = process.env.TONGCHENG_HEADLESS === '1';

async function main() {
  const browser = await chromium.launch({ headless });
  const context = await browser.newContext();
  const page = await context.newPage();

  console.log('打开同程首页，请你手动完成登录。完成后在终端按回车保存会话。');
  await page.goto('https://www.ly.com/', { waitUntil: 'domcontentloaded' });

  process.stdin.resume();
  await new Promise((resolve) => {
    process.stdin.once('data', () => resolve());
  });

  fs.mkdirSync(path.dirname(statePath), { recursive: true });
  await context.storageState({ path: statePath });
  console.log(`已保存 storage state 到: ${statePath}`);
  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
