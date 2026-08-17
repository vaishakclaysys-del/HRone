/* Admin user management: skills toggle, password match, eye toggle */
(function () {
  "use strict";

  function toggleSkills(role) {
    var section = document.getElementById("skills_section");
    if (!section) return;
    section.style.display = role === "senior_dev" ? "block" : "none";
    if (role !== "senior_dev") {
      document.querySelectorAll('input[name="skills"]').forEach(function (cb) { cb.checked = false; });
    }
  }

  function toggleVisibility(fieldId, eyeId) {
    var input = document.getElementById(fieldId);
    var eye = document.getElementById(eyeId);
    if (!input || !eye) return;
    if (input.type === "password") { input.type = "text"; eye.textContent = "🙈"; }
    else { input.type = "password"; eye.textContent = "👁"; }
  }

  function validatePasswords() {
    var pw = document.getElementById("password");
    var cf = document.getElementById("confirm_password");
    var err = document.getElementById("password_error");
    if (!pw || !cf || !err) return true;
    if (pw.value !== cf.value) { err.style.display = "block"; return false; }
    err.style.display = "none"; return true;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var roleSel = document.getElementById("role_select");
    if (roleSel) roleSel.addEventListener("change", function () { toggleSkills(roleSel.value); });

    document.querySelectorAll("[data-toggle-password]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var target = btn.getAttribute("data-toggle-password");
        var eye = btn.getAttribute("data-eye");
        toggleVisibility(target, eye);
      });
    });

    var form = document.querySelector("form[data-validate-passwords]");
    if (form) form.addEventListener("submit", function (e) {
      if (!validatePasswords()) e.preventDefault();
    });
  });
})();
