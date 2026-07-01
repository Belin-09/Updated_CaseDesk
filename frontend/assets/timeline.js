async function loadTimeline() {
  const response = await apiFetch("/cases/timeline/all");
  if (!response) return;

  const data = await response.json();
  const container = document.getElementById("timelineContainer");
  const emptyState = document.getElementById("emptyState");
  const timelineCount = document.getElementById("timelineCount");

  timelineCount.textContent = `${data.total} case${data.total !== 1 ? "s" : ""} across ${data.timeline.length} day${data.timeline.length !== 1 ? "s" : ""}`;

  if (data.timeline.length === 0) {
    container.innerHTML = "";
    emptyState.style.display = "block";
    return;
  }

  emptyState.style.display = "none";

  container.innerHTML = data.timeline.map(group => `
    <div class="timeline-group">
      <div class="timeline-date-marker"></div>
      <div class="timeline-date-label">${formatGroupDate(group.date)}</div>
      <div class="timeline-date-count">${group.cases.length} case${group.cases.length !== 1 ? "s" : ""}</div>
      <div class="timeline-cases">
        ${group.cases.map(c => `
          <div class="timeline-card ${c.error_flag ? 'flagged' : ''}" onclick="window.location.href='case-detail.html?id=${c.id}&v=1.6'">
            <div class="timeline-card-left">
              <div class="title">${escapeHtml(c.case_name || c.file_name || 'Untitled Case')}</div>
              <div class="meta">
                Case #${c.id}
                ${c.officer ? ` · ${escapeHtml(c.officer)}` : ''}
                ${c.location ? ` · ${escapeHtml(c.location)}` : ''}
                ${c.incident_type ? ` · ${escapeHtml(c.incident_type)}` : ''}
                ${c.error_flag ? ' · <span style="color:#ff8080;">Flagged</span>' : ` · ${c.status || 'open'}`}
              </div>
            </div>
            <div class="timeline-card-time">${formatTime(c.created_at)}</div>
          </div>
        `).join("")}
      </div>
    </div>
  `).join("");
}

function formatGroupDate(dateStr) {
  if (dateStr === "Unknown") return "Unknown Date";
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}

function formatTime(isoStr) {
  if (!isoStr) return "";
  const d = new Date(isoStr);
  return d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

loadTimeline();