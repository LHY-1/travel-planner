// Version: 20260408-2158
console.log('fix_renderplan.js loaded - version 20260408-2158');

const API = window.location.origin;
let currentPlanData = null;
let transportSortState = {};
let transportOpenState = {};

function applyPacePreset() {
  const v = pace.value;
  const presets = {
    balanced: { cost: 0.4, experience: 0.35, time: 0.1, fatigue: 0.1, comfort: 0.05 },
    budget: { cost: 0.58, experience: 0.2, time: 0.08, fatigue: 0.08, comfort: 0.06 },
    relaxed: { cost: 0.22, experience: 0.32, time: 0.12, fatigue: 0.2, comfort: 0.14 }
  };
  const p = presets[v] || presets.balanced;
  w_cost.value = p.cost;
  w_experience.value = p.experience;
  w_time.value = p.time;
  w_fatigue.value = p.fatigue;
  w_comfort.value = p.comfort;
}

function setStats(opt) {
  const p = opt.provider || '-';
  const o = opt.options || 0;
  const s = opt.status || '等待中';
  const c = opt.pace || '-';
  const paceLabels = { balanced: '平衡', budget: '省钱', relaxed: '休闲' };
  stats.innerHTML =
    '<div class="stat"><div class="k">路线</div><div class="v">' + p + '</div></div>' +
    '<div class="stat"><div class="k">选项</div><div class="v">' + o + '</div></div>' +
    '<div class="stat"><div class="k">状态</div><div class="v">' + s + '</div></div>' +
    '<div class="stat"><div class="k">节奏</div><div class="v">' + (paceLabels[c] || c) + '</div></div>';
}

function showNotice(msg, isInfo) {
  const notices = document.getElementById('notices');
  const n = document.createElement('div');
  n.className = 'notice' + (isInfo ? ' notice-info' : '');
  n.textContent = msg;
  notices.appendChild(n);
}

function getTransportIcon(mode) {
  if (mode === 'flight') return '[F]';
  if (mode === 'train') return '[T]';
  if (mode === 'highspeed' || mode === 'high_speed') return '[H]';
  if (mode === 'intercity') return '[I]';
  if (mode === 'slow' || mode === 'normal_train') return '[S]';
  return '[T]';
}

function getTransportLabel(mode) {
  const labels = {
    flight: '[F] 飞机',
    train: '[T] 火车',
    highspeed: '[H] 高铁',
    high_speed: '[H] 高铁',
    intercity: '[I] 城际',
    slow: '[S] 普速',
    normal_train: '[S] 普速'
  };
  return labels[mode] || ('[T] ' + (mode || '交通'));
}

function showDateRange(kind) {
  const s = document.getElementById(kind + '_date_start').value;
  const e = document.getElementById(kind + '_date_end').value;
  document.getElementById(kind + '_date_display').value = (s && e) ? (s + ' ~ ' + e) : (s || e || '');
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  const m = d.getMonth() + 1;
  const day = d.getDate();
  const wd = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][d.getDay()];
  return m + '/' + day + ' (' + wd + ')';
}

function formatTime(timeStr) {
  if (!timeStr) return '';
  if (timeStr.length >= 5) return timeStr.slice(0, 5);
  return timeStr;
}

function getOptionGroup(opt) {
  if (!opt) return 'other';
  if (opt.mode === 'flight' || opt.flight_no) return 'flight';
  const trainType = (opt.train_type || '').toLowerCase();
  if (trainType === 'high_speed' || trainType === 'intercity' || trainType === 'gd' || trainType === 'd') return 'rail-fast';
  return 'rail-normal';
}

function groupLabel(key) {
  return {
    flight: '飞机',
    'rail-fast': '高铁动车',
    'rail-normal': '普速'
  }[key] || key;
}

function sortTransportOptions(options, sortKey) {
  const arr = [...(options || [])];
  if (sortKey === 'price') {
    arr.sort((a, b) => (a.price || a.cost || 999999) - (b.price || b.cost || 999999));
  } else {
    arr.sort((a, b) => {
      const ta = (a.departure_time || a.depart_time || a.departTime || '99:99');
      const tb = (b.departure_time || b.depart_time || b.departTime || '99:99');
      return ta.localeCompare(tb);
    });
  }
  return arr;
}

