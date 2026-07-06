document.addEventListener("DOMContentLoaded", () => {
  loadAnalytics();
});

async function loadAnalytics() {
  try {
    const response = await apiFetch("/analytics/summary");
    if (!response || !response.ok) return;

    const data = await response.json();

    renderCasesPerYearChart(data.cases_per_year);
    renderSuspectedPioChart(data.pio_per_year);
    renderCasesByCommandChart(data.cases_by_command_year);
    renderCasesByTypeChart(data.cases_by_type_year);

  } catch (err) {
    console.error("Failed to load analytics:", err);
  }
}

// ── Chart 1: Cases per Year ────────────────────────────────────────────────

function renderCasesPerYearChart(data) {
  const ctx = document.getElementById("casesPerYearChart")?.getContext("2d");
  if (!ctx || !data) return;

  const labels = data.map(d => d.year);
  const counts = data.map(d => d.count);

  const colors = [
    "rgba(56, 189, 248, 0.75)",
    "rgba(79, 156, 255, 0.75)",
    "rgba(168, 85, 247, 0.75)",
    "rgba(52, 211, 153, 0.75)",
    "rgba(251, 191, 36, 0.75)",
    "rgba(251, 146, 60, 0.75)",
    "rgba(244, 63, 94, 0.75)"
  ];
  const borderColors = [
    "#38bdf8",
    "#4f9cff",
    "#a855f7",
    "#34d399",
    "#fbbf24",
    "#fb923c",
    "#f43f5e"
  ];

  new Chart(ctx, {
    type: "pie",
    data: {
      labels: labels,
      datasets: [{
        label: "Number of Cases",
        data: counts,
        backgroundColor: colors.slice(0, labels.length),
        borderColor: borderColors.slice(0, labels.length),
        borderWidth: 1.5,
        hoverOffset: 12
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: "right",
          labels: {
            color: "#8a93a3",
            font: { size: 11, weight: "bold" }
          }
        }
      },
      onClick: (event, activeElements) => {
        if (activeElements && activeElements.length > 0) {
          const index = activeElements[0].index;
          const year = labels[index];
          window.location.href = `cases.html?year=${encodeURIComponent(year)}`;
        }
      },
      onHover: (event, activeElements) => {
        event.native.target.style.cursor = activeElements.length > 0 ? "pointer" : "default";
      }
    }
  });
}

// ── Chart 2: Suspected PIO Numbers per Year ───────────────────────────────

function renderSuspectedPioChart(data) {
  const ctx = document.getElementById("suspectedPioChart")?.getContext("2d");
  if (!ctx || !data) return;

  const labels = data.map(d => d.year);
  const counts = data.map(d => d.count);

  const colors = [
    "rgba(244, 63, 94, 0.75)",
    "rgba(251, 146, 60, 0.75)",
    "rgba(251, 191, 36, 0.75)",
    "rgba(52, 211, 153, 0.75)",
    "rgba(168, 85, 247, 0.75)",
    "rgba(79, 156, 255, 0.75)",
    "rgba(56, 189, 248, 0.75)"
  ];
  const borderColors = [
    "#f43f5e",
    "#fb923c",
    "#fbbf24",
    "#34d399",
    "#a855f7",
    "#4f9cff",
    "#38bdf8"
  ];

  new Chart(ctx, {
    type: "pie",
    data: {
      labels: labels,
      datasets: [{
        label: "Suspected PIO Numbers",
        data: counts,
        backgroundColor: colors.slice(0, labels.length),
        borderColor: borderColors.slice(0, labels.length),
        borderWidth: 1.5,
        hoverOffset: 12
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: "right",
          labels: {
            color: "#8a93a3",
            font: { size: 11, weight: "bold" }
          }
        }
      },
      onClick: (event, activeElements) => {
        if (activeElements && activeElements.length > 0) {
          const index = activeElements[0].index;
          const year = labels[index];
          showPioNumbersForYear(year);
        }
      },
      onHover: (event, activeElements) => {
        event.native.target.style.cursor = activeElements.length > 0 ? "pointer" : "default";
      }
    }
  });
}

// ── PIO Details Modal Handling ───────────────────────────────────────────

const pioNumbersModal = document.getElementById("pioNumbersModal");
const closePioModalBtn = document.getElementById("closePioModalBtn");
const pioYearHeader = document.getElementById("pioYearHeader");
const pioListContainer = document.getElementById("pioListContainer");

if (closePioModalBtn) {
  closePioModalBtn.addEventListener("click", () => {
    pioNumbersModal.classList.remove("show");
  });
}

if (pioNumbersModal) {
  pioNumbersModal.addEventListener("click", (e) => {
    if (e.target === pioNumbersModal) {
      pioNumbersModal.classList.remove("show");
    }
  });
}

