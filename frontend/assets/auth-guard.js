const API_BASE = "http://127.0.0.1:8000";

// Backward-compatible token getter for scripts referencing window.token or token
Object.defineProperty(window, "token", {
  get: function() {
    return localStorage.getItem("token");
  },
  configurable: true
});

if (!localStorage.getItem("token")) {
  window.location.href = "index.html";
}

document.addEventListener("DOMContentLoaded", () => {
  const username = localStorage.getItem("username");
  const navUsername = document.getElementById("navUsername");
  if (navUsername) navUsername.textContent = username;

  const logoutBtn = document.getElementById("logoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      localStorage.clear();
      window.location.href = "index.html";
    });
  }

  // Check if force password change is required
  if (localStorage.getItem("must_change_password") === "true") {
    const changePasswordBtn = document.getElementById("changePasswordBtn");
    if (changePasswordBtn) {
      setTimeout(() => {
        changePasswordBtn.click();
      }, 300);
    }
  }
});

// Helper for authenticated fetch calls — used by all pages
async function apiFetch(path, options = {}) {
  const currentToken = localStorage.getItem("token");
  if (!currentToken) {
    window.location.href = "index.html";
    return;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.headers || {}),
      "Authorization": `Bearer ${currentToken}`
    }
  });

  if (response.status === 401) {
    localStorage.clear();
    window.location.href = "index.html";
    return;
  }

  return response;
}