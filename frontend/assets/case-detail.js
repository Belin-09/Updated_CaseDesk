const params = new URLSearchParams(window.location.search);
const caseId = params.get("id");
const searchTerm = params.get("search");

if (!caseId) {
  window.location.href = "dashboard.html";
}

// Update back link to preserve search query
if (searchTerm) {
  const backLink = document.querySelector(".back-link");
  if (backLink) {
    backLink.href = `dashboard.html?search=${encodeURIComponent(searchTerm)}`;
  }
}

const fieldIds = ["officer", "date", "location", "incident_type", "complainant", "suspect", "evidence", "notes", "status"];

async function loadCase() {
  const response = await apiFetch(`/cases/${caseId}`);
  if (!response) return;

  if (!response.ok) {
    document.getElementById("caseTitle").textContent = "Case not found";
    return;
  }

  const c = await response.json();

  document.getElementById("caseTitle").textContent = c.case_name || c.file_name || `Case #${c.id}`;
  document.getElementById("caseSubtitle").textContent = `Case #${c.id}`;

  fieldIds.forEach(f => {
    const el = document.getElementById(`f_${f}`);
    if (el) {
      el.value = c[f] || (f === "status" ? "open" : "");

      // Reset any previous match styling
      el.classList.remove("field-highlighted");
      const label = el.previousElementSibling;
      if (label && label.tagName === "LABEL") {
        const badge = label.querySelector(".field-match-badge");
        if (badge) badge.remove();
      }

      // Add highlight if field matches the search query
      if (searchTerm && c[f] && c[f].toLowerCase().includes(searchTerm.toLowerCase())) {
        el.classList.add("field-highlighted");
        if (label && label.tagName === "LABEL") {
          const badge = document.createElement("span");
          badge.className = "field-match-badge";
          badge.textContent = "Match";
          label.appendChild(badge);
        }
      }
    }
  });

  let previewContainer = document.getElementById("documentPreviewContainer");
  let rawTextBox = document.getElementById("rawTextBox");
  
  if (!previewContainer && rawTextBox) {
    previewContainer = document.createElement("div");
    previewContainer.id = "documentPreviewContainer";
    previewContainer.style.marginTop = "10px";
    rawTextBox.parentNode.insertBefore(previewContainer, rawTextBox);
    
    const card = rawTextBox.closest(".detail-card");
    if (card) {
      const heading = card.querySelector("h3");
      if (heading) heading.textContent = "Document Preview";
    }
  }

  let tabsContainer = document.getElementById("previewTabsContainer");
  if (!tabsContainer && previewContainer) {
    tabsContainer = document.createElement("div");
    tabsContainer.id = "previewTabsContainer";
    tabsContainer.className = "preview-tabs";
    previewContainer.parentNode.insertBefore(tabsContainer, previewContainer);
  }

  // Hide the source files card
  const sourceFilesCard = document.getElementById("fileList")?.closest(".detail-card");
  if (sourceFilesCard) {
    sourceFilesCard.style.display = "none";
  }

  document.getElementById("m_id").textContent = c.id;
  document.getElementById("m_uploaded_by").textContent = c.uploaded_by || "—";
  document.getElementById("m_created_at").textContent = formatDateTime(c.created_at);
  document.getElementById("m_updated_at").textContent = formatDateTime(c.updated_at);
  document.getElementById("m_error_flag").textContent = c.error_flag ? "Yes" : "No";
  document.getElementById("m_error_reason").textContent = c.error_reason || "—";

  renderTabs(c.files || [], c.raw_text, c.file_name, c.id);

  // Load first preview on startup
  const docsCount = (c.files && c.files.length > 0) ? c.files.length : (c.file_name ? 1 : 0);
  if (docsCount > 0) {
    selectTab(0);
  } else {
    loadPreview(null, 0, null);
  }
}

