// ─── CONFIG ───────────────────────────────────────────────
// Direct relative path approach if on same host, but here we are usually cross-port
// We'll use the current host but swap the port to 5000
const API_BASE = `${window.location.protocol}//${window.location.hostname}:5000/api`;

console.log(`[Config] API_BASE: ${API_BASE}`);

// ─── API CLIENT ───────────────────────────────────────────
const api = {
  async request(method, endpoint, data = null) {
    const token = Auth.getToken();
    console.log(`[API] ${method} ${endpoint} | Token ${token ? 'FOUND' : 'MISSING'}`);

    const headers = { 'Content-Type': 'application/json' };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
      console.log(`[API] Attached Authorization header (Bearer ${token.substring(0, 10)}...)`);
    }

    const opts = {
      method,
      headers,
      credentials: 'include',
    };
    if (data) opts.body = JSON.stringify(data);
    try {
      const res = await fetch(`${API_BASE}${endpoint}`, opts);

      // Global 401 Handling
      if (res.status === 401 && !endpoint.includes('/login') && !endpoint.includes('/signup')) {
        console.warn(`[Auth] 401 Unauthorized at ${endpoint}. Clearing local user & redirecting...`);
        Auth.clearUser();
        // Don't redirect if we're already on an auth page or the home page
        const isAuthPage = ['login.html', 'register.html', 'index.html', '/frontend/'].some(p => window.location.pathname.endsWith(p) || window.location.pathname === '/' || window.location.pathname === '/frontend/index.html');
        if (!isAuthPage) {
          window.location.href = '/frontend/pages/login.html';
        }
      }

      const json = await res.json();
      return { ok: res.ok, status: res.status, data: json };
    } catch (e) {
      console.error(`[API Error] ${method} ${endpoint}:`, e);
      return { ok: false, status: 0, data: { error: 'Network error. Is the backend running?' } };
    }
  },
  get: (ep) => api.request('GET', ep),
  post: (ep, d) => api.request('POST', ep, d),
  put: (ep, d) => api.request('PUT', ep, d),
};

// ─── AUTH HELPERS ─────────────────────────────────────────
const Auth = {
  getUser() {
    try { return JSON.parse(localStorage.getItem('hf_user')); } catch { return null; }
  },
  setUser(u, token) {
    localStorage.setItem('hf_user', JSON.stringify(u));
    if (token) localStorage.setItem('hf_token', token);
  },
  getToken() { return localStorage.getItem('hf_token'); },
  clearUser() {
    console.log('[Auth] Clearing user and token');
    localStorage.removeItem('hf_user');
    localStorage.removeItem('hf_token');
  },
  isLoggedIn() {
    const hasToken = !!this.getToken();
    if (!hasToken && this.getUser()) {
      console.warn('[Auth] User object found but no token. Treating as logged out.');
      this.clearUser();
      return false;
    }
    return hasToken;
  },
  requireAuth() {
    if (!this.isLoggedIn()) { window.location.href = '/frontend/pages/login.html'; return false; }
    return true;
  },
  requireGuest() {
    if (this.isLoggedIn()) { window.location.href = '/frontend/pages/dashboard.html'; }
  },
  async checkSession() {
    const { ok, data } = await api.get('/user');
    if (ok) {
      this.setUser(data.user);
      return true;
    } else {
      this.clearUser();
      return false;
    }
  }
};

// ─── TOAST ────────────────────────────────────────────────
function showToast(msg, type = 'success', duration = 3500) {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span class="toast-icon">${icon}</span><span class="toast-msg">${msg}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = 'slideInRight 0.4s reverse';
    setTimeout(() => toast.remove(), 380);
  }, duration);
}

// ─── NAVBAR SETUP ─────────────────────────────────────────
function initNavbar() {
  const user = Auth.getUser();
  const navActions = document.querySelector('.nav-actions');
  if (!navActions) return;

  if (user) {
    const initials = user.name ? user.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2) : 'U';
    navActions.innerHTML = `
      <div class="profile-menu">
        <div class="profile-avatar" id="avatarBtn">${initials}</div>
        <div class="dropdown-menu" id="dropdownMenu">
          <a href="/frontend/pages/dashboard.html">🏠 Dashboard</a>
          <a href="/frontend/pages/profile.html">👤 Profile</a>
          <a href="/frontend/pages/bmi.html">📊 BMI Calculator</a>
          <a href="/frontend/pages/premium.html">⭐ Premium</a>
          <div class="dropdown-divider"></div>
          <a href="#" id="logoutBtn">🚪 Logout</a>
        </div>
      </div>`;
    document.getElementById('avatarBtn').addEventListener('click', (e) => {
      e.stopPropagation();
      document.getElementById('dropdownMenu').classList.toggle('open');
    });
    document.addEventListener('click', () => {
      document.getElementById('dropdownMenu')?.classList.remove('open');
    });
    document.getElementById('logoutBtn').addEventListener('click', async (e) => {
      e.preventDefault();
      await api.post('/logout');
      Auth.clearUser();
      showToast('Logged out successfully', 'success', 1500);
      setTimeout(() => window.location.href = '/frontend/index.html', 1000);
    });
  } else {
    navActions.innerHTML = `
      <a href="/frontend/pages/login.html" class="btn btn-ghost btn-sm">Login</a>
      <a href="/frontend/pages/register.html" class="btn btn-primary btn-sm">Get Started</a>`;
  }

  // Hamburger
  const ham = document.querySelector('.hamburger');
  const navLinks = document.querySelector('.nav-links');
  if (ham && navLinks) {
    ham.addEventListener('click', () => navLinks.classList.toggle('mobile-open'));
  }
}

