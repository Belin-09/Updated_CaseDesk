let currentPage = 1;
const pageSize = 12;

const caseGrid = document.getElementById("caseGrid");
const emptyState = document.getElementById("emptyState");
const totalCount = document.getElementById("totalCount");
const pagination = document.getElementById("pagination");

const searchInput = document.getElementById("searchInput");
const caseSearchInput = document.getElementById("caseSearchInput");
const statusFilter = document.getElementById("statusFilter");
const sortBy = document.getElementById("sortBy");
const sortOrder = document.getElementById("sortOrder");

let searchDebounce;

// ── Load cases ───────────────────────────────────────────────────────────

async function loadCases() {
  try {
    const params = new URLSearchParams({
      page: currentPage,
      page_size: pageSize,
      sort_by: sortBy.value,
      order: sortOrder.value,
    });

    if (searchInput.value.trim()) params.append("search", searchInput.value.trim());
    if (caseSearchInput.value.trim()) params.append("case_search", caseSearchInput.value.trim());
    if (statusFilter.value) params.append("status", statusFilter.value);

    const response = await apiFetch(`/cases/?${params.toString()}`);
    if (!response || !response.ok) {
      totalCount.textContent = "Error loading cases";
      return;
    }

    const data = await response.json();

    const isSearchActive = !!searchInput.value.trim();
    if (isSearchActive) {
      const hits = data.total_hits || 0;
      totalCount.innerHTML = `<span class="search-summary-highlight">${hits} hit${hits !== 1 ? "s" : ""}</span> across <span class="search-summary-highlight">${data.total} case${data.total !== 1 ? "s" : ""}</span> found`;
    } else {
      totalCount.innerHTML = `${data.total} case${data.total !== 1 ? "s" : ""} found`;
    }

    if (!data.cases || data.cases.length === 0) {
      caseGrid.innerHTML = "";
      emptyState.style.display = "block";
      pagination.innerHTML = "";
      return;
    }

    emptyState.style.display = "none";
    renderCases(data.cases);
    renderPagination(data.total_pages, data.page);
  } catch (err) {
    console.error("Failed to load cases:", err);
    totalCount.textContent = "Error loading cases";
  }
}

// ── Render cards ─────────────────────────────────────────────────────────

function renderCases(cases) {
  const searchTerm = searchInput.value.trim();
  const isSearchActive = !!searchTerm;
  caseGrid.innerHTML = cases.map(c => {
    const statusBadge = c.error_flag
      ? `<span class="badge badge-flagged">Flagged</span>`
      : `<span class="badge badge-${c.status || 'open'}">${c.status || 'open'}</span>`;

    const hitsBadge = (isSearchActive && c.hit_count !== undefined)
      ? `<span class="badge badge-hits">${c.hit_count} hit${c.hit_count !== 1 ? 's' : ''}</span>`
      : '';

    const detailUrl = `case-detail.html?id=${c.id}&v=1.6${isSearchActive ? '&search=' + encodeURIComponent(searchTerm) : ''}`;

    let matchedFilesHtml = "";
    if (c.matched_files && c.matched_files.length > 0) {
      matchedFilesHtml = `
        <div class="matched-files-section" style="margin-top: 12px; padding-top: 12px; border-top: 1px dashed #2a3441;">
          <div style="font-size: 11px; color: #8a93a3; text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.5px;">Matched in files:</div>
          <div style="display: flex; flex-wrap: wrap; gap: 6px;">
            ${c.matched_files.map(f => {
              const ext = f.file_name.split('.').pop().toLowerCase();
              let icon = "📄";
              if (ext === "pdf") icon = "📕";
              else if (["png", "jpg", "jpeg"].includes(ext)) icon = "🖼️";
              
              return `
                <span class="matched-file-pill" style="font-size: 12px; background: rgba(79, 156, 255, 0.08); border: 1px solid rgba(79, 156, 255, 0.25); color: #4f9cff; padding: 3px 8px; border-radius: 4px; display: inline-flex; align-items: center; gap: 4px;" title="${escapeHtml(f.file_name)}">
                  <span>${icon}</span>
                  <span style="max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(f.file_name)}</span>
                  <span style="background: rgba(79, 156, 255, 0.2); font-size: 10px; font-weight: 700; padding: 1px 4px; border-radius: 3px; margin-left: 2px;">${f.hit_count} hit${f.hit_count !== 1 ? 's' : ''}</span>
                </span>
              `;
            }).join("")}
          </div>
        </div>
      `;
    }

    return `
      <div class="case-card" onclick="window.location.href='${detailUrl}'">
        <div class="case-card-header">
          <div>
            <div class="case-card-title">${escapeHtml(c.case_name || c.file_name || 'Untitled Case')}</div>
            <div class="case-card-id">Case #${c.id}</div>
          </div>
          <div class="case-card-badges">
            ${statusBadge}
            ${hitsBadge}
          </div>
        </div>
        <div class="case-card-field">
          <span class="case-card-field-label">Officer</span>
          <span class="case-card-field-value">${escapeHtml(c.officer || '—')}</span>
        </div>
        <div class="case-card-field">
          <span class="case-card-field-label">Date</span>
          <span class="case-card-field-value">${escapeHtml(c.date || '—')}</span>
        </div>
        <div class="case-card-field">
          <span class="case-card-field-label">Location</span>
          <span class="case-card-field-value">${escapeHtml(c.location || '—')}</span>
        </div>
        <div class="case-card-field">
          <span class="case-card-field-label">Incident</span>
          <span class="case-card-field-value">${escapeHtml(c.incident_type || '—')}</span>
        </div>
        ${matchedFilesHtml}
        <div class="case-card-footer">
          <span>Uploaded by ${escapeHtml(c.uploaded_by || 'unknown')}</span>
          <span>${formatDate(c.created_at)}</span>
        </div>
      </div>
    `;
  }).join("");
}

