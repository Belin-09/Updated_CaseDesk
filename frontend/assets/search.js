document.addEventListener("DOMContentLoaded", () => {
  const runSearchBtn = document.getElementById("runSearchBtn");
  const searchTermInput = document.getElementById("searchTermInput");
  const searchCategory = document.getElementById("searchCategory");
  const casesGrid = document.getElementById("casesGrid");
  const searchEmptyState = document.getElementById("searchEmptyState");
  const resultsCountBadge = document.getElementById("resultsCountBadge");

  if (runSearchBtn) {
    runSearchBtn.addEventListener("click", triggerSearch);
  }

  if (searchTermInput) {
    searchTermInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") {
        triggerSearch();
      }
    });
  }

  async function triggerSearch() {
    const category = searchCategory.value;
    const term = searchTermInput.value.trim();

    if (!term) {
      alert("Please enter a search query term.");
      return;
    }

    // Set loading state
    runSearchBtn.disabled = true;
    runSearchBtn.textContent = "Searching...";
    casesGrid.innerHTML = "";
    searchEmptyState.style.display = "none";
    resultsCountBadge.style.display = "none";

    try {
      const response = await apiFetch(`/cases/search/advanced?category=${category}&term=${encodeURIComponent(term)}`);
      if (!response) return;

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Failed to query database.");
      }

      const results = await response.json();
      displayResults(results, term);
    } catch (err) {
      casesGrid.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; color: #ff8080; padding: 40px; border: 1px solid #3a1c1c; background: rgba(58, 28, 28, 0.2); border-radius: 8px;">
          <strong>Error searching cases:</strong> ${escapeHtml(err.message)}
        </div>
      `;
    } finally {
      runSearchBtn.disabled = false;
      runSearchBtn.textContent = "Search Cases";
    }
  }

  function displayResults(cases, term) {
    if (cases.length === 0) {
      resultsCountBadge.style.display = "none";
      searchEmptyState.style.display = "block";
      searchEmptyState.innerHTML = `
        <div style="font-size: 48px; margin-bottom: 12px; filter: grayscale(1);">🔍</div>
        <h4 style="color: #e8eaed; font-size: 16px; margin-bottom: 6px;">No cases found</h4>
        <p style="font-size: 13px; max-width: 400px; margin: 0 auto;">No records matched your search term under this category. Please check spelling or try another field.</p>
      `;
      return;
    }

    // Update count badge
    resultsCountBadge.textContent = `${cases.length} case${cases.length !== 1 ? 's' : ''} found`;
    resultsCountBadge.style.display = "inline-block";
    searchEmptyState.style.display = "none";

    casesGrid.innerHTML = cases.map(c => {
      const detailUrl = `case-detail.html?id=${c.id}&v=1.8${term ? '&search=' + encodeURIComponent(term) : ''}`;
      
      const statusBadge = c.error_flag
        ? `<span class="badge badge-flagged">Flagged</span>`
        : `<span class="badge badge-${c.status || 'open'}">${c.status || 'open'}</span>`;

      return `
        <div class="case-card" onclick="window.location.href='${detailUrl}'" style="cursor: pointer;">
          <div class="case-card-header">
            <div>
              <div class="case-card-title">${escapeHtml(c.case_name || c.file_name || 'Untitled Case')}</div>
            </div>
            <div class="case-card-badges">
              ${statusBadge}
            </div>
          </div>
          
          <div class="case-card-field">
            <span class="case-card-field-label">Analyst</span>
            <span class="case-card-field-value">${escapeHtml(c.analyst || '—')}</span>
          </div>
          
          <div class="case-card-field">
            <span class="case-card-field-label">IO</span>
            <span class="case-card-field-value">${escapeHtml(c.investigating_officer || '—')}</span>
          </div>
          
          <div class="case-card-field">
            <span class="case-card-field-label">Pertains to</span>
            <span class="case-card-field-value">
              ${c.pertains_name ? escapeHtml(c.pertains_name) : '—'}
            </span>
          </div>
          
          <div class="case-card-field">
            <span class="case-card-field-label">Command</span>
            <span class="case-card-field-value">${escapeHtml(c.command || '—')}</span>
          </div>
          
          <div style="margin-top: 14px; display: flex; justify-content: flex-end; border-top: 1px dashed #2a3441; padding-top: 12px;">
            <a href="${detailUrl}" style="color: #4f9cff; text-decoration: none; font-size: 12px; font-weight: 600; display: inline-flex; align-items: center; gap: 4px; padding: 4px 8px; background: rgba(79, 156, 255, 0.08); border-radius: 4px; border: 1px solid rgba(79, 156, 255, 0.15); transition: all 0.15s ease;" onmouseover="this.style.background='rgba(79,156,255,0.15)'" onmouseout="this.style.background='rgba(79,156,255,0.08)'">
              View Case →
            </a>
          </div>
        </div>
      `;
    }).join("");
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }
});
