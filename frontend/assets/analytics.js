// Chart.js global dark theme defaults
Chart.defaults.color = "#8a93a3";
Chart.defaults.borderColor = "#2a3441";
Chart.defaults.font.family = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";

const COLORS = ["#4f9cff", "#4ade80", "#fbbf24", "#ff8080", "#a78bfa", "#34d399", "#f472b6", "#60a5fa", "#fb923c", "#94a3b8"];

async function loadAnalytics() {
  const response = await apiFetch("/analytics/summary");
  if (!response) return;

  const data = await response.json();

  renderStats(data.summary);
  renderMonthChart(data.cases_by_month);
  renderIncidentChart(data.cases_by_incident_type);
  renderOfficerChart(data.cases_by_officer);
  renderReviewChart(data.review_by_reason);
}

// ── Summary cards ────────────────────────────────────────────────────────

function renderStats(summary) {
  const statsRow = document.getElementById("statsRow");
  statsRow.innerHTML = `
    <div class="stat-card total">
      <div class="num">${summary.total_cases}</div>
      <div class="label">Total Cases</div>
    </div>
    <div class="stat-card open">
      <div class="num">${summary.open_cases}</div>
      <div class="label">Open</div>
    </div>
    <div class="stat-card closed">
      <div class="num">${summary.closed_cases}</div>
      <div class="label">Closed</div>
    </div>
    <div class="stat-card pending">
      <div class="num">${summary.pending_cases}</div>
      <div class="label">Pending</div>
    </div>
    <div class="stat-card flagged">
      <div class="num">${summary.flagged_cases}</div>
      <div class="label">Flagged</div>
    </div>
  `;
}

// ── Cases per month (line chart) ────────────────────────────────────────

function renderMonthChart(data) {
  const ctx = document.getElementById("monthChart");

  if (!data || data.length === 0) {
    showNoData(ctx, "monthChart");
    return;
  }

  new Chart(ctx, {
    type: "line",
    data: {
      labels: data.map(d => d.label),
      datasets: [{
        label: "Cases",
        data: data.map(d => d.count),
        borderColor: "#4f9cff",
        backgroundColor: "rgba(79, 156, 255, 0.1)",
        tension: 0.3,
        fill: true,
        pointBackgroundColor: "#4f9cff",
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { stepSize: 1 }, grid: { color: "#2a3441" } },
        x: { grid: { display: false } }
      }
    }
  });
}

// ── Cases by incident type (doughnut) ───────────────────────────────────

function renderIncidentChart(data) {
  const ctx = document.getElementById("incidentChart");

  if (!data || data.length === 0) {
    showNoData(ctx, "incidentChart");
    return;
  }

  new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: data.map(d => d.label),
      datasets: [{
        data: data.map(d => d.count),
        backgroundColor: COLORS,
        borderColor: "#1a2129",
        borderWidth: 2,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "right", labels: { boxWidth: 12, padding: 12, font: { size: 11 } } }
      }
    }
  });
}

// ── Cases by officer (horizontal bar) ───────────────────────────────────

function renderOfficerChart(data) {
  const ctx = document.getElementById("officerChart");

  if (!data || data.length === 0) {
    showNoData(ctx, "officerChart");
    return;
  }

  new Chart(ctx, {
    type: "bar",
    data: {
      labels: data.map(d => d.label),
      datasets: [{
        label: "Cases",
        data: data.map(d => d.count),
        backgroundColor: "#4ade80",
        borderRadius: 4,
      }]
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, ticks: { stepSize: 1 }, grid: { color: "#2a3441" } },
        y: { grid: { display: false } }
      }
    }
  });
}

// ── Review queue flag reasons (bar) ─────────────────────────────────────

function renderReviewChart(data) {
  const ctx = document.getElementById("reviewChart");

  if (!data || data.length === 0) {
    showNoData(ctx, "reviewChart");
    return;
  }

  new Chart(ctx, {
    type: "bar",
    data: {
      labels: data.map(d => d.label),
      datasets: [{
        label: "Flagged Cases",
        data: data.map(d => d.count),
        backgroundColor: ["#ff8080", "#fbbf24", "#a78bfa", "#60a5fa", "#f472b6"],
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { stepSize: 1 }, grid: { color: "#2a3441" } },
        x: { grid: { display: false } }
      }
    }
  });
}

// ── No-data fallback ─────────────────────────────────────────────────────

function showNoData(canvasEl, id) {
  const container = canvasEl.parentElement;
  container.innerHTML = `<div class="no-data-msg">No data available yet</div>`;
}

// ── Init ─────────────────────────────────────────────────────────────────

loadAnalytics();