function highlightSearchTerm(text, term) {
  if (text === null || text === undefined || text === "") return "—";
  if (!term) return escapeHtml(text);
  
  const lowerText = text.toLowerCase();
  const lowerTerm = term.toLowerCase();
  
  let result = "";
  let lastIndex = 0;
  let index = lowerText.indexOf(lowerTerm, lastIndex);
  
  while (index !== -1) {
    result += escapeHtml(text.substring(lastIndex, index));
    result += `<mark class="search-highlight">${escapeHtml(text.substring(index, index + term.length))}</mark>`;
    lastIndex = index + term.length;
    index = lowerText.indexOf(lowerTerm, lastIndex);
  }
  
  result += escapeHtml(text.substring(lastIndex));
  return result;
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function formatDate(isoStr) {
  if (!isoStr) return "";
  const d = new Date(isoStr);
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

// ── Pagination ───────────────────────────────────────────────────────────

function renderPagination(totalPages, page) {
  if (totalPages <= 1) {
    pagination.innerHTML = "";
    return;
  }

  pagination.innerHTML = `
    <button id="prevPage" ${page <= 1 ? "disabled" : ""}>← Prev</button>
    <span class="page-info">Page ${page} of ${totalPages}</span>
    <button id="nextPage" ${page >= totalPages ? "disabled" : ""}>Next →</button>
  `;

  document.getElementById("prevPage")?.addEventListener("click", () => {
    currentPage--;
    loadCases();
  });
  document.getElementById("nextPage")?.addEventListener("click", () => {
    currentPage++;
    loadCases();
  });
}

// ── Filters/search wiring ───────────────────────────────────────────────

searchInput.addEventListener("input", () => {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(() => {
    currentPage = 1;
    loadCases();
  }, 400);
});

caseSearchInput.addEventListener("input", () => {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(() => {
    currentPage = 1;
    loadCases();
  }, 400);
});

[statusFilter, sortBy, sortOrder].forEach(el => {
  el.addEventListener("change", () => {
    currentPage = 1;
    loadCases();
  });
});

// ── Upload modal ─────────────────────────────────────────────────────────

const uploadModal = document.getElementById("uploadModal");
const uploadBtn = document.getElementById("uploadBtn");
const cancelUploadBtn = document.getElementById("cancelUploadBtn");
const confirmUploadBtn = document.getElementById("confirmUploadBtn");
const fileInput = document.getElementById("fileInput");
const uploadStatus = document.getElementById("uploadStatus");

uploadBtn.addEventListener("click", () => {
  uploadModal.classList.add("show");
  uploadStatus.classList.remove("show", "success", "error");
  fileInput.value = "";
});

cancelUploadBtn.addEventListener("click", () => {
  uploadModal.classList.remove("show");
});

confirmUploadBtn.addEventListener("click", async () => {
  if (!fileInput.files.length) {
    showUploadStatus("Please select a file", "error");
    return;
  }

  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append("file", file);

  confirmUploadBtn.disabled = true;
  confirmUploadBtn.textContent = "Uploading...";

  try {
    const response = await apiFetch("/upload/", {
      method: "POST",
      body: formData
    });

    const data = await response.json();

    if (!response.ok) throw new Error(data.detail || "Upload failed");

    showUploadStatus(
      `Uploaded successfully. ${data.fields_extracted}/8 fields extracted.${data.error_flag ? ' Flagged for review.' : ''}`,
      "success"
    );

    setTimeout(() => {
      uploadModal.classList.remove("show");
      loadCases();
    }, 1500);

  } catch (err) {
    showUploadStatus(err.message, "error");
  } finally {
    confirmUploadBtn.disabled = false;
    confirmUploadBtn.textContent = "Upload";
  }
});

function showUploadStatus(message, type) {
  uploadStatus.textContent = message;
  uploadStatus.className = `upload-status show ${type}`;
}

// ── Scan Folder ──────────────────────────────────────────────────────────

const scanModal = document.getElementById("scanModal");
const scanFolderBtn = document.getElementById("scanFolderBtn");
const cancelScanBtn = document.getElementById("cancelScanBtn");
const confirmScanBtn = document.getElementById("confirmScanBtn");
const scanPathInput = document.getElementById("scanPathInput");
const browseFolderBtn = document.getElementById("browseFolderBtn");
const scanResults = document.getElementById("scanResults");
const scanStatus = document.getElementById("scanStatus");
const scanItemList = document.getElementById("scanItemList");

scanFolderBtn.addEventListener("click", () => {
  scanModal.classList.add("show");
  scanResults.style.display = "none";
  scanStatus.classList.remove("show", "success", "error");
  scanPathInput.value = "";
});

browseFolderBtn.addEventListener("click", async (e) => {
  e.stopPropagation();
  browseFolderBtn.disabled = true;
  const originalText = browseFolderBtn.textContent;
  browseFolderBtn.textContent = "Opening...";

  try {
    const response = await apiFetch("/upload/select-folder", {
      method: "POST"
    });
    if (response.ok) {
      const data = await response.json();
      if (data.folder_path) {
        scanPathInput.value = data.folder_path;
      } else if (data.message) {
        showScanStatus(data.message, "error");
      }
    }
  } catch (error) {
    console.error("Folder selector failed:", error);
    showScanStatus("Folder picker unavailable. Please type or paste folder path manually.", "error");
  } finally {
    browseFolderBtn.disabled = false;
    browseFolderBtn.textContent = originalText;
  }
});

cancelScanBtn.addEventListener("click", () => {
  scanModal.classList.remove("show");
  loadCases(); // refresh in case anything was processed
});

confirmScanBtn.addEventListener("click", async () => {
  const rootPath = scanPathInput.value.trim();
  if (!rootPath) {
    showScanStatus("Please enter a folder path", "error");
    return;
  }

  confirmScanBtn.disabled = true;
  confirmScanBtn.textContent = "Starting...";
  scanStatus.classList.remove("show", "success", "error");
  scanResults.style.display = "none";

  try {
    const response = await apiFetch("/upload/scan-folder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ root_path: rootPath })
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Failed to start scan");

    showScanStatus("Scan running in background...", "success");
    pollScanStatus();

  } catch (err) {
    showScanStatus(err.message, "error");
    confirmScanBtn.disabled = false;
    confirmScanBtn.textContent = "Scan";
  }
});

let pollInterval = null;

async function pollScanStatus() {
  if (pollInterval) clearInterval(pollInterval);

  const poll = async () => {
    const response = await apiFetch("/upload/scan-status");
    if (!response) return;

    const state = await response.json();

    document.getElementById("scanProcessed").textContent = state.processed;
    document.getElementById("scanSkipped").textContent = state.skipped;
    document.getElementById("scanReprocessed").textContent = state.reprocessed;
    document.getElementById("scanFailed").textContent = state.failed;

    const progressText = state.total > 0
      ? `Processed ${state.processed + state.skipped + state.reprocessed + state.failed} of ${state.total}${state.current_case ? ` — currently: ${state.current_case}` : ''}`
      : "Scanning...";

    showScanStatus(progressText, "success");

    scanItemList.innerHTML = (state.cases || []).map(c => `
      <div class="scan-item">
        <span>${escapeHtml(c.case_name)}</span>
        <span class="scan-item-status ${c.status}">
          ${c.status.toUpperCase()}
        </span>
      </div>
    `).join("");

    scanResults.style.display = "block";

    if (activeScanBanner) {
      if (state.active || state.status === "running") {
        activeScanBanner.style.display = "block";
        if (bannerScanProgress) {
          bannerScanProgress.textContent = state.total > 0
            ? `Processed ${state.processed + state.skipped + state.reprocessed + state.failed} of ${state.total}${state.current_case ? ` (currently: ${state.current_case})` : ''}`
            : "Scanning...";
        }
      }
    }

    if (state.status === "completed" || state.status === "failed") {
      clearInterval(pollInterval);

      confirmScanBtn.disabled = false;
      confirmScanBtn.textContent = "Scan";

      if (activeScanBanner) {
        if (bannerScanProgress) {
          bannerScanProgress.textContent = state.status === "completed" 
            ? `Scan completed! ${state.processed} processed, ${state.reprocessed} reprocessed, ${state.skipped} skipped.`
            : `Scan failed: ${state.error}`;
        }
        setTimeout(() => {
          activeScanBanner.style.display = "none";
        }, 5000);
      }

      if (state.status === "completed") {
        showScanStatus(
          `Scan complete. ${state.processed} processed, ${state.reprocessed} reprocessed, ${state.skipped} skipped, ${state.failed} failed.`,
          "success"
        );
        loadCases();
      } else {
        showScanStatus(`Scan failed: ${state.error}`, "error");
      }
    }
  };

  // Run immediately
  await poll();

  // Then every 2 seconds
  pollInterval = setInterval(poll, 2000);
}

function showScanStatus(message, type) {
  scanStatus.textContent = message;
  scanStatus.className = `upload-status show ${type}`;
}

// ── Active Scan Banner Elements & Controls ───────────────────────────────
const activeScanBanner = document.getElementById("activeScanBanner");
const bannerScanProgress = document.getElementById("bannerScanProgress");
const openScanModalBannerBtn = document.getElementById("openScanModalBannerBtn");

if (openScanModalBannerBtn) {
  openScanModalBannerBtn.addEventListener("click", () => {
    scanModal.classList.add("show");
  });
}

async function checkBackgroundScanOnLoad() {
  try {
    const response = await apiFetch("/upload/scan-status");
    if (!response || !response.ok) return;
    const state = await response.json();
    if (state.active || state.status === "running") {
      if (activeScanBanner) activeScanBanner.style.display = "block";
      pollScanStatus();
    }
  } catch (err) {
    console.error("Failed to check scan status on load:", err);
  }
}

// ── Init ─────────────────────────────────────────────────────────────────

const urlParams = new URLSearchParams(window.location.search);
const initialSearch = urlParams.get("search");
if (initialSearch) {
  searchInput.value = initialSearch;
}

loadCases();
checkBackgroundScanOnLoad();

// ── User Role and Navigation buttons visibility ───────────────────────────
const role = localStorage.getItem("role") || "officer";
const userMgmtBtn = document.getElementById("userMgmtBtn");
if (role === "admin") {
  userMgmtBtn.style.display = "inline-block";
}

// ── Change Password Modal Elements ───────────────────────────────────────
const changePasswordBtn = document.getElementById("changePasswordBtn");
const changePasswordModal = document.getElementById("changePasswordModal");
const cancelChangePasswordBtn = document.getElementById("cancelChangePasswordBtn");
const confirmChangePasswordBtn = document.getElementById("confirmChangePasswordBtn");
const currentPasswordInput = document.getElementById("currentPasswordInput");
const newPasswordInput = document.getElementById("newPasswordInput");
const changePasswordStatus = document.getElementById("changePasswordStatus");
const forcePasswordNotice = document.getElementById("forcePasswordNotice");

function checkForcePasswordChange() {
  if (localStorage.getItem("must_change_password") === "true") {
    changePasswordModal.classList.add("show");
    if (forcePasswordNotice) forcePasswordNotice.style.display = "block";
    if (cancelChangePasswordBtn) cancelChangePasswordBtn.style.display = "none";
  } else {
    if (forcePasswordNotice) forcePasswordNotice.style.display = "none";
    if (cancelChangePasswordBtn) cancelChangePasswordBtn.style.display = "inline-block";
  }
}

changePasswordBtn.addEventListener("click", () => {
  changePasswordModal.classList.add("show");
  changePasswordStatus.classList.remove("show", "success", "error");
  currentPasswordInput.value = "";
  newPasswordInput.value = "";
  checkForcePasswordChange();
});

cancelChangePasswordBtn.addEventListener("click", () => {
  if (localStorage.getItem("must_change_password") !== "true") {
    changePasswordModal.classList.remove("show");
  }
});

confirmChangePasswordBtn.addEventListener("click", async () => {
  const current_password = currentPasswordInput.value;
  const new_password = newPasswordInput.value;
  if (!current_password || !new_password) {
    showStatusMsg(changePasswordStatus, "Please fill in all fields", "error");
    return;
  }

  if (new_password.length < 6) {
    showStatusMsg(changePasswordStatus, "New password must be at least 6 characters long", "error");
    return;
  }

  confirmChangePasswordBtn.disabled = true;
  confirmChangePasswordBtn.textContent = "Updating...";

  try {
    const response = await apiFetch("/auth/change-password", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password, new_password })
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Failed to change password");

    localStorage.setItem("must_change_password", "false");
    if (forcePasswordNotice) forcePasswordNotice.style.display = "none";
    if (cancelChangePasswordBtn) cancelChangePasswordBtn.style.display = "inline-block";

    showStatusMsg(changePasswordStatus, "Password changed successfully!", "success");
    setTimeout(() => {
      changePasswordModal.classList.remove("show");
    }, 1500);
  } catch (err) {
    showStatusMsg(changePasswordStatus, err.message, "error");
  } finally {
    confirmChangePasswordBtn.disabled = false;
    confirmChangePasswordBtn.textContent = "Change Password";
  }
});

// Auto-check on dashboard load
checkForcePasswordChange();

// ── User Management Modal Elements ───────────────────────────────────────
const userMgmtModal = document.getElementById("userMgmtModal");
const closeUserMgmtBtn = document.getElementById("closeUserMgmtBtn");
const newUsernameInput = document.getElementById("newUsername");
const newUserPasswordInput = document.getElementById("newUserPassword");
const newUserRoleInput = document.getElementById("newUserRole");
const createUserBtn = document.getElementById("createUserBtn");
const createUserStatus = document.getElementById("createUserStatus");
const userListBody = document.getElementById("userListBody");

userMgmtBtn.addEventListener("click", () => {
  userMgmtModal.classList.add("show");
  createUserStatus.classList.remove("show", "success", "error");
  newUsernameInput.value = "";
  newUserPasswordInput.value = "";
  newUserRoleInput.value = "officer";
  loadUsers();
});

closeUserMgmtBtn.addEventListener("click", () => {
  userMgmtModal.classList.remove("show");
});

async function loadUsers() {
  userListBody.innerHTML = `<tr><td colspan="3" style="text-align:center; color:#8a93a3;">Loading...</td></tr>`;
  try {
    const response = await apiFetch("/auth/users");
    if (!response) return;
    const users = await response.json();
    if (!response.ok) throw new Error(users.detail || "Failed to load users");

    userListBody.innerHTML = users.map(u => {
      const createdStr = u.created_at ? new Date(u.created_at).toLocaleDateString("en-IN") : "—";
      return `
        <tr>
          <td style="padding: 8px 5px;">${escapeHtml(u.username)}</td>
          <td style="padding: 8px 5px;"><span class="badge ${u.role === 'admin' ? 'badge-pending' : 'badge-closed'}">${escapeHtml(u.role)}</span></td>
          <td style="padding: 8px 5px;">${escapeHtml(createdStr)}</td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    userListBody.innerHTML = `<tr><td colspan="3" style="text-align:center; color:#ff8080;">${escapeHtml(err.message)}</td></tr>`;
  }
}

createUserBtn.addEventListener("click", async () => {
  const username = newUsernameInput.value.trim();
  const password = newUserPasswordInput.value;
  const role = newUserRoleInput.value;

  if (!username || !password || !role) {
    showStatusMsg(createUserStatus, "Please fill in all fields", "error");
    return;
  }

  if (password.length < 6) {
    showStatusMsg(createUserStatus, "Password must be at least 6 characters long", "error");
    return;
  }

  createUserBtn.disabled = true;
  createUserBtn.textContent = "Creating...";

  try {
    const response = await apiFetch("/auth/create-user", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, role })
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Failed to create user");

    showStatusMsg(createUserStatus, "User created successfully!", "success");
    newUsernameInput.value = "";
    newUserPasswordInput.value = "";
    newUserRoleInput.value = "officer";
    loadUsers();
  } catch (err) {
    showStatusMsg(createUserStatus, err.message, "error");
  } finally {
    createUserBtn.disabled = false;
    createUserBtn.textContent = "Add User";
  }
});

function showStatusMsg(element, message, type) {
  element.textContent = message;
  element.className = `upload-status show ${type}`;
}