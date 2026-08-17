/* HR candidate detail page: decision toggle, inline field edit, email modal */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {

    /* ---------- Edit decision form toggle ---------- */
    var editBtn = document.getElementById("editBtn");
    var form = document.getElementById("editDecisionForm");
    if (editBtn && form) {
      editBtn.addEventListener("click", function () {
        var open = form.classList.toggle("is-visible");
        form.style.display = open ? "block" : "none";
        editBtn.textContent = open ? "✖ Cancel" : "✏️ Edit Decision";
      });
    }

    /* ---------- Inline edit: candidate email / phone ---------- */
    var editCandidateBtn = document.getElementById("editCandidateBtn");
    var saveCandidateBtn = document.getElementById("saveCandidateBtn");
    var email = document.getElementById("candidateEmail");
    var phone = document.getElementById("candidatePhone");

    if (editCandidateBtn) {
      editCandidateBtn.addEventListener("click", function () {
        if (email) email.readOnly = false;
        if (phone) phone.readOnly = false;
        if (email) email.focus();

        if (saveCandidateBtn) saveCandidateBtn.style.display = "inline-flex";
        editCandidateBtn.style.display = "none";
      });
    }

    /* ---------- Email template modal ---------- */
    var emailModal = document.getElementById("emailModal");
    var openEmailBtn = document.getElementById("openEmailBtn");
    var closeEmailBtn = document.getElementById("closeEmailBtn");
    var copyEmailBtn = document.getElementById("copyEmailBtn");
    var emailContent = document.getElementById("emailContent");
    var copiedMsg = document.getElementById("copiedMsg");

    if (openEmailBtn && emailModal) {
      openEmailBtn.addEventListener("click", function () {
        emailModal.removeAttribute("hidden");
      });
    }

    if (closeEmailBtn && emailModal) {
      closeEmailBtn.addEventListener("click", function () {
        emailModal.setAttribute("hidden", "");
      });
    }

    // Close modal on backdrop click (not on click inside the box itself)
    if (emailModal) {
      emailModal.addEventListener("click", function (e) {
        if (e.target === emailModal) {
          emailModal.setAttribute("hidden", "");
        }
      });
    }

    if (copyEmailBtn && emailContent) {
      copyEmailBtn.addEventListener("click", function () {
        var text = emailContent.innerText;
        navigator.clipboard.writeText(text).then(function () {
          if (copiedMsg) {
            copiedMsg.classList.add("is-visible");
            setTimeout(function () {
              copiedMsg.classList.remove("is-visible");
            }, 1800);
          }
        });
      });
    }
  });
})();