function renderSeedResult(data) {
  const container = document.getElementById('seedResult');
  let stops = [];
  let recommended_route = [];
  let daily_draft = [];
  let totalDays = 0;

  if (data && data.stops && data.stops.length > 0) {
    stops = data.stops;
    recommended_route = data.recommended_route || [];
    daily_draft = data.daily_draft || [];
    totalDays = stops.reduce((sum, s) => sum + (s.stay_days || 1), 0);
  }

  if (stops.length === 0) {
    container.innerHTML = '<div class="empty">暂无数据</div>';
    return;
  }

  let html = '';
  html += '<div class="summary">';
  html += '<div class="summary-item"><small>天数</small><strong>' + totalDays + '</strong></div>';
  html += '<div class="summary-item"><small>景点</small><strong>' + stops.length + '</strong></div>';
  html += '<div class="summary-item"><small>节奏</small><strong>' + (document.getElementById('pace').value === 'budget' ? '省钱' : document.getElementById('pace').value === 'relaxed' ? '休闲' : '平衡') + '</strong></div>';
  html += '</div>';

  if (recommended_route.length > 0) {
    html += '<div class="section-divider"><div class="divider-label">推荐路线</div></div>';
    html += '<div class="notice notice-info">';
    for (const city of recommended_route) html += '<span class="tag" style="margin-right:4px">' + city + '</span>';
    html += '</div>';
  }

  if (daily_draft.length > 0) {
    html += '<div class="section-divider"><div class="divider-label">每日草案</div></div>';
    html += '<div class="segment-list">';
    for (const draft of daily_draft) {
      html += '<div class="day-row day-depart">';
      html += '<span class="dr-num">第' + draft.day + '天</span>';
      html += '<span class="dr-city">' + draft.city + '</span>';
      html += '<span class="dr-theme">' + draft.theme + '</span>';
      html += '</div>';
    }
    html += '</div>';
  }

  html += '<div class="notice">草案已生成！可编辑停留天数，然后重新生成交通规划。</div>';
  container.innerHTML = html;
}

function renderCandidateGroups(dayIdx, selectedTransport, options) {
  const groups = {
    flight: [],
    'rail-fast': [],
    'rail-normal': []
  };
  for (const opt of (options || [])) {
    const key = getOptionGroup(opt);
    if (groups[key]) groups[key].push(opt);
  }

  let html = '<div class="trans-group">';
  html += '<div class="trans-group-label">交通候选</div>';

  for (const key of ['flight', 'rail-fast', 'rail-normal']) {
    const list = groups[key] || [];
    if (!list.length) continue;
    const sortKey = transportSortState[dayIdx + ':' + key] || 'time';
    const sorted = sortTransportOptions(list, sortKey);

    html += '<div class="segment-card" style="margin-top:10px">';
    html += '<div class="segment-header" style="cursor:pointer" onclick="toggleCandidateGroup(' + dayIdx + ', \'' + key + '\')">';
    html += '<span class="segment-title">' + groupLabel(key) + '</span>';
    html += '<span class="tag">' + sorted.length + '条</span>';
    html += '</div>';
    html += '<div class="transport-detail-tags" style="margin:8px 0;display:flex;gap:8px;flex-wrap:wrap">';
    html += '<span class="tag" onclick="setTransportSort(event, ' + dayIdx + ', \'' + key + '\', \'time\')">按时间</span>';
    html += '<span class="tag" onclick="setTransportSort(event, ' + dayIdx + ', \'' + key + '\', \'price\')">按价格</span>';
    html += '</div>';
    html += '<div class="trans-group-items" data-candidate-group="' + dayIdx + '" data-group-key="' + key + '" style="display:' + ((transportOpenState[dayIdx + ':' + key]) ? 'flex' : 'none') + '">';

    for (const opt of sorted) {
      const optIcon = getTransportIcon(opt.mode || 'train');
      const optNo = opt.train_no || opt.flight_no || '?';
      const optDepTime = opt.departure_time || opt.depart_time || opt.departTime || '';
      const optArrTime = opt.arrive_time || opt.arrival_time || opt.arriveTime || opt.arrivalTime || '';
      const optCost = opt.cost || opt.price || 0;
      const isCurrent = (selectedTransport.train_no || selectedTransport.flight_no || '') === optNo;
      html += '<span class="trans-opt' + (isCurrent ? ' current-opt' : '') + '" onclick="changeTransportByIdx(' + dayIdx + ', ' + (dayIdx + 1) + ', \'' + optNo + '\')">';
      html += '<span class="opt-icon">' + optIcon + '</span>';
      html += '<span class="opt-type">' + groupLabel(key) + '</span>';
      html += '<span class="opt-no">' + optNo + '</span>';
      if (optDepTime || optArrTime) html += '<span class="opt-time">' + (optDepTime ? formatTime(optDepTime) : '--:--') + '→' + (optArrTime ? formatTime(optArrTime) : '--:--') + '</span>';
      if (optCost) html += '<span class="opt-price">¥' + optCost + '</span>';
      html += '</span>';
    }

    html += '</div>';
    html += '</div>';
  }

  html += '</div>';
  return html;
}

