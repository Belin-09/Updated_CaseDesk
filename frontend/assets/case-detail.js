const params = new URLSearchParams(window.location.search);
const caseId = params.get("id");
let searchTerm = params.get("search");

// Set search input value if search term exists in URL
window.addEventListener("DOMContentLoaded", () => {
  const searchInput = document.getElementById("caseSearchInput");
  if (searchInput && searchTerm) {
    searchInput.value = searchTerm;
  }
});

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

const fieldIds = ["analyst", "investigating_officer", "pertains_service_no", "pertains_name", "pertains_unit", "date_deposition", "date_issuance", "date_intimation", "date_return", "status"];

async function loadCase() {
  const response = await apiFetch(`/cases/${caseId}`);
  if (!response) return;

  if (!response.ok) {
    document.getElementById("caseTitle").textContent = "Case not found";
    return;
  }

  const c = await response.json();

  document.getElementById("caseTitle").textContent = c.case_name || c.file_name || 'Untitled Case';
  document.getElementById("caseSubtitle").textContent = "";

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
  let sidebar = document.getElementById("previewSidebar");

  if (!tabsContainer && previewContainer) {
    tabsContainer = document.createElement("div");
    tabsContainer.id = "previewTabsContainer";
    tabsContainer.className = "preview-tabs vertical-tabs";
    if (sidebar) {
      sidebar.appendChild(tabsContainer);
    } else {
      previewContainer.parentNode.insertBefore(tabsContainer, previewContainer);
    }
  }

  let subTabsContainer = document.getElementById("previewSubTabsContainer");
  if (subTabsContainer) {
    subTabsContainer.remove(); // Clean up on reload
  }

  // Hide the source files card
  const sourceFilesCard = document.getElementById("fileList")?.closest(".detail-card");
  if (sourceFilesCard) {
    sourceFilesCard.style.display = "none";
  }


  document.getElementById("m_uploaded_by").textContent = c.uploaded_by || "—";
  document.getElementById("m_created_at").textContent = formatDateTime(c.created_at);
  document.getElementById("m_updated_at").textContent = formatDateTime(c.updated_at);
  document.getElementById("m_error_flag").textContent = c.error_flag ? "Yes" : "No";
  document.getElementById("m_error_reason").textContent = c.error_reason || "—";

  renderTabs(c.files || [], c.raw_text, c.file_name, c.id, c.source_folder);

  // Load first preview on startup
  const docsCount = (c.files && c.files.length > 0) ? c.files.length : (c.file_name ? 1 : 0);
  if (docsCount > 0) {
    let startIndex = 0;
    if (searchTerm && window.previewDocsList) {
      const matchIndex = window.previewDocsList.findIndex(d => d.hit_count > 0);
      if (matchIndex !== -1) {
        startIndex = matchIndex;
      }
    }
    selectTab(startIndex);
  } else {
    loadPreview(null, 0, null);
  }
}

