/* ============================================
   NovelNest — Client JS
   ============================================ */

document.addEventListener('DOMContentLoaded', () => {
  initNavbarToggle();
  initAvatarMenu();
  initThemeToggle();
  initFlashAutoDismiss();

  // Page-scoped initializers
  if (document.querySelector('.tab-btn')) {
    initTabs();
  }
  if (document.querySelector('.genre-tag')) {
    initGenreFilter();
  }
  if (document.querySelector('#activity-table') || document.querySelector('#audit-table')) {
    initTableFilters();
    initAdminUX();
    initStatCounters();
  }
  if (document.querySelector('.book-grid')) {
    enhanceBookGrids(document);
  }
});

function initNavbarToggle() {
  const nav = document.getElementById('navbar');
  const toggle = document.getElementById('nav-toggle');
  if (!nav || !toggle) return;
  toggle.addEventListener('click', () => {
    nav.classList.toggle('navbar--open');
  });
}

/* ---------- Tab Switching ---------- */
function initTabs() {
  const buttons = document.querySelectorAll('.tab-btn');
  const panels  = document.querySelectorAll('.tab-panel');

  if (!buttons.length) return;

  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.tab;

      buttons.forEach(b => b.classList.remove('active'));
      panels.forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const panel = document.getElementById('tab-' + target);
      if (panel) {
        panel.classList.add('active');

        // Lazy-load content if panel is empty and has a data-url
        if (panel.dataset.url && !panel.dataset.loaded) {
          loadTabContent(panel);
        }
      }
    });
  });

  // Activate first tab
  if (buttons[0]) buttons[0].click();
}

function loadTabContent(panel) {
  panel.innerHTML = `
    <div class="skeleton-grid">
      <div class="skeleton-card"></div>
      <div class="skeleton-card"></div>
      <div class="skeleton-card"></div>
      <div class="skeleton-card"></div>
      <div class="skeleton-card"></div>
      <div class="skeleton-card"></div>
    </div>
  `;

  fetch(panel.dataset.url)
    .then(res => res.text())
    .then(html => {
      panel.innerHTML = html;
      panel.dataset.loaded = '1';
      panel.classList.add('fade-in');
      enhanceBookGrids(panel);
    })
    .catch(() => {
      panel.innerHTML = '<div class="alert alert--error">Failed to load. Please refresh.</div>';
    });
}

function enhanceBookGrids(scope = document) {
  const grids = scope.querySelectorAll('.book-grid');
  grids.forEach((grid) => {
    if (grid.dataset.enhanced) return;
    grid.dataset.enhanced = '1';
    grid.classList.add('carousel-track');
    const shell = document.createElement('div');
    shell.className = 'carousel-shell';
    grid.parentNode.insertBefore(shell, grid);
    shell.appendChild(grid);

    const prev = document.createElement('button');
    prev.className = 'carousel-nav carousel-nav--prev';
    prev.textContent = '‹';
    prev.type = 'button';
    const next = document.createElement('button');
    next.className = 'carousel-nav carousel-nav--next';
    next.textContent = '›';
    next.type = 'button';
    shell.appendChild(prev);
    shell.appendChild(next);

    prev.addEventListener('click', () => grid.scrollBy({ left: -420, behavior: 'smooth' }));
    next.addEventListener('click', () => grid.scrollBy({ left: 420, behavior: 'smooth' }));
  });
}

/* ---------- Genre Filter ---------- */
function initGenreFilter() {
  document.querySelectorAll('.genre-tag').forEach(tag => {
    tag.addEventListener('click', () => {
      tag.classList.toggle('active');
    });
  });
}

function initAvatarMenu() {
  const btn = document.getElementById('avatar-btn');
  const menu = document.getElementById('avatar-dropdown');
  if (!btn || !menu) return;
  btn.addEventListener('click', () => menu.classList.toggle('open'));
  document.addEventListener('click', (e) => {
    if (!menu.contains(e.target) && e.target !== btn) menu.classList.remove('open');
  });
}

function initThemeToggle() {
  const toggle = document.getElementById('theme-toggle');
  if (!toggle) return;
  const stored = localStorage.getItem('novelnest-theme');
  if (stored) {
    document.body.setAttribute('data-theme', stored);
    toggle.textContent = stored === 'light' ? '🌞' : '🌙';
  }
  toggle.addEventListener('click', () => {
    const next = document.body.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    document.body.setAttribute('data-theme', next);
    localStorage.setItem('novelnest-theme', next);
    toggle.textContent = next === 'light' ? '🌞' : '🌙';
  });
}

function initTableFilters() {
  bindTableSearch('activity-search', 'activity-table');
  bindTableSearch('audit-search', 'audit-table');
}

function bindTableSearch(inputId, tableId) {
  const input = document.getElementById(inputId);
  const table = document.getElementById(tableId);
  if (!input || !table) return;
  input.addEventListener('input', () => {
    const q = input.value.toLowerCase().trim();
    table.querySelectorAll('tbody tr').forEach((tr) => {
      const txt = tr.textContent.toLowerCase();
      tr.style.display = txt.includes(q) ? '' : 'none';
    });
  });
}

function initAdminUX() {
  document.querySelectorAll('.js-confirm-form').forEach((form) => {
    form.addEventListener('submit', (e) => {
      const msg = form.dataset.confirm || 'Are you sure?';
      if (!window.confirm(msg)) e.preventDefault();
    });
  });

  document.querySelectorAll('.js-admin-save-form').forEach((form) => {
    form.addEventListener('submit', () => {
      const btn = form.querySelector('.js-save-btn');
      if (btn) {
        btn.disabled = true;
        btn.textContent = 'Saving...';
      }
    });
  });
}

function initStatCounters() {
  const counters = document.querySelectorAll('[data-counter]');
  counters.forEach((el) => {
    const target = Number(el.dataset.counter || 0);
    if (!Number.isFinite(target)) return;
    const duration = 550;
    const start = performance.now();
    const tick = (now) => {
      const p = Math.min((now - start) / duration, 1);
      el.textContent = Math.floor(target * p).toLocaleString();
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}

function initFlashAutoDismiss() {
  const wraps = document.querySelectorAll('.flash-messages .alert');
  wraps.forEach((alertEl, idx) => {
    setTimeout(() => {
      alertEl.style.opacity = '0';
      alertEl.style.transform = 'translateY(-6px)';
      setTimeout(() => alertEl.remove(), 250);
    }, 3200 + idx * 220);
  });
}
