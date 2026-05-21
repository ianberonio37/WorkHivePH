// WorkHive GA4 custom event helpers.
// Loaded after the gtag snippet on every public page (see <head>).
// 6 custom events wired here so the gtag config in <head> stays compact.
//
// All events PDPA-compliant: no PII captured, no email/phone in params.
// IP anonymization is set on the gtag config itself (anonymize_ip: true).

(function () {
  if (typeof window === 'undefined' || typeof window.gtag !== 'function') return;

  // ── 1. signup_form_view — when #join enters the viewport ────────────────
  // Useful for funnel: how many people scrolled to the CTA but did not submit?
  var joinSection = document.querySelector('#join');
  if (joinSection && 'IntersectionObserver' in window) {
    var seen = false;
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting && !seen) {
          seen = true;
          window.gtag('event', 'signup_form_view', {
            event_category: 'engagement',
            page_path: location.pathname,
          });
          observer.disconnect();
        }
      });
    }, { threshold: 0.5 });
    observer.observe(joinSection);
  }

  // ── 2. signup_form_submit — wire to any form with [data-ga4-signup] or
  //     to the join form if it has id=joinForm ───────────────────────────
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form || form.tagName !== 'FORM') return;
    if (form.matches('[data-ga4-signup], #joinForm, form[action*="join"]')) {
      window.gtag('event', 'signup_form_submit', {
        event_category: 'conversion',
        page_path: location.pathname,
      });
    }
  }, true);

  // ── 3. learn_article_read_80pct — only fires on /learn/<slug>/ pages ───
  if (location.pathname.startsWith('/learn/') && location.pathname !== '/learn/') {
    var fired80 = false;
    window.addEventListener('scroll', function () {
      if (fired80) return;
      var doc = document.documentElement;
      var scrolled = (window.scrollY + window.innerHeight) / doc.scrollHeight;
      if (scrolled >= 0.8) {
        fired80 = true;
        window.gtag('event', 'learn_article_read_80pct', {
          event_category: 'engagement',
          page_path: location.pathname,
        });
      }
    }, { passive: true });
  }

  // ── 4. cta_tool_click — clicks on the mid-article tool CTA ─────────────
  // Any <a> pointing to /<tool>.html (root-level WorkHive tool) counts.
  document.addEventListener('click', function (e) {
    var a = e.target.closest('a');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    // Match relative root-level .html (e.g., /logbook.html) but NOT external
    if (/^\/[a-z0-9-]+\.html(\?|#|$)/i.test(href)) {
      window.gtag('event', 'cta_tool_click', {
        event_category: 'conversion',
        tool_path:      href.split('?')[0].split('#')[0],
        page_path:      location.pathname,
      });
    }
  }, true);

  // ── 5. faq_open — <details> elements toggling open ─────────────────────
  document.addEventListener('toggle', function (e) {
    var d = e.target;
    if (!d || d.tagName !== 'DETAILS' || !d.open) return;
    var summary = d.querySelector('summary');
    var label   = summary ? (summary.textContent || '').trim().slice(0, 120) : '(no summary)';
    window.gtag('event', 'faq_open', {
      event_category: 'engagement',
      faq_question:   label,
      page_path:      location.pathname,
    });
  }, true);

  // ── 6. external_link_click — outbound links (Chronicle, Wikipedia, etc) ─
  document.addEventListener('click', function (e) {
    var a = e.target.closest('a');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    if (!/^https?:\/\//i.test(href)) return;
    try {
      var url = new URL(href, location.href);
      if (url.host === location.host) return;
      window.gtag('event', 'external_link_click', {
        event_category: 'engagement',
        link_host:      url.host,
        link_url:       url.href.slice(0, 200),
        page_path:      location.pathname,
      });
    } catch (_) { /* malformed URL, skip */ /* empty-catch-allow: best-effort silent swallow */ }
  }, true);
})();
