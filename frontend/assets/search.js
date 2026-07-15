document.addEventListener("DOMContentLoaded", () => {
  const runSearchBtn = document.getElementById("runSearchBtn");
  const addFilterBtn = document.getElementById("addFilterBtn");
  const queryBuilderContainer = document.getElementById("queryBuilderContainer");
  const casesGrid = document.getElementById("casesGrid");
  const searchEmptyState = document.getElementById("searchEmptyState");
  const resultsCountBadge = document.getElementById("resultsCountBadge");

  let searchMetadataOptions = null;
  let currentPage = 1;
  let lastFilters = null;
  let lastHighlightTerm = "";

  function getActiveFilters() {
    const rows = document.querySelectorAll(".filter-row");
    const filters = [];
    const dropdownCats = ["incident_type", "command", "analyst", "investigating_officer", "dates"];
    
    rows.forEach(row => {
      const cat = row.querySelector(".searchCategory").value;
      const termInput = row.querySelector(".searchTermInput");
      const termSelect = row.querySelector(".searchTermSelect");
      
      if (cat === "confirmed_pio") {
        filters.push({ category: cat, term: "true" });
        return;
      }
      
      let term = "";
      if (dropdownCats.includes(cat) && termSelect.style.display !== "none") {
        term = termSelect.value;
      } else {
        term = termInput.value.trim();
      }
      
      if (term) {
        filters.push({ category: cat, term: term });
      }
    });
    return filters;
  }

  async function fetchSearchOptions(year = null, filters = null) {
    try {
      let url = "/cases/search/options";
      const params = new URLSearchParams();
      if (year && year !== "all") {
        params.append("year", year);
      }
      if (filters && filters.length > 0) {
        params.append("filters", JSON.stringify(filters));
      }
      if (params.toString()) {
        url += "?" + params.toString();
      }
      const response = await apiFetch(url);
      if (response && response.ok) {
        searchMetadataOptions = await response.json();
        
        const searchYear = document.querySelector(".searchYear");
        if (searchYear && searchMetadataOptions.years && searchMetadataOptions.years.length > 0 && searchYear.options.length <= 1) {
          searchMetadataOptions.years.forEach(y => {
            const opt = document.createElement("option");
            opt.value = y;
            opt.textContent = y;
            searchYear.appendChild(opt);
          });
        }
        
        const initialRow = document.querySelector(".filter-row");
        if (initialRow) {
          populateRowDropdown(initialRow, initialRow.querySelector(".searchCategory").value);
          
          const urlParams = new URLSearchParams(window.location.search);
          const q = urlParams.get('q');
          const urlYear = urlParams.get('year');
          
          if (urlYear && searchYear) {
            searchYear.value = urlYear;
          }

          if (q) {
            const input = initialRow.querySelector(".searchTermInput");
            if (input) {
              input.value = q;
              if (runSearchBtn) setTimeout(() => runSearchBtn.click(), 100);
            }
          }
        }
      }
    } catch (e) {
      console.error("Failed to load search options", e);
    }
  }
  
  const globalSearchYear = document.querySelector(".searchYear");
  if (globalSearchYear) {
    globalSearchYear.addEventListener("change", async (e) => {
      await fetchSearchOptions(e.target.value, getActiveFilters());
      // Re-populate all visible dropdowns
      document.querySelectorAll(".filter-row").forEach(row => {
         const cat = row.querySelector(".searchCategory").value;
         populateRowDropdown(row, cat);
      });
    });
  }

  fetchSearchOptions();

  function populateRowDropdown(row, cat) {
    const termInput = row.querySelector(".searchTermInput");
    const termSelect = row.querySelector(".searchTermSelect");
    const currentValue = termSelect.value;
    
    const globalYearEl = document.querySelector(".searchYear");
    const year = globalYearEl ? globalYearEl.value : "all";
    
    const dropdownCats = ["incident_type", "command", "analyst", "investigating_officer", "dates"];
    
    if (dropdownCats.includes(cat) && searchMetadataOptions) {
      termInput.style.display = "none";
      termSelect.style.display = "block";
      
      termSelect.innerHTML = "";
      let optionsList = searchMetadataOptions[cat] || [];
      
      if (cat === "dates") {
        optionsList.sort((a, b) => {
          const dateA = new Date(a);
          const dateB = new Date(b);
          if (!isNaN(dateA) && !isNaN(dateB)) {
            return dateB - dateA;
          }
          return 0;
        });
      }
      
      if (optionsList.length === 0) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "-- No options available --";
        termSelect.appendChild(opt);
      } else {
        // Always add an empty "Select..." option for faceted search
        const defaultOpt = document.createElement("option");
        defaultOpt.value = "";
        defaultOpt.textContent = "-- Select --";
        termSelect.appendChild(defaultOpt);

        optionsList.forEach(val => {
          const opt = document.createElement("option");
          opt.value = val;
          opt.textContent = val;
          termSelect.appendChild(opt);
        });
        
        // Restore value if it exists
        if (currentValue && Array.from(termSelect.options).some(opt => opt.value === currentValue)) {
            termSelect.value = currentValue;
        }
      }
    } else if (cat === "confirmed_pio") {
      termInput.style.display = "none";
      termSelect.style.display = "none";
    } else {
      termInput.style.display = "block";
      termSelect.style.display = "none";
    }
  }

  function attachRowEvents(row) {
    const catSelect = row.querySelector(".searchCategory");
    const removeBtn = row.querySelector(".remove-row-btn");
    const searchInput = row.querySelector(".searchTermInput");
    const termSelect = row.querySelector(".searchTermSelect");
    
    catSelect.addEventListener("change", (e) => {
      populateRowDropdown(row, e.target.value);
    });
    
    if (termSelect) {
        termSelect.addEventListener("change", async () => {
            const year = document.querySelector(".searchYear") ? document.querySelector(".searchYear").value : null;
            await fetchSearchOptions(year, getActiveFilters());
            document.querySelectorAll(".filter-row").forEach(r => {
               if (r !== row) { // Repopulate other rows
                   const cat = r.querySelector(".searchCategory").value;
                   populateRowDropdown(r, cat);
               }
            });
        });
    }
    
    if (removeBtn) {
        removeBtn.addEventListener("click", async () => {
            row.remove();
            const year = document.querySelector(".searchYear") ? document.querySelector(".searchYear").value : null;
            await fetchSearchOptions(year, getActiveFilters());
            document.querySelectorAll(".filter-row").forEach(r => {
               const cat = r.querySelector(".searchCategory").value;
               populateRowDropdown(r, cat);
            });
        });
    }
    
    if (searchInput) {
        searchInput.addEventListener("keypress", (e) => {
            if (e.key === "Enter") triggerSearch();
        });
    }
  }

  const initialRow = document.querySelector(".filter-row");
  if (initialRow) attachRowEvents(initialRow);

  const globalYearEl = document.querySelector(".searchYear");
  if (globalYearEl) {
    globalYearEl.addEventListener("change", () => {
      document.querySelectorAll(".filter-row").forEach(row => {
        populateRowDropdown(row, row.querySelector(".searchCategory").value);
      });
    });
  }

  if (addFilterBtn) {
    addFilterBtn.addEventListener("click", () => {
      const newRow = document.createElement("div");
      newRow.className = "filter-row";
      newRow.style = initialRow.getAttribute("style"); 
      
      newRow.innerHTML = `
        <select class="searchCategory" style="padding: 16px 20px; background: rgba(42, 52, 65, 0.4); border: none; border-right: 1px solid #2a3441; color: #e8eaed; font-size: 14px; font-weight: 500; outline: none; cursor: pointer; min-width: 250px; appearance: none; -webkit-appearance: none; background-image: url('data:image/svg+xml;utf8,<svg fill=\'%238a93a3\' height=\'24\' viewBox=\'0 0 24 24\' width=\'24\' xmlns=\'http://www.w3.org/2000/svg\'><path d=\'M7 10l5 5 5-5z\'/></svg>'); background-repeat: no-repeat; background-position: right 10px center;">
            <option value="case_name">Case Number (Folder Name)</option>
            <option value="incident_type">Type of Case</option>
            <option value="command">Military Command</option>
            <option value="analyst">Analyst Name</option>
            <option value="investigating_officer">Investigating Officer</option>
            <option value="pertains">Case Pertains To</option>
            <option value="dates">Key Dates</option>
            <option value="confirmed_pio">Confirmed PIO Only</option>
            <option value="random">Global Text Search</option>
        </select>
        <input type="text" class="searchTermInput" placeholder="Enter search term or keyword..." style="flex: 1; padding: 16px 20px; background: transparent; border: none; color: #ffffff; font-size: 16px; outline: none; width: 100%;" onfocus="this.parentElement.style.borderColor='#4f9cff'; this.parentElement.style.boxShadow='0 0 0 1px #4f9cff, 0 8px 30px rgba(79,156,255,0.15)';" onblur="this.parentElement.style.borderColor='#2a3441'; this.parentElement.style.boxShadow='0 8px 24px rgba(0,0,0,0.4)';">
        <select class="searchTermSelect" style="display: none; flex: 1; padding: 16px 20px; background: transparent; border: none; color: #ffffff; font-size: 16px; outline: none; width: 100%; cursor: pointer; appearance: none; -webkit-appearance: none; background-image: url('data:image/svg+xml;utf8,<svg fill=\'%23ffffff\' height=\'24\' viewBox=\'0 0 24 24\' width=\'24\' xmlns=\'http://www.w3.org/2000/svg\'><path d=\'M7 10l5 5 5-5z\'/></svg>'); background-repeat: no-repeat; background-position: right 10px center;" onfocus="this.parentElement.style.borderColor='#4f9cff'; this.parentElement.style.boxShadow='0 0 0 1px #4f9cff, 0 8px 30px rgba(79,156,255,0.15)';" onblur="this.parentElement.style.borderColor='#2a3441'; this.parentElement.style.boxShadow='0 8px 24px rgba(0,0,0,0.4)';"></select>
        <button class="remove-row-btn" style="background: rgba(255, 79, 79, 0.05); border: none; border-left: 1px solid #2a3441; color: #ff4f4f; padding: 0 20px; cursor: pointer; font-size: 16px; transition: background 0.2s ease;" onmouseover="this.style.background='rgba(255, 79, 79, 0.2)'" onmouseout="this.style.background='rgba(255, 79, 79, 0.05)'" title="Remove Filter">✕</button>
      `;
      queryBuilderContainer.appendChild(newRow);
      attachRowEvents(newRow);
      populateRowDropdown(newRow, "case_name");
    });
  }

  const clearFiltersBtn = document.getElementById("clearFiltersBtn");
  if (clearFiltersBtn) {
    clearFiltersBtn.addEventListener("click", () => {
      // Remove dynamically added rows
      const rows = document.querySelectorAll(".filter-row");
      for (let i = 1; i < rows.length; i++) {
        rows[i].remove();
      }
      
      // Reset first row
      const firstRow = document.querySelector(".filter-row");
      if (firstRow) {
        const catSelect = firstRow.querySelector(".searchCategory");
        catSelect.value = "random";
        populateRowDropdown(firstRow, "random");
        
        const termInput = firstRow.querySelector(".searchTermInput");
        termInput.value = "";
      }
      
      // Reset year dropdown
      if (globalYearEl) {
        globalYearEl.value = "all";
      }
      
      // Clear results
      casesGrid.innerHTML = "";
      resultsCountBadge.style.display = "none";
      searchEmptyState.style.display = "block";
      searchEmptyState.innerHTML = `
        <div style="font-size: 48px; margin-bottom: 12px; filter: grayscale(1);">🔍</div>
        <h4 style="color: #e8eaed; font-size: 16px; margin-bottom: 6px;">Ready to Search</h4>
        <p style="font-size: 13px; max-width: 400px; margin: 0 auto;">Select a category and type a search term above, then click search to view matching cases.</p>
      `;
    });
  }

  if (runSearchBtn) {
    runSearchBtn.addEventListener("click", triggerSearch);
  }

  async function triggerSearch() {
    const filters = getActiveFilters();

    if (filters.length === 0) {
      alert("Please enter or select at least one search query term.");
      return;
    }

    const year = globalYearEl ? globalYearEl.value : "all";

    runSearchBtn.disabled = true;
    runSearchBtn.textContent = "Searching...";
    casesGrid.innerHTML = "";
    searchEmptyState.style.display = "none";
    resultsCountBadge.style.display = "none";

    // Determine the best term to highlight (prefer global text search)
    let highlightTerm = "";
    const textFilter = filters.find(f => f.category === "random" || f.category === "case_name");
    if (textFilter) {
        highlightTerm = textFilter.term;
    } else if (filters.length > 0) {
        highlightTerm = filters[0].term;
    }

    // Save for pagination
    lastFilters = filters;
    lastHighlightTerm = highlightTerm;
    currentPage = 1;

    await fetchPage(1, filters, year, highlightTerm);
  }

  async function fetchPage(page, filters, year, highlightTerm) {
    runSearchBtn.disabled = true;
    runSearchBtn.textContent = "Searching...";
    if (page === 1) {
      casesGrid.innerHTML = "";
      searchEmptyState.style.display = "none";
      resultsCountBadge.style.display = "none";
    }

    try {
      const params = new URLSearchParams();
      if (year && year !== "all") params.append("year", year);
      params.append("filters", JSON.stringify(filters));
      params.append("page", page);
      params.append("page_size", 20);

      const response = await apiFetch(`/cases/search/advanced?${params.toString()}`);
      if (!response) return;
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Failed to query database.");
      }

      const data = await response.json();
      currentPage = data.page;
      displayResults(data, highlightTerm);
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

  function displayResults(data, term) {
    const cases = data.cases || data;
    const total = data.total || cases.length;
    const page = data.page || 1;
    const totalPages = data.total_pages || 1;

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
    resultsCountBadge.textContent = `${total} case${total !== 1 ? 's' : ''} found`;
    resultsCountBadge.style.display = "inline-block";
    searchEmptyState.style.display = "none";

    casesGrid.innerHTML = cases.map(c => {
      const detailUrl = `case-detail.html?id=${c.id}&v=1.9${term ? '&search=' + encodeURIComponent(term) : ''}`;
      
      const statusBadge = "";

      const hitsBadge = (term && c.hit_count !== undefined && c.hit_count > 0)
        ? `<span class="badge" style="background: rgba(79, 156, 255, 0.15); color: #4f9cff; border: 1px solid rgba(79, 156, 255, 0.3); font-weight: 700; border-radius: 12px; padding: 2px 8px; font-size: 10px; text-transform: uppercase;">${c.hit_count} Hits</span>`
        : '';

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
        <div class="case-card" onclick="window.location.href='${detailUrl}'" style="cursor: pointer;">
          <div class="case-card-header">
            <div>
              <div class="case-card-title">${escapeHtml(c.case_name || c.file_name || 'Untitled Case')}</div>
            </div>
            <div class="case-card-badges" style="display: flex; gap: 6px; align-items: center;">
              ${hitsBadge}
              ${statusBadge}
            </div>
          </div>
          
          <div class="case-card-field">
            <span class="case-card-field-label">IO</span>
            <span class="case-card-field-value">${escapeHtml(c.investigating_officer || '—')}</span>
          </div>
          
          <div class="case-card-field">
            <span class="case-card-field-label">Analyst</span>
            <span class="case-card-field-value">${escapeHtml(c.analyst || '—')}</span>
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
          
          ${matchedFilesHtml}
          
          <div style="margin-top: 14px; display: flex; justify-content: flex-end; border-top: 1px dashed #2a3441; padding-top: 12px;">
            <a href="${detailUrl}" style="color: #4f9cff; text-decoration: none; font-size: 12px; font-weight: 600; display: inline-flex; align-items: center; gap: 4px; padding: 4px 8px; background: rgba(79, 156, 255, 0.08); border-radius: 4px; border: 1px solid rgba(79, 156, 255, 0.15); transition: all 0.15s ease;" onmouseover="this.style.background='rgba(79,156,255,0.15)'" onmouseout="this.style.background='rgba(79,156,255,0.08)'">
              View Case →
            </a>
          </div>
        </div>
      `;
    }).join("");

    // Add pagination controls if needed
    if (totalPages > 1) {
      const paginationHtml = `
        <div style="grid-column: 1 / -1; display: flex; justify-content: center; align-items: center; gap: 16px; padding: 24px 0 8px;">
          <button onclick="window.__searchPrevPage()" ${page <= 1 ? 'disabled' : ''}
            style="padding: 8px 18px; border-radius: 6px; border: 1px solid ${page <= 1 ? '#2a3441' : 'rgba(79, 156, 255, 0.4)'}; background: ${page <= 1 ? 'transparent' : 'rgba(79, 156, 255, 0.1)'}; color: ${page <= 1 ? '#555' : '#4f9cff'}; cursor: ${page <= 1 ? 'not-allowed' : 'pointer'}; font-weight: 600; font-size: 13px; transition: all 0.15s ease;">
            ◀ Previous
          </button>
          <span style="color: #8a93a3; font-size: 13px; font-weight: 500;">Page ${page} of ${totalPages}</span>
          <button onclick="window.__searchNextPage()" ${page >= totalPages ? 'disabled' : ''}
            style="padding: 8px 18px; border-radius: 6px; border: 1px solid ${page >= totalPages ? '#2a3441' : 'rgba(79, 156, 255, 0.4)'}; background: ${page >= totalPages ? 'transparent' : 'rgba(79, 156, 255, 0.1)'}; color: ${page >= totalPages ? '#555' : '#4f9cff'}; cursor: ${page >= totalPages ? 'not-allowed' : 'pointer'}; font-weight: 600; font-size: 13px; transition: all 0.15s ease;">
            Next ▶
          </button>
        </div>
      `;
      casesGrid.innerHTML += paginationHtml;
    }
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  // Global pagination handlers (called from onclick in pagination buttons)
  window.__searchPrevPage = function() {
    if (currentPage > 1 && lastFilters) {
      const year = document.querySelector(".searchYear")?.value || "all";
      fetchPage(currentPage - 1, lastFilters, year, lastHighlightTerm);
    }
  };
  window.__searchNextPage = function() {
    if (lastFilters) {
      const year = document.querySelector(".searchYear")?.value || "all";
      fetchPage(currentPage + 1, lastFilters, year, lastHighlightTerm);
    }
  };
});
