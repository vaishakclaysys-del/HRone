/* Shared helpers for HR Hackathon MVP UI */
(function () {
  "use strict";

  /* --- Sidebar active link highlighting (defensive: server may also set it) */
  function markActiveSidebar() {
    var path = window.location.pathname.replace(/\/+$/, "") || "/";
    var links = document.querySelectorAll(".sidebar-nav a[href]");
    links.forEach(function (a) {
      var href = a.getAttribute("href").replace(/\/+$/, "") || "/";
      if (href === path) a.classList.add("is-active");
    });
  }

  /* --- Generic modal helpers via [data-modal-open] / [data-modal-close]    */
  function bindModals() {
    document.querySelectorAll("[data-modal-open]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var sel = btn.getAttribute("data-modal-open");
        var modal = document.querySelector(sel);
        if (modal) modal.classList.add("is-active");
      });
    });
    document.querySelectorAll("[data-modal-close]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var modal = btn.closest(".modal-overlay");
        if (modal) modal.classList.remove("is-active");
      });
    });
    document.querySelectorAll(".modal-overlay").forEach(function (overlay) {
      overlay.addEventListener("click", function (e) {
        if (e.target === overlay) overlay.classList.remove("is-active");
      });
    });
  }

  /* --- Copy-to-clipboard via [data-copy-target="#id"] [data-copy-feedback] */
  function bindCopy() {
    document.querySelectorAll("[data-copy-target]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var sel = btn.getAttribute("data-copy-target");
        var node = document.querySelector(sel);
        if (!node) return;
        var text = node.innerText;
        navigator.clipboard.writeText(text).then(function () {
          var feedbackSel = btn.getAttribute("data-copy-feedback");
          if (feedbackSel) {
            var msg = document.querySelector(feedbackSel);
            if (msg) {
              msg.classList.add("is-visible");
              setTimeout(function () { msg.classList.remove("is-visible"); }, 2500);
            }
          } else {
            // Fallback toast
            try { alert("Copied!"); } catch (_e) {}
          }
        });
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    markActiveSidebar();
    bindModals();
    bindCopy();
  });
})();