function renderTabs(files, caseRawText, mainFileName, caseId, sourceFolder) {
  const tabsContainer = document.getElementById("previewTabsContainer");
  if (!tabsContainer) return;

  let docs = [];
  if (files && files.length > 0) {
    docs = files;
  } else if (mainFileName) {
    docs = [{
      id: 0,
      file_name: mainFileName,
      file_path: null,
      file_type: mainFileName.split('.').pop().toLowerCase(),
      raw_text: caseRawText
    }];
  }

  if (docs.length === 0) {
    tabsContainer.style.display = "none";
    return;
  }

  // Calculate hits and add properties to flat docs list
  docs.forEach((f, index) => {
    f.flatIndex = index;
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
    f.hit_count = fileHits;

    if (!f.file_path || !sourceFolder) {
      f.folderName = null;
      return;
    }
    
    let rel = f.file_path;
    if (rel.toLowerCase().startsWith(sourceFolder.toLowerCase())) {
      rel = rel.substring(sourceFolder.length);
    }
    rel = rel.replace(/^[\\\/]/, "").replace(/\\/g, "/");

    if (rel.includes("/")) {
      const folderName = rel.substring(0, rel.lastIndexOf("/"));
      const displayFolderName = folderName.replace(/\//g, " / ");
      f.folderName = displayFolderName;
      f.folderId = displayFolderName.replace(/[\s\/]+/g, "-");
    } else {
      f.folderName = null;
    }
  });

  // Group files by relative folder path
  const rootFiles = [];
  const groups = {}; // key: folder path, value: array of files

  docs.forEach(f => {
    if (f.folderName) {
      if (!groups[f.folderName]) {
        groups[f.folderName] = [];
      }
      groups[f.folderName].push(f);
    } else {
      rootFiles.push(f);
    }
  });

  window.previewDocsList = docs;
  window.caseMainRawText = caseRawText;
  window.currentCaseId = caseId;
  window.folderGroups = groups;
  window.activeFolderName = null;

  let html = "";

  // 1. Render root files
  rootFiles.forEach(f => {
    const hitBadge = f.hit_count > 0 
      ? `<span class="tab-hit-badge">${f.hit_count} hit${f.hit_count !== 1 ? 's' : ''}</span>`
      : "";
    const ext = f.file_name.split('.').pop().toLowerCase();
    let icon = "📄";
    if (ext === "pdf") icon = "📕";
    else if (["png", "jpg", "jpeg"].includes(ext)) icon = "🖼️";

    html += `
      <div class="preview-tab" id="tab-${f.flatIndex}" onclick="selectTab(${f.flatIndex})" title="${escapeHtml(f.file_name)}">
        <span>${icon} ${escapeHtml(f.file_name)}</span>
        ${hitBadge}
      </div>
    `;
  });

  // 2. Render folder tabs
  Object.keys(groups).sort().forEach(folderName => {
    const folderFiles = groups[folderName];
    const totalFolderHits = folderFiles.reduce((sum, file) => sum + file.hit_count, 0);
    const folderHitBadge = totalFolderHits > 0
      ? `<span class="tab-hit-badge folder-badge">${totalFolderHits} hit${totalFolderHits !== 1 ? 's' : ''}</span>`
      : "";
    const folderId = folderName.replace(/[\s\/]+/g, "-");

    html += `
      <div class="preview-folder-tab" id="folder-tab-${folderId}" onclick="selectFolderTab('${folderName}')">
        <span>📁 ${escapeHtml(folderName)}</span>
        ${folderHitBadge}
      </div>
    `;
  });

  tabsContainer.style.display = "flex";
  // Vertical layout doesn't need custom wheel to scrollLeft translation
  // if (!tabsContainer.dataset.wheelBound) {
  //   tabsContainer.dataset.wheelBound = "true";
  //   tabsContainer.addEventListener("wheel", (evt) => {
  //     if (evt.deltaY !== 0) {
  //       evt.preventDefault();
  //       tabsContainer.scrollLeft += evt.deltaY;
  //     }
  //   }, { passive: false });
  // }

  tabsContainer.innerHTML = html;
}

window.selectFolderTab = function(folderName) {
  const folderFiles = window.folderGroups[folderName];
  if (folderFiles && folderFiles.length > 0) {
    selectTab(folderFiles[0].flatIndex);
  }
};

window.renderSubTabs = function(folderName) {
  const subContainer = document.getElementById("previewSubTabsContainer");
  if (!subContainer) return;

  const folderFiles = window.folderGroups[folderName] || [];
  subContainer.innerHTML = folderFiles.map(f => {
    const hitBadge = f.hit_count > 0 
      ? `<span class="tab-hit-badge">${f.hit_count} hit${f.hit_count !== 1 ? 's' : ''}</span>`
      : "";
    const ext = f.file_name.split('.').pop().toLowerCase();
    let icon = "📄";
    if (ext === "pdf") icon = "📕";
    else if (["png", "jpg", "jpeg"].includes(ext)) icon = "🖼️";

    return `
      <div class="preview-sub-tab" id="sub-tab-${f.flatIndex}" onclick="selectTab(${f.flatIndex})" title="${escapeHtml(f.file_name)}">
        <span>${icon} ${escapeHtml(f.file_name)}</span>
        ${hitBadge}
      </div>
    `;
  }).join("");
};

window.selectTab = function(index) {
  const file = window.previewDocsList[index];
  if (!file) return;

  if (file.folderName) {
    let subContainer = document.getElementById("previewSubTabsContainer");
    if (!subContainer) {
      subContainer = document.createElement("div");
      subContainer.id = "previewSubTabsContainer";
      subContainer.className = "preview-sub-tabs vertical-sub-tabs";
    }

    subContainer.style.display = "flex";

    // Highlight the folder tab
    document.querySelectorAll(".preview-tab, .preview-folder-tab").forEach(tab => {
      tab.classList.remove("active");
    });
    const folderTab = document.getElementById(`folder-tab-${file.folderId}`);
    if (folderTab) {
      folderTab.classList.add("active");
      // Move the subContainer directly after the active folder tab (accordion effect)
      folderTab.parentNode.insertBefore(subContainer, folderTab.nextSibling);
    }

    if (window.activeFolderName !== file.folderName) {
      window.activeFolderName = file.folderName;
      window.renderSubTabs(file.folderName);
    }

    // Highlight sub-tab item
    document.querySelectorAll(".preview-sub-tab").forEach(sTab => {
      sTab.classList.remove("active");
    });
    const subTab = document.getElementById(`sub-tab-${index}`);
    if (subTab) {
      subTab.classList.add("active");
    }
  } else {
    window.activeFolderName = null;
    const subContainer = document.getElementById("previewSubTabsContainer");
    if (subContainer) {
      subContainer.style.display = "none";
    }

    document.querySelectorAll(".preview-tab, .preview-folder-tab").forEach(tab => {
      if (tab.id === `tab-${index}`) {
        tab.classList.add("active");
      } else {
        tab.classList.remove("active");
      }
    });
  }

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
    let viewUrl = fileId === 0 
      ? `${API_BASE}/cases/${window.currentCaseId}/view-source?token=${currentToken}&_t=${Date.now()}`
      : `${API_BASE}/cases/files/${fileId}/view?token=${currentToken}&_t=${Date.now()}`;

    if (searchTerm) {
      viewUrl += `&search=${encodeURIComponent(searchTerm)}`;
    }

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
        <iframe src="${viewUrl}" class="docx-preview-iframe" style="width:100%; height:600px; border:1px solid #2a3441; border-radius:6px; background:#0f1419; margin-bottom: 12px;"></iframe>
        <div style="background:#1e293b; color:#38bdf8; padding:10px 14px; border-radius:6px; font-size:13px; margin-bottom:12px; font-weight:600; border:1px solid rgba(56, 189, 248, 0.2);">
          📄 Word Document Text Preview (extracted text is shown below):
        </div>
      `;
      const iframe = previewContainer.querySelector(".docx-preview-iframe");
      if (iframe) {
        iframe.addEventListener("load", () => {
          if (searchTerm) {
            iframe.contentWindow.postMessage({ type: 'NAVIGATE_HIT', index: currentHitIndex }, '*');
          }
        });
      }
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

  const previewContainer = document.getElementById("documentPreviewContainer");
  if (previewContainer) {
    previewContainer.parentNode.insertBefore(nav, previewContainer);
  } else {
    rawTextBox.parentNode.insertBefore(nav, rawTextBox);
  }

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

  // Scroll the mark into view inside the rawTextBox without scrolling the page
  const targetMark = marks[currentHitIndex];
  const containerHalfHeight = rawTextBox.clientHeight / 2;
  // Calculate position of the mark relative to the scrolling container
  const markTop = targetMark.offsetTop;
  
  rawTextBox.scrollTo({
    top: markTop - containerHalfHeight,
    behavior: "smooth"
  });

  // Scroll in docx iframe if it exists
  const iframe = document.querySelector(".docx-preview-iframe");
  if (iframe && iframe.contentWindow) {
    iframe.contentWindow.postMessage({ type: 'NAVIGATE_HIT', index: currentHitIndex }, '*');
  }

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

// ── Reprocess Fields ─────────────────────────────────────────────────────

const reprocessBtn = document.getElementById("reprocessBtn");
if (reprocessBtn) {
  reprocessBtn.addEventListener("click", async () => {
    reprocessBtn.disabled = true;
    reprocessBtn.textContent = "Reprocessing...";

    try {
      const response = await apiFetch(`/cases/${caseId}/reprocess`, {
        method: "POST"
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Failed to reprocess fields");

      // Reload fields
      loadCase();
      
      const saveStatus = document.getElementById("saveStatus");
      if (saveStatus) {
        saveStatus.textContent = "Fields reprocessed & updated successfully";
        saveStatus.style.color = "#4ade80";
        setTimeout(() => { saveStatus.textContent = ""; }, 3000);
      }

    } catch (err) {
      alert(err.message);
    } finally {
      reprocessBtn.disabled = false;
      reprocessBtn.textContent = "🔄 Reprocess Fields";
    }
  });
}

// ── Case Search ──────────────────────────────────────────────────────────

function triggerCaseSearch() {
  const input = document.getElementById("caseSearchInput");
  if (!input) return;
  
  const term = input.value.trim();
  searchTerm = term;
  
  const newUrl = new URL(window.location.href);
  if (term) {
    newUrl.searchParams.set("search", term);
  } else {
    newUrl.searchParams.delete("search");
  }
  window.history.pushState({}, "", newUrl.toString());
  
  const backLink = document.querySelector(".back-link");
  if (backLink) {
    if (term) {
      backLink.href = `dashboard.html?search=${encodeURIComponent(term)}`;
    } else {
      backLink.href = "dashboard.html";
    }
  }
  
  loadCase();
}

window.addEventListener("DOMContentLoaded", () => {
  const searchBtn = document.getElementById("caseSearchBtn");
  const searchInput = document.getElementById("caseSearchInput");
  
  if (searchBtn) {
    searchBtn.addEventListener("click", triggerCaseSearch);
  }
  if (searchInput) {
    searchInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") {
        triggerCaseSearch();
      }
    });
  }
});

// ── Init ─────────────────────────────────────────────────────────────────

loadCase();