// ─── SET ACTIVE NAV LINK ──────────────────────────────────
function setActiveNav() {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-links a, .sidebar-nav a').forEach(a => {
    if (a.href && path.includes(a.getAttribute('href').split('/').pop()?.split('.')[0])) {
      a.classList.add('active');
    }
  });
}

// ─── FORMAT HELPERS ───────────────────────────────────────
const fmt = {
  date: (d) => new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
  round: (n, dec = 1) => Math.round(n * Math.pow(10, dec)) / Math.pow(10, dec),
};

// ─── HEALTH SCORE CALCULATOR ──────────────────────────────
function calcHealthScore(data) {
  let score = 0;
  const waterGoal = 8, stepsGoal = 10000, sleepGoal = 8;
  if (data.water) score += Math.min((data.water / waterGoal) * 25, 25);
  if (data.steps) score += Math.min((data.steps / stepsGoal) * 30, 30);
  if (data.sleep) score += Math.min((data.sleep / sleepGoal) * 20, 20);
  if (data.mood) score += (data.mood / 5) * 15;
  if (data.weight) score += 10;
  return Math.round(score);
}

function getScoreGrade(score) {
  if (score >= 85) return { label: 'Excellent 🏆', color: 'var(--lime-300)' };
  if (score >= 70) return { label: 'Great 💪', color: 'var(--teal-300)' };
  if (score >= 50) return { label: 'Good 👍', color: 'var(--amber-400)' };
  return { label: 'Keep Going 🌱', color: 'var(--coral-400)' };
}

// ─── BMI CALCULATOR ───────────────────────────────────────
function calcBMI(weightKg, heightCm) {
  const h = heightCm / 100;
  return fmt.round(weightKg / (h * h));
}

function getBMICategory(bmi) {
  if (bmi < 18.5) return { label: 'Underweight', color: 'var(--teal-300)', bg: 'rgba(43,163,181,0.12)' };
  if (bmi < 25) return { label: 'Normal weight', color: 'var(--lime-300)', bg: 'rgba(163,230,53,0.12)' };
  if (bmi < 30) return { label: 'Overweight', color: 'var(--amber-400)', bg: 'rgba(251,191,36,0.12)' };
  return { label: 'Obese', color: 'var(--coral-400)', bg: 'rgba(251,113,133,0.12)' };
}

// ─── WEEKLY CHART ─────────────────────────────────────────
function renderWeeklyChart(weeklyData) {
  const chart = document.getElementById('weeklyChart');
  if (!chart) return;
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const maxSteps = Math.max(...weeklyData.map(d => d.steps || 0), 1);
  chart.innerHTML = days.map((day, i) => {
    const d = weeklyData[i] || {};
    const h = Math.max(((d.steps || 0) / maxSteps) * 100, 4);
    return `
      <div class="bar-group">
        <div class="bar-wrap">
          <div class="bar" style="height:${h}px" title="${d.steps || 0} steps on ${day}"></div>
        </div>
        <span class="bar-day">${day}</span>
      </div>`;
  }).join('');
}

// ─── WATER CUPS ───────────────────────────────────────────
function renderWaterCups(filled = 0) {
  const container = document.getElementById('waterCups');
  if (!container) return;
  container.innerHTML = '';
  for (let i = 0; i < 8; i++) {
    const cup = document.createElement('div');
    cup.className = `water-cup ${i < filled ? 'filled' : ''}`;
    cup.title = `${i + 1} glass${i > 0 ? 'es' : ''}`;
    cup.addEventListener('click', () => {
      const newFilled = i + 1 === filled ? i : i + 1;
      renderWaterCups(newFilled);
      const inp = document.getElementById('waterInput');
      if (inp) inp.value = newFilled;
    });
    container.appendChild(cup);
  }
}

// ─── INIT ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initNavbar();
  setActiveNav();
});