function renderPlanResult(data) {
  currentPlanData = data;
  const container = document.getElementById('seedResult');
  const planOption = data && data.options && data.options[0];
  const daily_itinerary = planOption ? planOption.daily_itinerary : null;
  if (!daily_itinerary || daily_itinerary.length === 0) {
    container.innerHTML = '<div class="empty">暂无数据</div>';
    return;
  }

  let totalCost = planOption ? planOption.total_cost : 0;
  let flightCount = 0;
  let transportCount = 0;
  for (const d of daily_itinerary) {
    if (d.transport) {
      transportCount++;
      if (d.transport.mode === 'flight' || d.transport.flight_no) flightCount++;
    }
  }

  let html = '';
  html += '<div class="summary">';
  html += '<div class="summary-item"><small>天数</small><strong>' + daily_itinerary.length + '</strong></div>';
  html += '<div class="summary-item"><small>总费用</small><strong>¥' + totalCost.toFixed(0) + '</strong></div>';
  html += '<div class="summary-item"><small>交通</small><strong>' + transportCount + '</strong></div>';
  html += '<div class="summary-item"><small>航班</small><strong>' + flightCount + '</strong></div>';
  html += '</div>';
  html += '<div class="section-divider"><div class="divider-label">每日行程</div></div>';

  for (let i = 0; i < daily_itinerary.length; i++) {
    const day = daily_itinerary[i];
    html += '<div class="day-card">';
    html += '<div class="day-header">';
    html += '<span class="day-num">第' + day.day + '天</span>';
    html += '<span class="day-date">' + (day.date ? formatDate(day.date) : '') + '</span>';
    html += '</div>';
    html += '<div class="day-activity">' + day.city;
    if (day.action) html += ' - ' + day.action;
    if (day.theme) html += ' <span class="tag" style="font-size:11px;padding:1px 6px">' + day.theme + '</span>';
    html += '</div>';

    const selectedTransport = day.transport || ((day.transport_options && day.transport_options.length > 0) ? day.transport_options[0] : null);
    if (selectedTransport) {
      const t = selectedTransport;
      const icon = getTransportIcon(t.mode || 'train');
      const fromCity = t.from_city || '';
      const toCity = t.to_city || '';
      const trainNo = t.train_no || t.flight_no || '-';
      const depTime = t.departure_time || t.depart_time || '';
      const arrTime = t.arrive_time || t.arrival_time || '';
      const departStation = t.depart_station || t.depart_airport || '';
      const arriveStation = t.arrive_station || t.arrive_airport || '';
      const cost = t.cost || t.price || 0;
      const bookingUrl = t.booking_url || '';
      const duration = t.duration || t.duration_text || '';
      const modeLabel = getTransportLabel(t.mode).replace(/^\[[^\]]+\]\s*/, '');

      html += '<div class="transport-row">';
      html += '<span class="tr-icon">' + icon + '</span>';
      html += '<span class="tr-route">' + fromCity + ' -> ' + toCity + '</span>';
      html += '<span class="tr-no">' + modeLabel + ' ' + trainNo + '</span>';
      if (depTime || arrTime) html += '<span class="tr-time">' + (depTime ? formatTime(depTime) : '--:--') + ' -> ' + (arrTime ? formatTime(arrTime) : '--:--') + '</span>';
      if (duration) html += '<span class="tr-dur">' + duration + '</span>';
      if (cost) html += '<span class="tr-price">¥' + cost + '</span>';
      if (bookingUrl) html += '<a class="book-link tr-book" href="' + bookingUrl + '" target="_blank">预订</a>';
      html += '</div>';

      const startStation = t.start_station || '';
      const endStation = t.end_station || '';
      const saleStatus = t.sale_status || null;
      const seatSummary = t.seat_summary || [];
      const detailTags = [];
      if (startStation || endStation) detailTags.push(`<span class="tag" onclick="toggleTransportDetail(this, 'route')">起终点站</span>`);
      if (saleStatus && (saleStatus.message || saleStatus.note || saleStatus.sale_state || saleStatus.can_buy_now)) detailTags.push(`<span class="tag" onclick="toggleTransportDetail(this, 'sale')">售票状态</span>`);
      if (seatSummary && seatSummary.length > 0) detailTags.push(`<span class="tag" onclick="toggleTransportDetail(this, 'seat')">座席</span>`);
      if (detailTags.length > 0) {
        html += '<div class="transport-detail-tags" style="margin-top:8px">' + detailTags.join(' ') + '</div>';
        html += '<div class="transport-detail-panel" data-detail="route" style="display:none">' +
          (startStation ? ('始发：' + startStation) : '') +
          ((startStation && endStation) ? ' ｜ ' : '') +
          (endStation ? ('终到：' + endStation) : '') +
          '</div>';
        html += '<div class="transport-detail-panel" data-detail="sale" style="display:none">';
        if (saleStatus) {
          if (saleStatus.message) html += '售票：' + saleStatus.message;
          else if (saleStatus.note) html += '售票：' + saleStatus.note;
          if (saleStatus.can_buy_now) html += ' ｜ 可购：' + saleStatus.can_buy_now;
          if (saleStatus.sale_state) html += ' ｜ 状态码：' + saleStatus.sale_state;
        }
        html += '</div>';
        const seatHtml = seatSummary.slice(0, 6).map(seat => {
          const seatName = seat.seat_name || seat.seat_code || '';
          const seatPrice = seat.price || 0;
          const seatAvail = seat.availability || '';
          const flags = [];
          if (seat.student_bookable) flags.push('学生');
          if (seat.berth_selectable) flags.push('可选铺');
          if (seat.candidate) flags.push('候补');
          let extra = '';
          if (seatAvail !== '') extra += ' 余票:' + seatAvail;
          if (flags.length) extra += ' ' + flags.join('/');
          return '<span class="tag" style="margin-right:4px;margin-top:4px">' + seatName + ' ¥' + seatPrice + extra + '</span>';
        }).join('');
        html += '<div class="transport-detail-panel transport-seat-summary" data-detail="seat" style="display:none">' + seatHtml + '</div>';
      }

      if (day.transport_options && day.transport_options.length > 0) {
        html += renderCandidateGroups(i, selectedTransport, day.transport_options);
      }
    }

    html += '</div>';
  }

  container.innerHTML = html;
}

