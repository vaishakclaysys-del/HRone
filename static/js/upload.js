/* Bulk upload + Excel merge page: drag/drop, file count, loader overlay */
(function () {
  "use strict";

  function setupFileDrop(dropEl) {
    var input = dropEl.querySelector('input[type="file"]');
    var titleEl = dropEl.querySelector(".file-drop-title");
    if (!input) return;

    dropEl.addEventListener("click", function () {
      if (e.target === input) return; 
      input.click(); 
      });

    ["dragenter", "dragover"].forEach(function (evt) {
      dropEl.addEventListener(evt, function (e) {
        e.preventDefault(); e.stopPropagation();
        dropEl.classList.add("is-dragover");
      });
    });
    ["dragleave", "drop"].forEach(function (evt) {
      dropEl.addEventListener(evt, function (e) {
        e.preventDefault(); e.stopPropagation();
        dropEl.classList.remove("is-dragover");
      });
    });
    dropEl.addEventListener("drop", function (e) {
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        updateLabel();
      }
    });
    input.addEventListener("change", updateLabel);

    function updateLabel() {
      var n = input.files ? input.files.length : 0;
      if (titleEl && n > 0) {
        titleEl.textContent = n + " file" + (n === 1 ? "" : "s") + " selected";
      }
      var btn = document.querySelector('[data-upload-count="' + input.name + '"]');
      if (btn) {
        var baseLabel = btn.getAttribute("data-base-label") || btn.textContent.trim();
        btn.setAttribute("data-base-label", baseLabel);
        btn.textContent = baseLabel + " (" + n + ")";
      }
    }
  }

  function setupFilePicker(pickerEl) {
    var input = pickerEl.querySelector('input[type="file"]');
    var nameEl = pickerEl.querySelector(".file-name");
    if (!input || !nameEl) return;
    var defaultLabel = nameEl.textContent;
    input.addEventListener("change", function () {
      if (input.files && input.files.length) nameEl.textContent = input.files[0].name;
      else nameEl.textContent = defaultLabel;
    });
  }

  function bindLoaderForms() {
    document.querySelectorAll('[data-loader-form]').forEach(function (form) {
      form.addEventListener("submit", function () {
        var loader = document.getElementById("loader");
        if (loader) loader.classList.add("is-active");
        var btn = form.querySelector('button[type="submit"]');
        if (btn) btn.disabled = true;
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".file-drop").forEach(setupFileDrop);
    document.querySelectorAll(".file-picker").forEach(setupFilePicker);
    bindLoaderForms();
  });
})();