function renderTabs(files, caseRawText, mainFileName, caseId) {
  const tabsContainer = document.getElementById("previewTabsContainer");
  if (!tabsContainer) return;

  let docs = [];
  if (files && files.length > 0) {
    docs = files;
  } else if (mainFileName) {
    docs = [{
      id: 0,
      file_name: mainFileName,
      file_type: mainFileName.split('.').pop().toLowerCase(),
      raw_text: caseRawText
    }];
  }

  if (docs.length === 0) {
    tabsContainer.style.display = "none";
    return;
  }

  tabsContainer.style.display = "flex";
  if (!tabsContainer.dataset.wheelBound) {
    tabsContainer.dataset.wheelBound = "true";
    tabsContainer.addEventListener("wheel", (evt) => {
      if (evt.deltaY !== 0) {
        evt.preventDefault();
        tabsContainer.scrollLeft += evt.deltaY;
      }
    }, { passive: false });
  }
  tabsContainer.innerHTML = docs.map((f, index) => {
    // Count hits in this particular file dynamically
    let fileHits = 0;
    const ext = f.file_name.split('.').pop().toLowerCase();
    const isImage = ["png", "jpg", "jpeg", "gif"].includes(ext);
    const textToSearch = f.raw_text || caseRawText;
    
    if (searchTerm && textToSearch && !isImage) {
      const lowerText = textToSearch.toLowerCase();
      const lowerTerm = searchTerm.toLowerCase();
      let pos = lowerText.indexOf(lowerTerm);
      while (pos !== -1) {
        fileHits++;
        pos = lowerText.indexOf(lowerTerm, pos + lowerTerm.length);
      }
    }

    const hitBadge = fileHits > 0 
      ? `<span class="tab-hit-badge">${fileHits} hit${fileHits !== 1 ? 's' : ''}</span>`
      : "";

    // Determine icon
    let icon = "📄";
    if (ext === "pdf") icon = "📕";
    else if (["png", "jpg", "jpeg"].includes(ext)) icon = "🖼️";

    return `
      <div class="preview-tab" id="tab-${index}" onclick="selectTab(${index})" title="${escapeHtml(f.file_name)}">
        <span>${icon} ${escapeHtml(f.file_name)}</span>
        ${hitBadge}
      </div>
    `;
  }).join("");

  window.previewDocsList = docs;
  window.caseMainRawText = caseRawText;
  window.currentCaseId = caseId;
}

window.selectTab = function(index) {
  const tabs = document.querySelectorAll(".preview-tab");
  tabs.forEach((tab, i) => {
    if (i === index) {
      tab.classList.add("active");
    } else {
      tab.classList.remove("active");
    }
  });

  const file = window.previewDocsList[index];
  // If it's a real case file (id != 0), use its individual raw_text (or empty if none).
  // If it's the fallback main case file (id == 0), use its raw_text or the case's main raw text.
  const rawText = (file.id === 0) ? (file.raw_text || window.caseMainRawText) : (file.raw_text || "");
  loadPreview(file.file_name, file.id, rawText);
};

