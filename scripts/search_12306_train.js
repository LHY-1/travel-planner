#!/usr/bin/env node
import { chromium } from 'playwright';

const stationCodeMap = {
  // 直辖市 / 主要城市
  '北京': 'BJP', '北京南': 'VNP', '北京西': 'BXP', '北京丰台': 'FTP',
  '上海': 'SHH', '上海虹桥': 'AOH', '上海南': 'SNH', '上海站': 'SHH',
  '天津': 'TJP', '天津西': 'TXP', '天津南': 'TIP',
  '重庆': 'CQW', '重庆北': 'UKW', '重庆西': 'JXW',
  // 主要省会
  '西安': 'XAY', '西安北': 'EAY',
  '南京': 'NJH', '南京南': 'NKH', '南京站': 'NJH',
  '杭州': 'HZH', '杭州东': 'HGH', '杭州南': 'XHH',
  '苏州': 'SZH', '苏州北': 'OBH', '苏州园区': 'KHH',
  '广州': 'GZQ', '广州南': 'IZQ', '广州东': 'GGQ',
  '深圳': 'SZQ', '深圳北': 'IOQ', '深圳站': 'SZQ',
  '成都': 'CDW', '成都东': 'ICW', '成都南': 'CNW',
  '武汉': 'WHN', '武汉站': 'WNN',
  '长沙': 'CSQ', '长沙南': 'CWQ',
  '济南': 'JNK', '济南西': 'JGK', '济南东': 'JEL',
  '郑州': 'ZZF', '郑州东': 'ZAF',
  '石家庄': 'SJP', '石家庄北': 'VVP',
  '沈阳': 'SYT', '沈阳北': 'SBT',
  '哈尔滨': 'HBB', '哈尔滨西': 'VBB',
  '南昌': 'NCG', '南昌西': 'NXG',
  '合肥': 'HFH', '合肥南': 'ENH',
  '福州': 'FZS', '福州南': 'FYS',
  '贵阳': 'GIW', '贵阳北': 'KQW',
  '昆明': 'KMM', '昆明南': 'KOM',
  '南宁': 'NNZ', '南宁东': 'NFZ',
  '太原': 'TYV', '太原南': 'TNV',
  '兰州': 'LZJ', '兰州西': 'LAJ',
  '拉萨': 'LSO',
  '乌鲁木齐': 'WCR',
  '呼和浩特': 'HHC',
  '三亚': 'QYQ',
  '厦门': 'XMS', '厦门北': 'XBS',
  '青岛': 'QDK', '青岛北': 'QHK',
  '大连': 'DLT', '大连北': 'DFT',
  '宁波': 'NGH',
  '温州': 'RZH',
  '洛阳': 'LYF',
  '开封': 'KFF',
  '保定': 'BDP',
  '唐山': 'TSP',
  '秦皇岛': 'QTP',
  '张家界': 'DIQ',
  '凤凰': 'FHQ',
  '桂林': 'GLZ', '桂林北': 'GBZ',
  '丽江': 'LHM',
  '大理': 'DKM',
  '西宁': 'XNO',
  '银川': 'YIJ',
  '乌鲁木齐南': 'WMR',
};

function parseArgs(argv) {
  const [origin, destination, date] = argv.slice(2);
  if (!origin || !destination || !date) {
    console.error('Usage: node scripts/search_12306_train.js <origin> <destination> <date>');
    process.exit(2);
  }
  return { origin, destination, date };
}

function parsePriceFromAria(label) {
  if (!label) return null;
  const m = label.match(/票价(\d+)元/);
  return m ? Number(m[1]) : null;
}

function parseAvailability(label, text) {
  if (label) {
    const m = label.match(/余票([^，]+)/);
    if (m) return m[1];
  }
  return (text || '').trim() || null;
}

async function main() {
  const query = parseArgs(process.argv);
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const payload = {
    query: {
      kind: 'train',
      origin: query.origin,
      destination: query.destination,
      date: query.date,
      constraints: {
        seatClass: null,
        maxTransferHours: null,
      },
    },
    results: [],
    notes: [],
    generatedAt: new Date().toISOString(),
  };

  try {
    const fromCode = stationCodeMap[query.origin];
    const toCode = stationCodeMap[query.destination];
    if (!fromCode || !toCode) {
      payload.notes.push('missing_station_code_mapping');
      console.log(JSON.stringify(payload, null, 2));
      process.exit(1);
    }

    const target = 'https://kyfw.12306.cn/otn/leftTicket/init?linktypeid=dc';
    await page.goto(target, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(5000);

    await page.evaluate(({ origin, destination, date, fromCode, toCode }) => {
      document.querySelector('input#fromStation').value = fromCode;
      document.querySelector('input#fromStationText').value = origin;
      document.querySelector('input#toStation').value = toCode;
      document.querySelector('input#toStationText').value = destination;
      document.querySelector('input#train_date').value = date;
    }, { ...query, fromCode, toCode });

    await page.click('#query_ticket');
    await page.waitForTimeout(8000);

    payload.results = await page.evaluate(() => {
      function parsePriceFromAria(label) {
        if (!label) return null;
        const m = label.match(/票价(\d+)元/);
        return m ? Number(m[1]) : null;
      }
      function parseAvailability(label, text) {
        if (label) {
          const m = label.match(/余票([^，]+)/);
          if (m) return m[1];
        }
        return (text || '').trim() || null;
      }

      const seatKeys = [
        ['SWZ', '商务座'],
        ['TZ', '特等座'],
        ['ZY', '一等座'],
        ['ZE', '二等座'],
        ['GR', '高级软卧'],
        ['RW', '软卧'],
        ['YW', '硬卧'],
        ['YZ', '硬座'],
        ['WZ', '无座']
      ];

      const rows = Array.from(document.querySelectorAll('#queryLeftTable tr')).filter(tr => tr.innerText.trim());
      return rows.map(tr => {
        const trainNo = tr.querySelector('a.number')?.textContent?.trim() || null;
        const stations = Array.from(tr.querySelectorAll('.cdz strong')).map(x => x.textContent.trim());
        const times = Array.from(tr.querySelectorAll('.cds strong')).map(x => x.textContent.trim());
        const duration = tr.querySelector('.ls strong')?.textContent?.trim() || null;
        const arrivalDay = tr.querySelector('.ls span')?.textContent?.trim() || null;
        const seats = {};
        for (const [prefix, label] of seatKeys) {
          const cell = tr.querySelector(`td[id^="${prefix}_"]`);
          if (!cell) continue;
          seats[label] = {
            availability: parseAvailability(cell.getAttribute('aria-label'), cell.innerText),
            price: parsePriceFromAria(cell.getAttribute('aria-label'))
          };
        }
        return {
          trainNo,
          fromStation: stations[0] || null,
          toStation: stations[1] || null,
          departTime: times[0] || null,
          arriveTime: times[1] || null,
          duration,
          arrivalDay,
          seats
        };
      }).filter(r => r.trainNo);
    });

    payload.notes.push(`Opened ${target}`);
    payload.notes.push('12306 result table fetched via page automation.');
    payload.notes.push('Current station-code map is still limited and should be expanded.');
    console.log(JSON.stringify(payload, null, 2));
  } catch (err) {
    payload.notes.push(`Error: ${String(err.message || err)}`);
    console.log(JSON.stringify(payload, null, 2));
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

main();