async function showPioNumbersForYear(year) {
  if (!pioNumbersModal || !pioYearHeader || !pioListContainer) return;
  
  pioYearHeader.textContent = year;
  pioListContainer.innerHTML = `<div style="text-align: center; padding: 20px; color: #8a93a3;">Loading...</div>`;
  pioNumbersModal.classList.add("show");
  
  try {
    const response = await apiFetch(`/analytics/pio-numbers?year=${encodeURIComponent(year)}`);
    if (!response || !response.ok) throw new Error("Failed to load numbers");
    
    const data = await response.json();
    const list = data.numbers || [];
    
    if (list.length === 0) {
      pioListContainer.innerHTML = `
        <div style="text-align: center; padding: 30px; color: #5a6473; font-size: 13.5px;">
          ❌ No suspected PIO numbers found for this year.
        </div>
      `;
      return;
    }
    
    pioListContainer.innerHTML = list.map(item => `
      <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px; background: #0f1419; border: 1px solid #2a3441; border-radius: 6px; margin-bottom: 8px; font-size: 13.5px; transition: all 0.15s ease;">
        <span style="color: #f43f5e; font-weight: 700; font-family: monospace; font-size: 15px; letter-spacing: 0.5px;">📱 ${escapeHtml(item.number)}</span>
        <a href="case-detail.html?id=${item.case_id}&search=${encodeURIComponent(item.number)}" style="color: #4f9cff; text-decoration: none; font-size: 12px; font-weight: 600; display: inline-flex; align-items: center; gap: 4px; padding: 4px 8px; background: rgba(79, 156, 255, 0.08); border-radius: 4px; border: 1px solid rgba(79, 156, 255, 0.15); transition: all 0.15s ease;" onmouseover="this.style.background='rgba(79,156,255,0.15)'" onmouseout="this.style.background='rgba(79,156,255,0.08)'">
          Go to Case
        </a>
      </div>
    `).join("");
    
  } catch (err) {
    pioListContainer.innerHTML = `
      <div style="color: #ff8080; text-align: center; padding: 20px;">
        Error: ${escapeHtml(err.message)}
      </div>
    `;
  }
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ── Chart 3: Cases per Command per Year ────────────────────────────────────

function renderCasesByCommandChart(data) {
  const canvas = document.getElementById("casesByCommandChart");
  if (!canvas || !data || !data.years) return;
  const ctx = canvas.getContext("2d");

  const years = data.years;
  const commands = data.commands;
  
  // Set width on wrapper parent
  const wrapper = document.getElementById("casesByCommandWrapper");
  if (wrapper) {
    const minWidth = Math.max(480, years.length * 100);
    wrapper.style.width = `${minWidth}px`;
  }

  const colors = [
    "#38bdf8", "#4f9cff", "#a855f7", "#34d399", "#fbbf24", "#fb923c", "#f43f5e", "#64748b"
  ];

  const datasets = commands.map((cmd, idx) => ({
    label: cmd,
    data: years.map(y => (data.data[y] && data.data[y][cmd]) || 0),
    backgroundColor: colors[idx % colors.length],
    borderRadius: 4
  }));

  new Chart(ctx, {
    type: "bar",
    data: {
      labels: years,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#e8eaed", font: { size: 11 } } }
      },
      scales: {
        x: { ticks: { color: "#8a93a3" }, grid: { display: false } },
        y: { ticks: { color: "#8a93a3", stepSize: 1 }, grid: { color: "rgba(255,255,255,0.06)" } }
      },
      onClick: (event, activeElements) => {
        if (activeElements && activeElements.length > 0) {
          const index = activeElements[0].index;
          const datasetIndex = activeElements[0].datasetIndex;
          
          const year = years[index];
          const command = datasets[datasetIndex].label;
          
          showCasesForCommandAndYear(command, year);
        }
      },
      onHover: (event, activeElements) => {
        event.native.target.style.cursor = activeElements.length > 0 ? "pointer" : "default";
      }
    }
  });
}

// ── Chart 4: Cases per Type per Year ───────────────────────────────────────

function renderCasesByTypeChart(data) {
  const canvas = document.getElementById("casesByTypeChart");
  if (!canvas || !data || !data.years) return;
  const ctx = canvas.getContext("2d");

  const years = data.years;
  const types = data.types;
  
  // Set width on wrapper parent
  const wrapper = document.getElementById("casesByTypeWrapper");
  if (wrapper) {
    const minWidth = Math.max(480, years.length * 100);
    wrapper.style.width = `${minWidth}px`;
  }

  const typeColors = {
    "Int (Cyber Espionage)": "#a855f7",
    "Int (Social Media violation)": "#38bdf8",
    "DV / Misc": "#34d399"
  };

  const datasets = types.map(t => ({
    label: t,
    data: years.map(y => (data.data[y] && data.data[y][t]) || 0),
    backgroundColor: typeColors[t] || "#8a93a3",
    borderRadius: 4
  }));

  new Chart(ctx, {
    type: "bar",
    data: {
      labels: years,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#e8eaed", font: { size: 11 } } }
      },
      scales: {
        x: { ticks: { color: "#8a93a3" }, grid: { display: false } },
        y: { ticks: { color: "#8a93a3", stepSize: 1 }, grid: { color: "rgba(255,255,255,0.06)" } }
      },
      onClick: (event, activeElements) => {
        if (activeElements && activeElements.length > 0) {
          const index = activeElements[0].index;
          const datasetIndex = activeElements[0].datasetIndex;
          
          const year = years[index];
          const type = datasets[datasetIndex].label;
          
          showCasesForTypeAndYear(type, year);
        }
      },
      onHover: (event, activeElements) => {
        event.native.target.style.cursor = activeElements.length > 0 ? "pointer" : "default";
      }
    }
  });
}

