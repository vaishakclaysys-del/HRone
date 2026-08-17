/* Final results: offer letter modal */
(function () {
  "use strict";

  function openOfferLetter(name, email, score, role, recommendation) {
    document.getElementById("detailCandidateName").textContent = name;
    document.getElementById("detailCandidateEmail").textContent = email || "—";

    var sc = parseInt(score, 10) || 0;
    var position = role || (sc >= 80 ? "AI/ML Engineer (L3)" : "AI/ML Engineer (L1)");
    document.getElementById("letterPosition").textContent = position;
    document.getElementById("detailPosition").textContent = position;

    var recMap = {
      "highly_recommended": "Overall the candidate is highly recommended and demonstrates exceptional skills.",
      "recommended":        "Overall the candidate meets the core requirements and is a suitable fit.",
      "below_expectations": "Overall the candidate appears trainable with a good foundational understanding.",
      "not_recommended":    "Overall the candidate shows some gaps but may be considered for a junior role."
    };
    document.getElementById("letterRecommendationText").textContent = recMap[recommendation] || "";

    var today = new Date();
    var dateStr = today.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
    document.getElementById("letterDate").textContent = dateStr;

    document.getElementById("offerModal").classList.add("is-active");
    var msg = document.getElementById("copiedMsg");
    if (msg) msg.classList.remove("is-visible");
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".offer-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        openOfferLetter(
          btn.dataset.name,
          btn.dataset.email,
          btn.dataset.score,
          btn.dataset.role,
          btn.dataset.rec
        );
      });
    });

    var exportBtn = document.querySelector("[data-export-url]");
    if (exportBtn) {
      exportBtn.addEventListener("click", function () {
        window.location.href = exportBtn.getAttribute("data-export-url");
      });
    }
  });
})();

// Additional: handle offer generation buttons that POST to a generate URL
(function () {
  async function openOfferLetterFromUrl(url, role) {
    try {
      var today = new Date();
      var dateStr = today.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
      var dateEl = document.getElementById('letterDate');
      if (dateEl) dateEl.textContent = dateStr;

      var loading = document.getElementById('letterLoading');
      var generated = document.getElementById('letterGeneratedText');
      var errorEl = document.getElementById('letterError');
      var copiedMsg = document.getElementById('copiedMsg');

      if (loading) loading.style.display = 'block';
      if (generated) generated.style.display = 'none';
      if (errorEl) errorEl.style.display = 'none';
      if (copiedMsg) copiedMsg.style.display = 'none';

      var modal = document.getElementById('offerModal');
      if (modal) modal.classList.add('active');

      var resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ job_position: role || '', reporting_to: '', salary: '' }),
      });

      if (!resp.ok) throw new Error('request failed');
      var data = await resp.json();

      if (loading) loading.style.display = 'none';
      if (generated) { generated.textContent = data.letter || data.html || ''; generated.style.display = 'block'; }
    } catch (err) {
      var loading2 = document.getElementById('letterLoading');
      var errorEl2 = document.getElementById('letterError');
      if (loading2) loading2.style.display = 'none';
      if (errorEl2) { errorEl2.textContent = 'Failed to generate offer letter. Please try again.'; errorEl2.style.display = 'block'; }
      console.error(err);
    }
  }

  function closeModal() {
    var modal = document.getElementById('offerModal');
    if (modal) modal.classList.remove('active');
  }

  function copyLetter() {
    var content = document.getElementById('copyContent');
    if (!content) return;
    navigator.clipboard.writeText(content.innerText || content.textContent || '').then(function () {
      var msg = document.getElementById('copiedMsg');
      if (msg) { msg.style.display = 'inline'; setTimeout(function () { msg.style.display = 'none'; }, 2500); }
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.offer-btn[data-generate-url]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        openOfferLetterFromUrl(btn.getAttribute('data-generate-url'), btn.getAttribute('data-role'));
      });
    });

    var modal = document.getElementById('offerModal');
    if (modal) {
      modal.addEventListener('click', function (e) { if (e.target === modal) closeModal(); });
    }

    // expose helpers for template onclicks
    window.closeModal = closeModal;
    window.copyLetter = copyLetter;
  });
})();
