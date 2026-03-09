const currency = new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const compact = new Intl.NumberFormat('zh-CN', { notation: 'compact', maximumFractionDigits: 1 });

const state = { data: null, activeIndex: 0 };

fetch('./data/positions.json')
  .then((res) => res.json())
  .then((data) => {
    state.data = data;
    renderOverview(data);
    renderTabs(data.investors);
    renderInvestor(0);
    renderErrors(data.errors || []);
  })
  .catch((err) => {
    document.body.innerHTML = `<main class="shell" style="padding:80px 0"><div class="panel"><h2>数据加载失败</h2><p>${err.message}</p></div></main>`;
  });

function money(value) {
  return currency.format(value || 0);
}

function delta(value) {
  const cls = value >= 0 ? 'up' : 'down';
  const sign = value >= 0 ? '+' : '-';
  return `<span class="card-delta ${cls}">${sign}${compact.format(Math.abs(value || 0))}</span>`;
}

function renderOverview(data) {
  document.getElementById('yearsBack').textContent = `${data.yearsBack}Y`;
  document.getElementById('investorCount').textContent = `${data.investorCount}`;
  document.getElementById('generatedAt').textContent = new Date(data.generatedAt).toLocaleString('zh-CN', { hour12: false });

  document.getElementById('rankingGrid').innerHTML = data.rankings.map((item, index) => `
    <article class="ranking-card" style="--card-accent:${data.investors[index]?.accent || 'rgba(56,189,248,.35)'}">
      <div class="rank-no">TOP ${index + 1}</div>
      <h3>${item.name}</h3>
      <p>${item.entity}</p>
      <div class="card-value">${money(item.portfolioValue)}</div>
      <p>${delta(item.valueChange)} · 核心仓位 ${item.topHolding}</p>
    </article>
  `).join('');

  document.getElementById('changesList').innerHTML = data.spotlightChanges.map((item) => `
    <div class="change-item">
      <span class="badge ${item.status}">${labelStatus(item.status)}</span>
      <div>
        <strong>${item.name}</strong>
        <p>${item.investor} · ${item.entity}</p>
      </div>
      <div>
        <strong>${signedMoney(item.diffValue)}</strong>
        <p>${money(item.value)}</p>
      </div>
    </div>
  `).join('');
}

function renderTabs(investors) {
  const tabs = document.getElementById('investorTabs');
  tabs.innerHTML = investors.map((item, index) => `
    <button class="tab-button ${index === 0 ? 'active' : ''}" data-index="${index}">${item.name}</button>
  `).join('');
  tabs.querySelectorAll('button').forEach((button) => {
    button.addEventListener('click', () => {
      tabs.querySelectorAll('button').forEach((b) => b.classList.remove('active'));
      button.classList.add('active');
      renderInvestor(Number(button.dataset.index));
    });
  });
}

function renderInvestor(index) {
  state.activeIndex = index;
  const investor = state.data.investors[index];
  document.getElementById('detailEntity').textContent = investor.entity;
  document.getElementById('detailName').textContent = investor.name;
  document.getElementById('detailQuarter').textContent = `${investor.latestQuarter} · ${investor.latestDate}`;
  document.getElementById('detailValue').textContent = money(investor.latestPortfolioValue);

  document.getElementById('holdingsTable').innerHTML = `
    <table>
      <thead><tr><th>持仓</th><th>市值</th><th>股数</th></tr></thead>
      <tbody>
        ${investor.latestHoldings.map((item) => `
          <tr>
            <td><strong>${item.name}</strong><div>${item.cusip || '-'}</div></td>
            <td>${money(item.value)}</td>
            <td>${compact.format(item.shares || 0)}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;

  document.getElementById('detailChanges').innerHTML = investor.changes.map((item) => `
    <div class="change-item">
      <span class="badge ${item.status}">${labelStatus(item.status)}</span>
      <div>
        <strong>${item.name}</strong>
        <p>${item.cusip || 'N/A'}</p>
      </div>
      <div>
        <strong>${signedMoney(item.diffValue)}</strong>
        <p>当前 ${money(item.value)}</p>
      </div>
    </div>
  `).join('');

  drawChart(investor.timeline, investor.accent);
}

function drawChart(points, accent) {
  const canvas = document.getElementById('timelineChart');
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth * dpr;
  const height = canvas.clientHeight * dpr;
  canvas.width = width;
  canvas.height = height;
  ctx.clearRect(0, 0, width, height);

  const pad = 44 * dpr;
  const values = points.map((item) => item.portfolioValue);
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = Math.max(max - min, 1);

  ctx.strokeStyle = 'rgba(148,163,184,.25)';
  ctx.lineWidth = 1;
  for (let i = 0; i < 4; i += 1) {
    const y = pad + ((height - pad * 2) / 3) * i;
    ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(width - pad, y); ctx.stroke();
  }

  const xy = points.map((item, index) => {
    const x = pad + ((width - pad * 2) / Math.max(points.length - 1, 1)) * index;
    const y = height - pad - ((item.portfolioValue - min) / span) * (height - pad * 2);
    return { x, y, item };
  });

  const gradient = ctx.createLinearGradient(0, pad, 0, height - pad);
  gradient.addColorStop(0, `${accent}cc`);
  gradient.addColorStop(1, 'rgba(56,189,248,.08)');

  ctx.beginPath();
  xy.forEach((point, index) => index === 0 ? ctx.moveTo(point.x, point.y) : ctx.lineTo(point.x, point.y));
  ctx.strokeStyle = accent;
  ctx.lineWidth = 3 * dpr;
  ctx.stroke();

  ctx.lineTo(xy[xy.length - 1].x, height - pad);
  ctx.lineTo(xy[0].x, height - pad);
  ctx.closePath();
  ctx.fillStyle = gradient;
  ctx.fill();

  ctx.fillStyle = '#edf6ff';
  ctx.font = `${12 * dpr}px Space Grotesk`;
  ctx.fillText(points[0].quarter, pad, height - 14 * dpr);
  ctx.fillText(points[points.length - 1].quarter, width - pad - 72 * dpr, height - 14 * dpr);
  ctx.fillText(compact.format(max), pad, pad - 10 * dpr);
}

function renderErrors(errors) {
  if (!errors.length) return;
  document.getElementById('errorsSection').classList.remove('hidden');
  document.getElementById('errorsList').innerHTML = errors.map((item) => `<p>${item.investor}: ${item.error}</p>`).join('');
}

function labelStatus(status) {
  return {
    new: '新进',
    increased: '增持',
    reduced: '减持',
    exited: '清仓',
    flat: '持平',
  }[status] || status;
}

function signedMoney(value) {
  const sign = value >= 0 ? '+' : '-';
  return `${sign}${currency.format(Math.abs(value || 0))}`;
}
