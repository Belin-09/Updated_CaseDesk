let currentPage = 1;
const pageSize = 12;

const caseGrid = document.getElementById("caseGrid");
const emptyState = document.getElementById("emptyState");
const totalCount = document.getElementById("totalCount");
const pagination = document.getElementById("pagination");

const searchInput = document.getElementById("searchInput");
const statusFilter = document.getElementById("statusFilter");
const sortBy = document.getElementById("sortBy");
const sortOrder = document.getElementById("sortOrder");

let searchDebounce;

// ── Load cases ───────────────────────────────────────────────────────────

async function loadCases() {
  const params = new URLSearchParams({
    page: currentPage,
    page_size: pageSize,
    sort_by: sortBy.value,
    order: sortOrder.value,
  });

  if (searchInput.value.trim()) params.append("search", searchInput.value.trim());
  if (statusFilter.value) params.append("status", statusFilter.value);

  const response = await apiFetch(`/cases/?${params.toString()}`);
  if (!response) return;

  const data = await response.json();

  const isSearchActive = !!searchInput.value.trim();
  if (isSearchActive) {
    const hits = data.total_hits || 0;
    totalCount.innerHTML = `<span class="search-summary-highlight">${hits} hit${hits !== 1 ? "s" : ""}</span> across <span class="search-summary-highlight">${data.total} case${data.total !== 1 ? "s" : ""}</span> found`;
  } else {
    totalCount.innerHTML = `${data.total} case${data.total !== 1 ? "s" : ""} found`;
  }

  if (data.cases.length === 0) {
    caseGrid.innerHTML = "";
    emptyState.style.display = "block";
    pagination.innerHTML = "";
    return;
  }

  emptyState.style.display = "none";
  renderCases(data.cases);
  renderPagination(data.total_pages, data.page);
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

    const detailUrl = `case-detail.html?id=${c.id}&v=1.5${isSearchActive ? '&search=' + encodeURIComponent(searchTerm) : ''}`;

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
const scanResults = document.getElementById("scanResults");
const scanStatus = document.getElementById("scanStatus");
const scanItemList = document.getElementById("scanItemList");

scanFolderBtn.addEventListener("click", () => {
  scanModal.classList.add("show");
  scanResults.style.display = "none";
  scanStatus.classList.remove("show", "success", "error");
  scanPathInput.value = "";
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

    if (state.status === "completed" || state.status === "failed") {
      clearInterval(pollInterval);

      confirmScanBtn.disabled = false;
      confirmScanBtn.textContent = "Scan";

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

// ── Init ─────────────────────────────────────────────────────────────────

const urlParams = new URLSearchParams(window.location.search);
const initialSearch = urlParams.get("search");
if (initialSearch) {
  searchInput.value = initialSearch;
}

loadCases();

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

changePasswordBtn.addEventListener("click", () => {
  changePasswordModal.classList.add("show");
  changePasswordStatus.classList.remove("show", "success", "error");
  currentPasswordInput.value = "";
  newPasswordInput.value = "";
});

cancelChangePasswordBtn.addEventListener("click", () => {
  changePasswordModal.classList.remove("show");
});

confirmChangePasswordBtn.addEventListener("click", async () => {
  const current_password = currentPasswordInput.value;
  const new_password = newPasswordInput.value;
  if (!current_password || !new_password) {
    showStatusMsg(changePasswordStatus, "Please fill in all fields", "error");
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