function loadPreview(fileName, fileId, rawTextContent) {
  const previewContainer = document.getElementById("documentPreviewContainer");
  const rawTextBox = document.getElementById("rawTextBox");
  
  if (!previewContainer || !rawTextBox) return;
  
  if (fileName) {
    const ext = fileName.split('.').pop().toLowerCase();
    const currentToken = localStorage.getItem("token");
    const viewUrl = fileId === 0 
      ? `${API_BASE}/cases/${window.currentCaseId}/view-source?token=${currentToken}&_t=${Date.now()}`
      : `${API_BASE}/cases/files/${fileId}/view?token=${currentToken}&_t=${Date.now()}`;

    if (ext === "pdf") {
      let finalUrl = viewUrl;
      if (searchTerm) {
        finalUrl += `#search=${encodeURIComponent(searchTerm)}`;
      }
      previewContainer.innerHTML = `
        <iframe src="${finalUrl}" class="pdf-preview-iframe" style="width:100%; height:600px; border:1px solid #2a3441; border-radius:6px; background:#0f1419; margin-bottom: 12px;"></iframe>
        <div style="background:#1e293b; color:#38bdf8; padding:10px 14px; border-radius:6px; font-size:13px; margin-bottom:12px; font-weight:600; border:1px solid rgba(56, 189, 248, 0.2);">
          📕 PDF Document Text Preview (extracted text is shown below):
        </div>
      `;
      rawTextBox.style.display = "block";
      const textToDisplay = rawTextContent || "No extracted text available.";
      if (searchTerm) {
        rawTextBox.innerHTML = highlightSearchTerm(textToDisplay, searchTerm);
      } else {
        rawTextBox.textContent = textToDisplay;
      }
    } else if (["png", "jpg", "jpeg"].includes(ext)) {
      previewContainer.innerHTML = `
        <div style="text-align: center; background:#0f1419; padding: 20px; border:1px solid #2a3441; border-radius:6px; max-height: 600px; overflow: auto; margin-bottom: 12px;">
          <img src="${viewUrl}" class="image-preview-img" style="max-width:100%; height:auto; border-radius:4px;">
        </div>
        <div style="background:#1e293b; color:#38bdf8; padding:10px 14px; border-radius:6px; font-size:13px; margin-bottom:12px; font-weight:600; border:1px solid rgba(56, 189, 248, 0.2);">
          🖼️ Image Text OCR Preview (extracted text is shown below):
        </div>
      `;
      rawTextBox.style.display = "block";
      const textToDisplay = rawTextContent || "No extracted text available.";
      if (searchTerm) {
        rawTextBox.innerHTML = highlightSearchTerm(textToDisplay, searchTerm);
      } else {
        rawTextBox.textContent = textToDisplay;
      }
    } else {
      previewContainer.innerHTML = `
        <div style="background:#1e293b; color:#38bdf8; padding:10px 14px; border-radius:6px; font-size:13px; margin-bottom:12px; font-weight:600; border:1px solid rgba(56, 189, 248, 0.2);">
          📄 Word Document Preview (extracted text is shown below):
        </div>
      `;
      rawTextBox.style.display = "block";
      const textToDisplay = rawTextContent || "No extracted text available.";
      if (searchTerm) {
        rawTextBox.innerHTML = highlightSearchTerm(textToDisplay, searchTerm);
      } else {
        rawTextBox.textContent = textToDisplay;
      }
    }
  } else {
    previewContainer.innerHTML = `<div style="color:#5a6473; font-size:13px;">No document associated with this case.</div>`;
    rawTextBox.style.display = "none";
  }

  if (searchTerm && rawTextBox.style.display !== "none") {
    renderHitNavigator();
  } else {
    const existingNav = document.getElementById("hitNavigator");
    if (existingNav) existingNav.remove();
  }
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function highlightSearchTerm(text, term) {
  if (text === null || text === undefined || text === "") return "—";
  if (!term) return escapeHtml(text);
  
  const lowerText = text.toLowerCase();
  const lowerTerm = term.toLowerCase();
  
  let result = "";
  let lastIndex = 0;
  let hitIndex = 0;
  let index = lowerText.indexOf(lowerTerm, lastIndex);
  
  while (index !== -1) {
    result += escapeHtml(text.substring(lastIndex, index));
    result += `<mark class="search-highlight" data-hit-index="${hitIndex}">${escapeHtml(text.substring(index, index + term.length))}</mark>`;
    hitIndex++;
    lastIndex = index + term.length;
    index = lowerText.indexOf(lowerTerm, lastIndex);
  }
  
  result += escapeHtml(text.substring(lastIndex));
  return result;
}

// ── Hit Navigator ────────────────────────────────────────────────────────

let currentHitIndex = 0;
let totalHits = 0;

function renderHitNavigator() {
  // Remove any existing navigator
  const existing = document.getElementById("hitNavigator");
  if (existing) existing.remove();

  const rawTextBox = document.getElementById("rawTextBox");
  if (!rawTextBox) return;

  const marks = rawTextBox.querySelectorAll("mark.search-highlight");
  totalHits = marks.length;
  if (totalHits === 0) return;

  currentHitIndex = 0;

  const nav = document.createElement("div");
  nav.className = "hit-navigator";
  nav.id = "hitNavigator";
  nav.innerHTML = `
    <span class="hit-counter">🔍 <span class="hit-current" id="hitCurrentNum">1</span> of ${totalHits} hit${totalHits !== 1 ? "s" : ""} in text</span>
    <button id="hitPrevBtn" onclick="navigateHit(-1)">▲ Prev</button>
    <button id="hitNextBtn" onclick="navigateHit(1)">▼ Next</button>
  `;

  rawTextBox.parentNode.insertBefore(nav, rawTextBox);

  // Jump to first hit
  jumpToHit(0);
}

function jumpToHit(index) {
  const rawTextBox = document.getElementById("rawTextBox");
  if (!rawTextBox) return;

  const marks = rawTextBox.querySelectorAll("mark.search-highlight");
  if (marks.length === 0) return;

  // Clamp index
  if (index < 0) index = marks.length - 1;
  if (index >= marks.length) index = 0;
  currentHitIndex = index;

  // Remove active class from all, add to current
  marks.forEach(m => m.classList.remove("active-hit"));
  marks[currentHitIndex].classList.add("active-hit");

  // Scroll the mark into view inside the rawTextBox
  marks[currentHitIndex].scrollIntoView({ behavior: "smooth", block: "center" });

  // Update counter
  const counter = document.getElementById("hitCurrentNum");
  if (counter) counter.textContent = currentHitIndex + 1;
}

window.navigateHit = function(direction) {
  jumpToHit(currentHitIndex + direction);
};

function formatDateTime(isoStr) {
  if (!isoStr) return "—";
  const d = new Date(isoStr);
  return d.toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

// ── Save ─────────────────────────────────────────────────────────────────

document.getElementById("saveBtn").addEventListener("click", async () => {
  const saveBtn = document.getElementById("saveBtn");
  const saveStatus = document.getElementById("saveStatus");

  const payload = {};
  fieldIds.forEach(f => {
    payload[f] = document.getElementById(`f_${f}`).value;
  });

  saveBtn.disabled = true;
  saveBtn.textContent = "Saving...";

  try {
    const response = await apiFetch(`/cases/${caseId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Failed to save");

    saveStatus.textContent = "Saved successfully";
    saveStatus.style.color = "#4ade80";
    loadCase();

  } catch (err) {
    saveStatus.textContent = err.message;
    saveStatus.style.color = "#ff8080";
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = "Save Changes";
    setTimeout(() => { saveStatus.textContent = ""; }, 3000);
  }
});

// ── Export PDF ───────────────────────────────────────────────────────────

document.getElementById("exportBtn").addEventListener("click", async () => {
  const exportBtn = document.getElementById("exportBtn");
  exportBtn.disabled = true;
  exportBtn.textContent = "Generating...";

  try {
    const response = await apiFetch(`/export/${caseId}`);
    if (!response || !response.ok) {
      throw new Error("Failed to generate PDF");
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `case_${caseId}_report.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);

  } catch (err) {
    alert(err.message);
  } finally {
    exportBtn.disabled = false;
    exportBtn.textContent = "📄 Export PDF";
  }
});

// ── Delete ───────────────────────────────────────────────────────────────

document.getElementById("deleteBtn").addEventListener("click", async () => {
  if (!confirm("Are you sure you want to delete this case? This cannot be undone.")) return;

  const response = await apiFetch(`/cases/${caseId}`, { method: "DELETE" });
  if (!response) return;

  if (response.ok) {
    window.location.href = "dashboard.html";
  } else {
    const data = await response.json();
    alert(data.detail || "Failed to delete case");
  }
});

// ── Init ─────────────────────────────────────────────────────────────────

loadCase();