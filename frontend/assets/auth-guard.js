const API_BASE = "http://127.0.0.1:8000";

const token = localStorage.getItem("token");
const username = localStorage.getItem("username");

if (!token) {
  window.location.href = "index.html";
}

document.addEventListener("DOMContentLoaded", () => {
  const navUsername = document.getElementById("navUsername");
  if (navUsername) navUsername.textContent = username;

  const logoutBtn = document.getElementById("logoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      localStorage.clear();
      window.location.href = "index.html";
    });
  }
});

// Helper for authenticated fetch calls — used by all pages
async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.headers || {}),
      "Authorization": `Bearer ${token}`
    }
  });

  if (response.status === 401) {
    localStorage.clear();
    window.location.href = "index.html";
    return;
  }

  return response;
}