function changeTransportByIdx(dayIdx, dayNo, transportNo) {
  if (!currentPlanData || !currentPlanData.options || !currentPlanData.options[0] || !currentPlanData.options[0].daily_itinerary) return;
  const itinerary = currentPlanData.options[0].daily_itinerary;
  const day = itinerary[dayIdx];
  if (!day || !day.transport_options || day.transport_options.length === 0) return;
  const target = day.transport_options.find(opt => (opt.train_no || opt.flight_no || '') === transportNo);
  if (!target) return;
  day.transport = JSON.parse(JSON.stringify(target));
  renderPlanResult(currentPlanData);
  const notices = document.getElementById('notices');
  if (notices) {
    notices.innerHTML = '';
    showNotice('已切换第' + dayNo + '天交通方案为：' + getTransportLabel(target.mode) + ' ' + transportNo, true);
  }
}

function toggleTransportDetail(el, detailType) {
  const row = el.closest('.day-card');
  if (!row) return;
  const panels = row.querySelectorAll('.transport-detail-panel');
  panels.forEach(panel => {
    panel.style.display = panel.getAttribute('data-detail') === detailType && panel.style.display !== 'block' ? 'block' : 'none';
  });
}

function toggleCandidateGroup(dayIdx, groupKey) {
  const stateKey = dayIdx + ':' + groupKey;
  transportOpenState[stateKey] = !transportOpenState[stateKey];
  if (currentPlanData) renderPlanResult(currentPlanData);
}

