// Version: 20260405-1715
console.log('fix_renderplan.js loaded - version 20260405-1715');

const API = window.location.origin;

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
  if (mode === 'highspeed') return '[H]';
  if (mode === 'intercity') return '[I]';
  if (mode === 'slow') return '[S]';
  if (mode === 'bus') return '[B]';
  return '[T]';
}

function getTransportLabel(mode) {
  const labels = {
    flight: '[F] 飞机',
    train: '[T] 火车',
    highspeed: '[H] 高铁',
    intercity: '[I] 城际',
    slow: '[S] 普速',
    bus: '[B] 汽车'
  };
  return labels[mode] || mode;
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

function renderSeedResult(data) {
  const container = document.getElementById('seedResult');
  
  // 兼容两种格式：recommend API 和旧 route 格式
  let stops = [];
  let recommended_route = [];
  let daily_draft = [];
  let reasons = [];
  let totalDays = 0;
  
  if (data && data.stops && data.stops.length > 0) {
    // recommend API 格式
    stops = data.stops;
    recommended_route = data.recommended_route || [];
    daily_draft = data.daily_draft || [];
    reasons = data.reasons || [];
    totalDays = stops.reduce((sum, s) => sum + (s.stay_days || 1), 0);
  } else if (data && data.route && data.route.cities && data.route.cities.length > 0) {
    // 旧 route 格式（兼容）
    stops = data.route.cities.map(c => ({ city: c.city || c.name, stay_days: c.days || 1, reason: c.reason || '' }));
    totalDays = data.route.total_days || 0;
  }
  
  if (stops.length === 0 && !(data && data.stops)) {
    container.innerHTML = '<div class="empty">暂无数据</div>';
    if (data && data.debug) console.log('debug:', data.debug);
    return;
  }
  
  let html = '';
  
  // 摘要
  html += '<div class="summary">';
  html += '<div class="summary-item"><small>天数</small><strong>' + totalDays + '</strong></div>';
  html += '<div class="summary-item"><small>景点</small><strong>' + stops.length + '</strong></div>';
  html += '<div class="summary-item"><small>节奏</small><strong>' + (document.getElementById('pace').value === 'budget' ? '省钱' : document.getElementById('pace').value === 'relaxed' ? '休闲' : '平衡') + '</strong></div>';
  html += '</div>';
  
  // 推荐路线
  if (recommended_route.length > 0) {
    html += '<div class="section-divider"><div class="divider-label">推荐路线</div></div>';
    html += '<div class="notice notice-info">';
    for (const city of recommended_route) {
      html += '<span class="tag" style="margin-right:4px">' + city + '</span>';
    }
    html += '</div>';
  }
  
  // 每日草案
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
  
  // 停留城市列表
  if (stops.length > 0) {
    html += '<div class="section-divider"><div class="divider-label">停留城市</div></div>';
    html += '<div class="segment-list">';
    
    for (const stop of stops) {
      html += '<div class="segment-card">';
      html += '<div class="segment-header">';
      html += '<span class="segment-title">' + stop.city + '</span>';
      html += '<span class="tag">' + stop.stay_days + '天</span>';
      html += '</div>';
      if (stop.reason) {
        html += '<div class="segment-meta" style="margin-top:6px;font-size:12px;color:var(--muted)">' + stop.reason + '</div>';
      }
      html += '</div>';
    }
    
    html += '</div>';
  }
  
  // 提示
  html += '<div class="notice">草案已生成！可编辑停留天数，然后重新生成交通规划。</div>';
  
  container.innerHTML = html;
}

function renderPlanResult(data) {
  const container = document.getElementById('seedResult');
  
  // PlanResponse 格式: { options: [{ daily_itinerary: [...] }], notices: [...] }
  const planOption = data && data.options && data.options[0];
  const daily_itinerary = planOption ? planOption.daily_itinerary : (data ? data.daily_itineraries : null);
  
  if (!daily_itinerary || daily_itinerary.length === 0) {
    container.innerHTML = '<div class="empty">暂无数据</div>';
    if (data && data.notices) {
      for (const n of data.notices) {
        container.innerHTML += '<div class="notice" style="margin-top:8px">' + n + '</div>';
      }
    }
    if (data && data.debug) console.log('debug:', data.debug);
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
  
  if (data && data.notices && data.notices.length > 0) {
    for (const n of data.notices) {
      if (!n.includes('API Error')) {
        html += '<div class="notice">' + n + '</div>';
      }
    }
  }
  
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
    
    if (day.transport) {
      const t = day.transport;
      const icon = getTransportIcon(t.mode || 'train');
      const fromCity = t.from_city || t.fromCity || '';
      const toCity = t.to_city || t.toCity || '';
      const trainNo = t.train_no || t.flight_no || '-';
      const depTime = t.departure_time || t.depart_time || t.departTime || '';
      const cost = t.cost || t.price || 0;
      const bookingUrl = t.booking_url || t.bookingUrl || '';
      const duration = t.duration || t.duration_text || t.durationText || '';
      
      html += '<div class="transport-row">';
      html += '<span class="tr-icon">' + icon + '</span>';
      html += '<span class="tr-route">' + fromCity + ' -> ' + toCity + '</span>';
      html += '<span class="tr-no">' + trainNo + '</span>';
      if (depTime) html += '<span class="tr-time">' + formatTime(depTime) + '</span>';
      if (duration) html += '<span class="tr-dur">' + duration + '</span>';
      if (cost) html += '<span class="tr-price">¥' + cost + '</span>';
      if (bookingUrl) html += '<a class="book-link tr-book" href="' + bookingUrl + '" target="_blank">预订</a>';
      html += '</div>';
      
      if (day.transport_options && day.transport_options.length > 0) {
        html += '<div class="trans-group">';
        html += '<div class="trans-group-label">其他选项</div>';
        html += '<div class="trans-group-items">';
        
        for (const opt of day.transport_options) {
          const optIcon = getTransportIcon(opt.mode || 'train');
          const optTrainNo = opt.train_no || opt.flight_no || '?';
          const optTime = opt.departure_time || opt.depart_time || opt.departTime || '';
          const optCost = opt.cost || opt.price || 0;
          const isFlight = opt.mode === 'flight' || !!opt.flight_no;
          
          html += '<span class="trans-opt" onclick="changeTransportByIdx(' + i + ', \'' + optTrainNo + '\')">';
          html += '<span class="opt-icon">' + optIcon + '</span>';
          html += '<span class="opt-type">' + (isFlight ? '飞机' : '火车') + '</span>';
          html += '<span class="opt-no">' + optTrainNo + '</span>';
          if (optTime) html += '<span class="opt-time">' + formatTime(optTime) + '</span>';
          if (optCost) html += '<span class="opt-price">¥' + optCost + '</span>';
          html += '</span>';
        }
        
        html += '</div></div>';
      }
    }
    
    // 时间线
    if (day.timeline && day.timeline.length > 0) {
      html += '<div class="timeline">';
      for (const ev of day.timeline) {
        html += '<div class="timeline-item">';
        html += '<span class="tl-time">' + (ev.time || '') + '</span>';
        html += '<span class="tl-icon">' + (ev.type === 'transport' ? '[T]' : ev.type === 'meal' ? '[M]' : '[A]') + '</span>';
        html += '<span class="tl-event">' + ev.event + '</span>';
        if (ev.duration_min > 0) html += '<span class="tl-dur">' + ev.duration_min + 'min</span>';
        html += '</div>';
      }
      html += '</div>';
    }
    
    html += '</div>';
  }
  
  container.innerHTML = html;
}

function changeTransportByIdx(dayIdx, transportNo) {
  console.log('Change transport: Day ' + dayIdx + ' -> ' + transportNo);
  alert('Change transport to: ' + transportNo);
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
    console.log('seed result:', data);
    setStats({ provider: '完成', options: (data.stops && data.stops.length) || 0, status: '完成', pace: body.pace });
    renderSeedResult(data);
  } catch (e) {
    console.error(e);
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
    console.log('=== renderPlan data ===', JSON.stringify(data, null, 2));
    setStats({ provider: '完成', options: (data.daily_itineraries && data.daily_itineraries.length) || 0, status: '完成', pace: body.pace });
    renderPlanResult(data);
  } catch (e) {
    console.error(e);
    setStats({ provider: '错误', options: 0, status: '失败', pace: '-' });
    showNotice('错误: ' + e.message, false);
  }
}

document.getElementById('departure_date_start').addEventListener('change', () => showDateRange('departure'));
document.getElementById('departure_date_end').addEventListener('change', () => showDateRange('departure'));
document.getElementById('return_date_start').addEventListener('change', () => showDateRange('return'));
document.getElementById('return_date_end').addEventListener('change', () => showDateRange('return'));

console.log('fix_renderplan.js initialized');