// ── Cases List Modal Handling ───────────────────────────────────────────

const casesListModal = document.getElementById("casesListModal");
const closeCasesListModalBtn = document.getElementById("closeCasesListModalBtn");
const casesListModalHeader = document.getElementById("casesListModalHeader");
const casesListModalSubheader = document.getElementById("casesListModalSubheader");
const casesListModalContainer = document.getElementById("casesListModalContainer");

if (closeCasesListModalBtn) {
  closeCasesListModalBtn.addEventListener("click", () => {
    casesListModal.classList.remove("show");
  });
}

if (casesListModal) {
  casesListModal.addEventListener("click", (e) => {
    if (e.target === casesListModal) {
      casesListModal.classList.remove("show");
    }
  });
}

async function fetchAndShowCasesModal(headerText, subheaderText, apiParams) {
  if (!casesListModal || !casesListModalHeader || !casesListModalSubheader || !casesListModalContainer) return;

  casesListModalHeader.textContent = headerText;
  casesListModalSubheader.textContent = subheaderText;
  casesListModalContainer.innerHTML = `<div style="text-align: center; padding: 20px; color: #8a93a3;">Loading...</div>`;
  casesListModal.classList.add("show");

  try {
    const response = await apiFetch(`/cases/?${apiParams.toString()}`);
    if (!response || !response.ok) throw new Error("Failed to load cases");

    const data = await response.json();
    const list = data.cases || [];

    if (list.length === 0) {
      casesListModalContainer.innerHTML = `
        <div style="text-align: center; padding: 30px; color: #5a6473; font-size: 13.5px;">
          ❌ No cases found matching these parameters.
        </div>
      `;
      return;
    }

    casesListModalContainer.innerHTML = list.map(c => {
      const statusBadge = c.error_flag
        ? `<span class="badge badge-flagged" style="padding: 2px 6px; font-size: 10px;">Flagged</span>`
        : `<span class="badge badge-${c.status || 'open'}" style="padding: 2px 6px; font-size: 10px;">${c.status || 'open'}</span>`;

      return `
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px; background: #0f1419; border: 1px solid #2a3441; border-radius: 6px; margin-bottom: 8px; font-size: 13.5px; transition: all 0.15s ease;">
          <div style="display: flex; flex-direction: column; gap: 4px;">
            <span style="color: #e8eaed; font-weight: 600;">${escapeHtml(c.case_name || c.file_name || 'Untitled Case')}</span>
            <div style="display: flex; gap: 8px; align-items: center; font-size: 11px; color: #8a93a3;">
              <span>Case #${c.id}</span>
              <span>•</span>
              <span>by ${escapeHtml(c.uploaded_by || 'unknown')}</span>
              <span>•</span>
              ${statusBadge}
            </div>
          </div>
          <a href="case-detail.html?id=${c.id}" style="color: #4f9cff; text-decoration: none; font-size: 12px; font-weight: 600; display: inline-flex; align-items: center; gap: 4px; padding: 4px 8px; background: rgba(79, 156, 255, 0.08); border-radius: 4px; border: 1px solid rgba(79, 156, 255, 0.15); transition: all 0.15s ease;" onmouseover="this.style.background='rgba(79,156,255,0.15)'" onmouseout="this.style.background='rgba(79,156,255,0.08)'">
            View Case
          </a>
        </div>
      `;
    }).join("");

  } catch (err) {
    casesListModalContainer.innerHTML = `
      <div style="color: #ff8080; text-align: center; padding: 20px;">
        Error: ${escapeHtml(err.message)}
      </div>
    `;
  }
}

function showCasesForCommandAndYear(command, year) {
  const params = new URLSearchParams({
    command: command,
    page_size: 100
  });
  if (year !== "Unknown") {
    params.append("year", year);
  }
  fetchAndShowCasesModal(
    `Cases — ${command} Command`,
    `List of cases under the ${command} command for the year ${year}:`,
    params
  );
}

function showCasesForTypeAndYear(type, year) {
  const params = new URLSearchParams({
    incident_type: type,
    page_size: 100
  });
  if (year !== "Unknown") {
    params.append("year", year);
  }
  fetchAndShowCasesModal(
    `Cases — ${type}`,
    `List of ${type} cases for the year ${year}:`,
    params
  );
}