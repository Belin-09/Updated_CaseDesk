let flaggedCases = [];
let selectedCaseId = null;
let activeFileIndex = 0;
let currentDetailCase = null;

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
  reviewList.innerHTML = flaggedCases.map(c => {
    let shortReason = c.error_reason || "";
    let isExtractionEx = shortReason.startsWith("EXTRACTION_EXCEPTION:");
    let badgeText = isExtractionEx ? "EXTRACTION_EXCEPTION" : shortReason;
    
    return `
    <div class="review-list-item ${c.id === selectedCaseId ? 'active' : ''}" onclick="selectCase(${c.id})" style="flex-direction: column; align-items: stretch; gap: 8px;">
      <div style="display: flex; justify-content: space-between; align-items: flex-start;">
        <div class="review-list-item-left">
          <div class="title">${escapeHtml(c.case_name || c.file_name || 'Untitled Case')}</div>
          <div class="meta">Uploaded by ${escapeHtml(c.uploaded_by || 'unknown')} ${c.file_count ? `• ${c.file_count} files` : ''}</div>
        </div>
        <span class="reason-badge">${badgeText}</span>
      </div>
      ${isExtractionEx ? `<div style="font-size: 11px; color: #cc0000; background: #fff0f0; padding: 6px; border-radius: 4px; border: 1px solid #ffcccc; word-break: break-all;">${escapeHtml(shortReason.replace("EXTRACTION_EXCEPTION: ", ""))}</div>` : ''}
    </div>
  `}).join("");
}

// ── Select + load detail ────────────────────────────────────────────────

async function selectCase(caseId) {
  selectedCaseId = caseId;
  activeFileIndex = 0;
  renderList();

  const response = await apiFetch(`/review/${caseId}`);
  if (!response) return;

  const c = await response.json();
  currentDetailCase = c;
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

  let detailedReason = c.error_reason;
  if (c.error_reason === "LOW_FIELDS") {
      let missing = [];
      if (!c.analyst) missing.push("Analyst");
      if (!c.investigating_officer) missing.push("Investigating Officer");
      if (!c.pertains_service_no && !c.pertains_name && !c.pertains_unit) missing.push("Pertains Details");
      if (!c.incident_type) missing.push("Incident Type");
      if (!c.command) missing.push("Military Command");
      if (!c.date_deposition) missing.push("Deposition Date");
      if (missing.length > 0) detailedReason += ` (Missing: ${missing.join(", ")})`;
  } else if (c.error_reason === "LOW_OCR_CONFIDENCE") {
      let confs = c.files.map(f => f.ocr_confidence).filter(x => x != null);
      if (confs.length > 0) {
          let avg = Math.round(confs.reduce((a,b)=>a+b, 0) / confs.length);
          detailedReason += ` (Average confidence: ${avg}%)`;
      }
  }

  reviewDetail.innerHTML = `
    <h3 style="font-size:16px; margin-bottom:4px;">${escapeHtml(c.case_name || 'Untitled Case')}</h3>
    <div style="font-size:12px; color:#5a6473; margin-bottom:18px;">
      Flag reason: <span style="color:#ff8080; font-weight:600;">${escapeHtml(detailedReason)}</span>
    </div>

    <div class="review-files-row">${fileTabs}</div>

    <div class="raw-text-box" style="margin-bottom:20px;">
      ${activeFile ? escapeHtml(activeFile.raw_text || 'No text extracted from this file.') : escapeHtml(c.raw_text || 'No text available.')}
      ${activeFile && activeFile.ocr_confidence !== null && activeFile.ocr_confidence !== undefined ? `<br><br><em>OCR Confidence: ${activeFile.ocr_confidence}%</em>` : ''}
      ${activeFile && activeFile.extraction_error ? `<br><br><span style="color:#ff8080;">Extraction error: ${escapeHtml(activeFile.extraction_error)}</span>` : ''}
    </div>

    <div class="field-row">
      <div class="field-group">
        <label>Investigating Officer</label>
        <input type="text" id="r_investigating_officer" value="${escapeAttr(c.investigating_officer)}">
      </div>
      <div class="field-group">
        <label>Analyst</label>
        <input type="text" id="r_analyst" value="${escapeAttr(c.analyst)}">
      </div>
    </div>
    <div class="field-row" style="grid-template-columns: repeat(3, 1fr);">
      <div class="field-group">
        <label>Pertains Service No</label>
        <input type="text" id="r_pertains_service_no" value="${escapeAttr(c.pertains_service_no)}">
      </div>
      <div class="field-group">
        <label>Pertains Name</label>
        <input type="text" id="r_pertains_name" value="${escapeAttr(c.pertains_name)}">
      </div>
      <div class="field-group">
        <label>Pertains Unit</label>
        <input type="text" id="r_pertains_unit" value="${escapeAttr(c.pertains_unit)}">
      </div>
    </div>
    <div class="field-row" style="grid-template-columns: repeat(4, 1fr);">
      <div class="field-group">
        <label>Deposition Date</label>
        <input type="text" id="r_date_deposition" value="${escapeAttr(c.date_deposition)}">
      </div>
      <div class="field-group">
        <label>Hash Letter Issuance</label>
        <input type="text" id="r_date_issuance" value="${escapeAttr(c.date_issuance)}">
      </div>
      <div class="field-group">
        <label>Intimation Date</label>
        <input type="text" id="r_date_intimation" value="${escapeAttr(c.date_intimation)}">
      </div>
      <div class="field-group">
        <label>Return Date</label>
        <input type="text" id="r_date_return" value="${escapeAttr(c.date_return)}">
      </div>
    </div>
    <div class="field-row">
      <div class="field-group">
        <label>Incident Type</label>
        <input type="text" id="r_incident_type" value="${escapeAttr(c.incident_type)}">
      </div>
      <div class="field-group">
        <label>Military Command</label>
        <input type="text" id="r_command" value="${escapeAttr(c.command)}">
      </div>
    </div>
    <div class="field-group" style="margin-top: 15px;">
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
  if (currentDetailCase) {
    activeFileIndex = index;
    renderDetail(currentDetailCase);
  }
}

// ── Resolve ──────────────────────────────────────────────────────────────

async function resolveCase(caseId) {
  const payload = {
    analyst: document.getElementById("r_analyst").value,
    investigating_officer: document.getElementById("r_investigating_officer").value,
    pertains_service_no: document.getElementById("r_pertains_service_no").value,
    pertains_name: document.getElementById("r_pertains_name").value,
    pertains_unit: document.getElementById("r_pertains_unit").value,
    date_deposition: document.getElementById("r_date_deposition").value,
    date_issuance: document.getElementById("r_date_issuance").value,
    date_intimation: document.getElementById("r_date_intimation").value,
    date_return: document.getElementById("r_date_return").value,
    incident_type: document.getElementById("r_incident_type").value,
    command: document.getElementById("r_command").value,
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

// switchFile is defined above

loadReviewQueue();