function setTransportSort(event, dayIdx, groupKey, sortKey) {
  event.preventDefault();
  event.stopPropagation();
  const stateKey = dayIdx + ':' + groupKey;
  transportSortState[stateKey] = sortKey;
  transportOpenState[stateKey] = true;
  if (currentPlanData) renderPlanResult(currentPlanData);
}

async function runRecommendSeed() {
  const start_city = document.getElementById('start_city').value;
  const end_city = document.getElementById('end_city').value;
  const days = document.getElementById('days').value;
  const budget = document.getElementById('budget').value;
  const travel_date = document.getElementById('travel_date').value;
  const candidate_cities_raw = document.getElementById('candidate_cities').value;
  const w_cost = document.getElementById('w_cost').value;
  const w_experience = document.getElementById('w_experience').value;
  const w_time = document.getElementById('w_time').value;
  const w_fatigue = document.getElementById('w_fatigue').value;
  const w_comfort = document.getElementById('w_comfort').value;

  setStats({ provider: '生成中...', options: 0, status: '请稍候', pace: '-' });
  const body = {
    start_city,
    end_city: end_city || start_city,
    days: parseInt(days) || 4,
    budget: parseFloat(budget) || 3000,
    travel_date: travel_date || null,
    candidate_cities: candidate_cities_raw.split(',').map(s => s.trim()).filter(Boolean),
    weights: {
      cost: parseFloat(w_cost) || 0.4,
      experience: parseFloat(w_experience) || 0.35,
      time: parseFloat(w_time) || 0.1,
      fatigue: parseFloat(w_fatigue) || 0.1,
      comfort: parseFloat(w_comfort) || 0.05
    },
    pace: document.getElementById('pace').value || 'balanced'
  };

  try {
    const res = await fetch(API + '/recommend/itinerary-seed', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await res.json();
    setStats({ provider: '完成', options: (data.stops && data.stops.length) || 0, status: '完成', pace: body.pace });
    renderSeedResult(data);
  } catch (e) {
    setStats({ provider: '错误', options: 0, status: '失败', pace: '-' });
    showNotice('错误: ' + e.message, false);
  }
}

async function runPlan() {
  const start_city = document.getElementById('start_city').value;
  const end_city = document.getElementById('end_city').value;
  const days = document.getElementById('days').value;
  const budget = document.getElementById('budget').value;
  const travel_date = document.getElementById('travel_date').value;
  const candidate_cities_raw = document.getElementById('candidate_cities').value;

  setStats({ provider: '规划中...', options: 0, status: '请稍候', pace: '-' });
  const body = {
    start_city,
    end_city: end_city || start_city,
    days: parseInt(days) || 4,
    budget: parseFloat(budget) || 3000,
    travel_date: travel_date || null,
    candidate_cities: candidate_cities_raw.split(',').map(s => s.trim()).filter(Boolean),
    weights: {
      cost: parseFloat(document.getElementById('w_cost').value) || 0.4,
      experience: parseFloat(document.getElementById('w_experience').value) || 0.35,
      time: parseFloat(document.getElementById('w_time').value) || 0.1,
      fatigue: parseFloat(document.getElementById('w_fatigue').value) || 0.1,
      comfort: parseFloat(document.getElementById('w_comfort').value) || 0.05
    },
    pace: document.getElementById('pace').value || 'balanced'
  };

  try {
    const res = await fetch(API + '/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error('HTTP ' + res.status + ': ' + err);
    }
    const data = await res.json();
    setStats({ provider: '完成', options: (data.daily_itineraries && data.daily_itineraries.length) || 0, status: '完成', pace: body.pace });
    renderPlanResult(data);
  } catch (e) {
    setStats({ provider: '错误', options: 0, status: '失败', pace: '-' });
    showNotice('错误: ' + e.message, false);
  }
}

document.getElementById('departure_date_start').addEventListener('change', () => showDateRange('departure'));
document.getElementById('departure_date_end').addEventListener('change', () => showDateRange('departure'));
document.getElementById('return_date_start').addEventListener('change', () => showDateRange('return'));
document.getElementById('return_date_end').addEventListener('change', () => showDateRange('return'));

console.log('fix_renderplan.js initialized');
