import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const statePath = process.env.TONGCHENG_STORAGE_STATE || path.resolve('browser_state/tongcheng-storage.json');
const headless = process.env.TONGCHENG_HEADLESS === '1';
const debugDir = path.resolve('runtime_data/flight_debug');

const cityCodes = {
  '西安': 'SIA',
  '北京': 'PEK',
  '上海': 'SHA',
  '杭州': 'HGH',
  '南京': 'NKG',
  '苏州': 'SZV',
  '广州': 'CAN',
  '深圳': 'SZX',
  '成都': 'CTU',
  '重庆': 'CKG',
  '武汉': 'WUH',
  '长沙': 'CSX',
  '青岛': 'TAO'
};

function usage() {
  console.error('Usage: node scripts/search_tongcheng_transport.js <fromCity> <toCity> <date>');
  process.exit(2);
}

function buildKnownItineraryUrl(fromCity, toCity, date) {
  const fromCode = cityCodes[fromCity];
  const toCode = cityCodes[toCity];
  if (!fromCode || !toCode) return null;
  return `https://www.ly.com/flights/itinerary/oneway/${fromCode}-${toCode}?date=${date}&from=${encodeURIComponent(fromCity)}&to=${encodeURIComponent(toCity)}&fromairport=&toairport=&p=&childticket=0,0`;
}

function parseDuration(s) {
  if (!s) return 0;
  let m = 0;
  let hit = s.match(/(\d+)h/);
  if (hit) m += Number(hit[1]) * 60;
  hit = s.match(/(\d+)m/);
  if (hit) m += Number(hit[1]);
  hit = s.match(/(\d+)小时/);
  if (hit) m += Number(hit[1]) * 60;
  hit = s.match(/(\d+)分/);
  if (hit) m += Number(hit[1]);
  return m;
}

async function saveDebugArtifacts(page, prefix) {
  fs.mkdirSync(debugDir, { recursive: true });
  const stamp = `${Date.now()}-${prefix}`;
  const htmlPath = path.join(debugDir, `${stamp}.html`);
  const pngPath = path.join(debugDir, `${stamp}.png`);
  fs.writeFileSync(htmlPath, await page.content(), 'utf8');
  await page.screenshot({ path: pngPath, fullPage: true });
  return { htmlPath, pngPath };
}

async function extractFlights(page, bookingUrl) {
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(2500);

  const data = await page.evaluate(({ bookingUrl }) => {
    const text = (el) => (el?.innerText || el?.textContent || '').replace(/\s+/g, ' ').trim();
    const cards = Array.from(document.querySelectorAll('.flight-item'));

    return cards.slice(0, 80).map((card) => {
      const rawText = text(card);
      const nameText = text(card.querySelector('.flight-item-name'));
      const typeText = text(card.querySelector('.flight-item-type'));
      const startStrong = card.querySelector('.f-startTime strong');
      const startAirport = card.querySelector('.f-startTime em');
      const durationEl = card.querySelector('.f-line-to i');
      const endStrong = card.querySelector('.f-endTime strong');
      const endAirport = card.querySelector('.f-endTime em');
      const priceEm = card.querySelector('.head-prices strong em');
      const extraPrice = text(card.querySelector('.head-prices .gray-style'));
      const mealTexts = Array.from(card.querySelectorAll('.red-labels .label-tip')).map(el => text(el)).filter(Boolean);

      const flightNoMatch = (nameText || '').match(/[A-Z0-9]{2}\d{3,4}/);
      const airline = nameText ? nameText.replace(/[A-Z0-9]{2}\d{3,4}.*/, '').trim() : '';
      const price = priceEm ? Number((text(priceEm) || '').replace(/[^\d.]/g, '')) : null;
      const durationText = text(durationEl);
      const transfer = /经停|中转/.test(rawText) ? 1 : 0;

      return {
        raw_text: rawText,
        mode: 'flight',
        airline,
        flight_no: flightNoMatch ? flightNoMatch[0] : '',
        aircraft: typeText,
        depart_time: text(startStrong),
        arrive_time: text(endStrong),
        depart_airport: text(startAirport),
        arrive_airport: text(endAirport),
        duration_text: durationText,
        duration_min: 0,
        meal: mealTexts.join(' | '),
        discount_text: extraPrice,
        transfer_count: transfer,
        price,
        comfort_score: transfer ? 0.68 : 0.82,
        booking_url: bookingUrl,
      };
    });
  }, { bookingUrl });

  return data.map(item => {
    item.duration_min = parseDuration(item.duration_text);
    return item;
  }).filter(x => x.price !== null && x.depart_time && x.arrive_time && x.flight_no);
}

async function main() {
  const [fromCity, toCity, date] = process.argv.slice(2);
  if (!fromCity || !toCity || !date) usage();

  const hasState = fs.existsSync(statePath);
  const browser = await chromium.launch({ headless, slowMo: headless ? 0 : 80 });
  const context = hasState
    ? await browser.newContext({ storageState: statePath })
    : await browser.newContext();
  const page = await context.newPage();

  const results = {
    query: { fromCity, toCity, date },
    fetchedAt: new Date().toISOString(),
    source: 'tongcheng-browser',
    loggedInState: hasState,
    transport: []
  };

  try {
    const knownUrl = buildKnownItineraryUrl(fromCity, toCity, date);
    results.knownUrl = knownUrl;

    if (!knownUrl) {
      results.error = 'missing_city_code_mapping';
      console.log(JSON.stringify(results, null, 2));
      process.exit(1);
    }

    await page.goto(knownUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(5000);

    results.pageTitle = await page.title();
    results.url = page.url();
    results.bodyText = (await page.locator('body').innerText()).slice(0, 10000);
    const debug = await saveDebugArtifacts(page, 'flight-itinerary');
    results.debug = debug;
    results.transport = await extractFlights(page, knownUrl);
    results.transport_count = results.transport.length;
    console.log(JSON.stringify(results, null, 2));
  } catch (err) {
    results.error = String(err);
    results.url = page.url();
    try {
      results.debug = await saveDebugArtifacts(page, 'flight-error');
    } catch {}
    console.log(JSON.stringify(results, null, 2));
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

main();
