const API_BASE = "http://127.0.0.1:8000";

const loginForm = document.getElementById("loginForm");
const errorMsg = document.getElementById("errorMsg");
const loginBtn = document.getElementById("loginBtn");

// If already logged in, skip straight to dashboard
if (localStorage.getItem("token")) {
  window.location.href = "dashboard.html";
}

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;

  errorMsg.classList.remove("show");
  loginBtn.disabled = true;
  loginBtn.textContent = "Signing in...";

  try {
    const formData = new URLSearchParams();
    formData.append("username", username);
    formData.append("password", password);

    const response = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded"
      },
      body: formData
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Login failed");
    }

    // Store token + user info
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("username", data.username);
    localStorage.setItem("role", data.role);

    window.location.href = "dashboard.html";

  } catch (err) {
    errorMsg.textContent = err.message;
    errorMsg.classList.add("show");
    loginBtn.disabled = false;
    loginBtn.textContent = "Sign In";
  }
});