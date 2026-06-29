let flaggedCases = [];
let selectedCaseId = null;
let activeFileIndex = 0;

const reviewList = document.getElementById("reviewList");
const reviewDetail = document.getElementById("reviewDetail");
const reviewCount = document.getElementById("reviewCount");
const emptyState = document.getElementById("emptyState");
const reasonFilter = document.getElementById("reasonFilter");

// ── Load flagged cases list ─────────────────────────────────────────────

async function loadReviewQueue() {
  const params = new URLSearchParams();
  if (reasonFilter.value) params.append("error_reason", reasonFilter.value);

  const response = await apiFetch(`/review/?${params.toString()}`);
  if (!response) return;

  const data = await response.json();
  flaggedCases = data.cases;

  reviewCount.textContent = `${data.total} case${data.total !== 1 ? "s" : ""} flagged for review`;

  if (flaggedCases.length === 0) {
    reviewList.innerHTML = "";
    emptyState.style.display = "block";
    reviewDetail.innerHTML = "Select a case from the list to review";
    reviewDetail.className = "review-detail-panel empty";
    return;
  }

  emptyState.style.display = "none";
  renderList();
}

function renderList() {
  reviewList.innerHTML = flaggedCases.map(c => `
    <div class="review-list-item ${c.id === selectedCaseId ? 'active' : ''}" onclick="selectCase(${c.id})">
      <div class="review-list-item-left">
        <div class="title">${escapeHtml(c.case_name || c.file_name || 'Untitled Case')}</div>
        <div class="meta">Case #${c.id} · ${escapeHtml(c.uploaded_by || 'unknown')}</div>
      </div>
      <span class="reason-badge">${c.error_reason}</span>
    </div>
  `).join("");
}

// ── Select + load detail ────────────────────────────────────────────────

async function selectCase(caseId) {
  selectedCaseId = caseId;
  activeFileIndex = 0;
  renderList();

  const response = await apiFetch(`/review/${caseId}`);
  if (!response) return;

  const c = await response.json();
  renderDetail(c);
}

function renderDetail(c) {
  reviewDetail.className = "review-detail-panel";

  const fileTabs = c.files.map((f, i) => `
    <div class="review-file-tab ${i === activeFileIndex ? 'active' : ''}" onclick="switchFile(${i})">
      ${escapeHtml(f.file_name)}
    </div>
  `).join("");

  const activeFile = c.files[activeFileIndex];

  reviewDetail.innerHTML = `
    <h3 style="font-size:16px; margin-bottom:4px;">${escapeHtml(c.case_name || 'Untitled Case')}</h3>
    <div style="font-size:12px; color:#5a6473; margin-bottom:18px;">
      Flag reason: <span style="color:#ff8080;">${c.error_reason}</span>
    </div>

    <div class="review-files-row">${fileTabs}</div>

    <div class="raw-text-box" style="margin-bottom:20px;">
      ${activeFile ? escapeHtml(activeFile.raw_text || 'No text extracted from this file.') : escapeHtml(c.raw_text || 'No text available.')}
      ${activeFile && activeFile.ocr_confidence !== null && activeFile.ocr_confidence !== undefined ? `<br><br><em>OCR Confidence: ${activeFile.ocr_confidence}%</em>` : ''}
      ${activeFile && activeFile.extraction_error ? `<br><br><span style="color:#ff8080;">Extraction error: ${escapeHtml(activeFile.extraction_error)}</span>` : ''}
    </div>

    <div class="field-row">
      <div class="field-group">
        <label>Officer</label>
        <input type="text" id="r_officer" value="${escapeAttr(c.officer)}">
      </div>
      <div class="field-group">
        <label>Date</label>
        <input type="text" id="r_date" value="${escapeAttr(c.date)}">
      </div>
    </div>
    <div class="field-row">
      <div class="field-group">
        <label>Location</label>
        <input type="text" id="r_location" value="${escapeAttr(c.location)}">
      </div>
      <div class="field-group">
        <label>Incident Type</label>
        <input type="text" id="r_incident_type" value="${escapeAttr(c.incident_type)}">
      </div>
    </div>
    <div class="field-row">
      <div class="field-group">
        <label>Complainant</label>
        <input type="text" id="r_complainant" value="${escapeAttr(c.complainant)}">
      </div>
      <div class="field-group">
        <label>Suspect</label>
        <input type="text" id="r_suspect" value="${escapeAttr(c.suspect)}">
      </div>
    </div>
    <div class="field-row">
      <div class="field-group" style="grid-column: span 2;">
        <label>Evidence</label>
        <textarea id="r_evidence">${escapeHtml(c.evidence)}</textarea>
      </div>
    </div>
    <div class="field-row">
      <div class="field-group" style="grid-column: span 2;">
        <label>Notes</label>
        <textarea id="r_notes">${escapeHtml(c.notes)}</textarea>
      </div>
    </div>
    <div class="field-group">
      <label>Review Note</label>
      <textarea id="r_review_note" placeholder="Explain what was corrected or why this is being escalated...">${escapeHtml(c.review_note)}</textarea>
    </div>

    <div class="review-actions">
      <button class="btn-success" id="resolveBtn">✓ Resolve</button>
      <button class="btn-warning" id="escalateBtn">⚠ Escalate</button>
    </div>
  `;

  document.getElementById("resolveBtn").addEventListener("click", () => resolveCase(c.id));
  document.getElementById("escalateBtn").addEventListener("click", () => escalateCase(c.id));

  window.currentFiles = c.files;
}

function switchFile(index) {
  activeFileIndex = index;
  const c = flaggedCases.find(fc => fc.id === selectedCaseId);
  selectCase(selectedCaseId); // reload to keep it simple and consistent
}

// ── Resolve ──────────────────────────────────────────────────────────────

async function resolveCase(caseId) {
  const payload = {
    officer: document.getElementById("r_officer").value,
    date: document.getElementById("r_date").value,
    location: document.getElementById("r_location").value,
    incident_type: document.getElementById("r_incident_type").value,
    complainant: document.getElementById("r_complainant").value,
    suspect: document.getElementById("r_suspect").value,
    evidence: document.getElementById("r_evidence").value,
    notes: document.getElementById("r_notes").value,
    review_note: document.getElementById("r_review_note").value,
  };

  const response = await apiFetch(`/review/${caseId}/resolve`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response) return;
  const data = await response.json();

  if (!response.ok) {
    alert(data.detail || "Failed to resolve case");
    return;
  }

  selectedCaseId = null;
  reviewDetail.innerHTML = "Select a case from the list to review";
  reviewDetail.className = "review-detail-panel empty";
  loadReviewQueue();
}

// ── Escalate ─────────────────────────────────────────────────────────────

async function escalateCase(caseId) {
  const reviewNote = document.getElementById("r_review_note").value.trim();

  if (!reviewNote) {
    alert("Please add a review note explaining the escalation before escalating.");
    return;
  }

  const response = await apiFetch(`/review/${caseId}/escalate`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ review_note: reviewNote })
  });

  if (!response) return;
  const data = await response.json();

  if (!response.ok) {
    alert(data.detail || "Failed to escalate case");
    return;
  }

  loadReviewQueue();
  selectCase(caseId);
}

// ── Helpers ──────────────────────────────────────────────────────────────

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function escapeAttr(str) {
  if (str === null || str === undefined) return "";
  return String(str).replace(/"/g, "&quot;");
}

// ── Wiring ───────────────────────────────────────────────────────────────

reasonFilter.addEventListener("change", () => {
  selectedCaseId = null;
  loadReviewQueue();
});

// ── Init ─────────────────────────────────────────────────────────────────

loadReviewQueue();