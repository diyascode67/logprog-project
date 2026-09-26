/* ========================================================================= */
/* Smart Retail - Ultra-Smooth App Core & Full SPA Engine                   */
/* ========================================================================= */

(() => {
  // ── Custom Cursor Engine (Ultra-Smooth 120fps & Zero-Lag) ─────────────────
  const cursor = document.querySelector('.custom-cursor');
  const isFinePointer = window.matchMedia('(pointer: fine)').matches;
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const textFieldSelector = 'textarea, [contenteditable]:not([contenteditable="false"]), input:not([type]), input[type="text"], input[type="search"], input[type="email"], input[type="password"], input[type="tel"], input[type="url"], input[type="number"]';

  if (cursor && isFinePointer && !prefersReducedMotion) {
    let mouseX = -100;
    let mouseY = -100;
    let isText = false;
    let rafId = null;
    let isCursorActive = false;
    let lastTarget = null;

    // Seamless Top-Layer Dialog integration:
    // Move the cursor element into the active <dialog> so it is rendered
    // in the browser's Top Layer above all modal content and backdrops.
    if (typeof HTMLDialogElement !== 'undefined') {
      const origShowModal = HTMLDialogElement.prototype.showModal;
      HTMLDialogElement.prototype.showModal = function() {
        origShowModal.apply(this, arguments);
        try {
          this.appendChild(cursor);
        } catch (e) {}
      };

      const origClose = HTMLDialogElement.prototype.close;
      HTMLDialogElement.prototype.close = function() {
        origClose.apply(this, arguments);
        try {
          if (cursor.parentElement !== document.body) {
            document.body.appendChild(cursor);
          }
        } catch (e) {}
      };

      document.addEventListener('close', (e) => {
        if (e.target instanceof HTMLDialogElement && cursor.parentElement !== document.body) {
          document.body.appendChild(cursor);
        }
      }, true);

      document.addEventListener('cancel', (e) => {
        if (e.target instanceof HTMLDialogElement && cursor.parentElement !== document.body) {
          document.body.appendChild(cursor);
        }
      }, true);
    }

    // Restore last cursor position immediately to prevent ANY default cursor flash
    try {
      const saved = sessionStorage.getItem('sr_cpos');
      if (saved) {
        const [sx, sy] = saved.split(',').map(Number);
        if (!isNaN(sx) && !isNaN(sy)) {
          mouseX = sx;
          mouseY = sy;
          cursor.style.transform = `translate3d(${mouseX - 2.5}px, ${mouseY - 1.5}px, 0)`;
          document.body.classList.add('custom-cursor-enabled');
          isCursorActive = true;
        }
      }
    } catch (e) {}

    const updateCursorDOM = () => {
      const xOffset = isText ? 12 : 2.5;
      const yOffset = isText ? 12 : 1.5;
      cursor.style.transform = `translate3d(${mouseX - xOffset}px, ${mouseY - yOffset}px, 0)`;
      rafId = null;
    };

    const onPointerMove = (e) => {
      if (e.pointerType && e.pointerType !== 'mouse') return;

      mouseX = e.clientX;
      mouseY = e.clientY;

      if (!isCursorActive) {
        document.body.classList.add('custom-cursor-enabled');
        isCursorActive = true;
      }

      // Optimize: Only inspect target when moving over a different element
      if (e.target !== lastTarget) {
        lastTarget = e.target;
        const target = e.target instanceof Element ? e.target : null;
        const nextIsText = Boolean(target?.closest(textFieldSelector));
        if (nextIsText !== isText) {
          isText = nextIsText;
          cursor.classList.toggle('is-text', isText);
        }
      }

      if (!rafId) {
        rafId = requestAnimationFrame(updateCursorDOM);
      }
    };

    // Save position only on unload/pagehide, completely eliminating disk/sessionStorage I/O during mousemove
    window.addEventListener('beforeunload', () => {
      try {
        if (isCursorActive) {
          sessionStorage.setItem('sr_cpos', `${mouseX},${mouseY}`);
        }
      } catch (e) {}
    });

    document.addEventListener('pointermove', onPointerMove, { passive: true });
    document.addEventListener('pointerdown', () => cursor.classList.add('is-pressed'));
    document.addEventListener('pointerup', () => cursor.classList.remove('is-pressed'));
    document.addEventListener('pointerleave', () => {
      document.body.classList.remove('custom-cursor-enabled');
      isCursorActive = false;
    });
  }

  // ── Mobile Sidebar: close when tapping outside ───────────────────────────
  (function initMobileSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    document.addEventListener('pointerdown', (e) => {
      if (sidebar.classList.contains('open') && !sidebar.contains(e.target)) {
        sidebar.classList.remove('open');
      }
    }, { passive: true });
  })();

  function initMotion() {
    // Pure CSS page transitions are now used on .main-body for zero layout-thrashing
  }

  // ── Password Visibility Toggles ─────────────────────────────────────────
  function initPasswordToggles() {
    document.querySelectorAll('[data-password-toggle]').forEach((toggle) => {
      const field = document.getElementById(toggle.dataset.passwordToggle);
      if (!field || toggle.__hasToggleListener) return;
      toggle.__hasToggleListener = true;

      toggle.addEventListener('click', () => {
        const isVisible = field.type === 'text';
        field.type = isVisible ? 'password' : 'text';
        toggle.setAttribute('aria-label', isVisible ? 'Tampilkan kata sandi' : 'Sembunyikan kata sandi');
        toggle.classList.toggle('is-visible', !isVisible);
        field.focus();
      });
    });
  }

  // ── Component Initializer on Each View Change ───────────────────────────
  function initPageComponents() {
    initMotion();
    initPasswordToggles();

    // Initialize POS if on Kasir page
    if (document.querySelector('#pos-config') && typeof window.initPos === 'function') {
      window.initPos();
    }
  }

  // ── Core DOM Swapper for Dynamic SPA Navigation ──────────────────────────
  function applyHtmlToDoc(html, targetUrl, push = true) {
    const parser = new DOMParser();
    const nextDoc = parser.parseFromString(html, 'text/html');

    // Update document title
    document.title = nextDoc.title;

    // Update active nav links in sidebar
    const navLinks = document.querySelectorAll('.sidebar .nav-link');
    const targetPath = new URL(targetUrl, window.location.origin).pathname;

    navLinks.forEach((link) => {
      const linkPath = new URL(link.href, window.location.origin).pathname;
      link.classList.toggle('active', linkPath === targetPath);
    });

    // Swap Topbar Title & Actions
    const curTitle = document.querySelector('.topbar-title-group');
    const nextTitle = nextDoc.querySelector('.topbar-title-group');
    if (curTitle && nextTitle) curTitle.innerHTML = nextTitle.innerHTML;

    const curActions = document.querySelector('.topbar-actions');
    const nextActions = nextDoc.querySelector('.topbar-actions');
    if (curActions && nextActions) curActions.innerHTML = nextActions.innerHTML;

    // Swap Flash Messages
    const curFlash = document.querySelector('.flash-area');
    const nextFlash = nextDoc.querySelector('.flash-area');
    if (curFlash && nextFlash) {
      curFlash.innerHTML = nextFlash.innerHTML;
    } else if (curFlash && !nextFlash) {
      curFlash.innerHTML = '';
    }

    // Swap Main Body Content
    const curBody = document.querySelector('.main-body');
    const nextBody = nextDoc.querySelector('.main-body');
    if (curBody && nextBody) curBody.innerHTML = nextBody.innerHTML;

    // Close any open mobile drawer
    const sidebar = document.getElementById('sidebar');
    if (sidebar) sidebar.classList.remove('open');

    if (push) {
      history.pushState({ url: targetUrl }, '', targetUrl);
    }

    // Instant top scroll without jerky bounce
    window.scrollTo({ top: 0, behavior: 'instant' });

    // Re-initialize view components
    initPageComponents();
  }

  // ── Instant SPA Navigation Router ───────────────────────────────────────
  async function navigate(url, push = true) {
    try {
      const response = await fetch(url, {
        headers: { 'X-Requested-With': 'SPA' }
      });

      if (!response.ok) {
        window.location.href = url;
        return;
      }

      const html = await response.text();
      applyHtmlToDoc(html, response.url || url, push);
    } catch (err) {
      window.location.href = url;
    }
  }

  // Expose globally so buttons or scripts can trigger smooth SPA transitions
  window.__spaNavigate = navigate;

  // Intercept all internal navigation link clicks
  document.addEventListener('click', (event) => {
    // Only primary left clicks without modifier keys
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    // Skip if already prevented by a child element's onclick
    if (event.defaultPrevented) return;

    const anchor = event.target.closest('a');
    if (!anchor || !anchor.href) return;

    // Skip downloads, in-page hash anchors, new-tab
    if (anchor.hasAttribute('download')) return;
    if (anchor.target === '_blank') return;
    if (anchor.getAttribute('href')?.startsWith('#')) return;

    const url = new URL(anchor.href, window.location.origin);
    // Only same-origin internal links
    if (url.origin !== window.location.origin) return;
    // Exclude auth endpoints (must do full reload for cookie/session changes)
    if (url.pathname === '/login' || url.pathname === '/logout') return;

    event.preventDefault();
    if (url.href !== window.location.href) {
      // Tutup semua open <dialog> sebelum navigasi agar tidak ada visual sisa modal
      document.querySelectorAll('dialog[open]').forEach((d) => d.close());
      navigate(url.href, true);
    }
  });

  // Intercept all in-app HTML form submissions dynamically
  document.addEventListener('submit', async (event) => {
    const form = event.target;
    // Skip if already handled by JS (event.preventDefault already called)
    if (event.defaultPrevented) return;
    // Skip native <dialog> forms
    if (form.method?.toLowerCase() === 'dialog') return;
    // Skip forms marked as non-spa
    if (form.dataset.spa === 'false') return;

    const actionUrl = new URL(form.action || window.location.href, window.location.origin);
    if (actionUrl.origin !== window.location.origin) return;
    if (actionUrl.pathname === '/login' || actionUrl.pathname === '/logout') return;

    event.preventDefault();

    try {
      let fetchUrl = actionUrl.href;
      const fetchOptions = { headers: { 'X-Requested-With': 'SPA' } };

      if (form.method?.toLowerCase() === 'post') {
        fetchOptions.method = 'POST';
        fetchOptions.body = new FormData(form);
      } else {
        const params = new URLSearchParams(new FormData(form)).toString();
        fetchUrl = actionUrl.pathname + (params ? '?' + params : '');
      }

      const response = await fetch(fetchUrl, fetchOptions);
      const targetUrl = response.url || fetchUrl;
      const html = await response.text();
      applyHtmlToDoc(html, targetUrl, true);
    } catch (err) {
      form.submit();
    }
  });

  // Browser Back / Forward support
  window.addEventListener('popstate', () => {
    navigate(window.location.href, false);
  });

  // Initial execution
  initPageComponents();
})();
