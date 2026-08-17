/* HR interview scheduling: multi-select interviewer dropdown + auto-match */
(function () {
  "use strict";

  function toggleDropdown(trigger) {
    var dropdown = trigger.nextElementSibling;
    dropdown.classList.toggle("is-open");
    document.addEventListener("click", function close(e) {
      if (!trigger.parentElement.contains(e.target)) {
        dropdown.classList.remove("is-open");
        document.removeEventListener("click", close);
      }
    });
  }

  function updateLabel(wrapper) {
    var checked = wrapper.querySelectorAll('input[name="interviewer_username[]"]:checked');
    var autoBox = wrapper.querySelector('input[data-auto-suggest]');
    var label = wrapper.querySelector(".multi-select-label");
    if (autoBox && autoBox.checked) {
      label.textContent = "Auto-suggest interviewer";
    } else if (checked.length === 0) {
      label.textContent = "Select interviewer";
    } else if (checked.length === 1) {
      label.textContent = checked[0].closest("label").textContent.trim();
    } else {
      label.textContent = checked.length + " interviewers selected";
    }
  }

  function handleAutoSuggest(checkbox) {
    if (checkbox.checked) {
      var namedBoxes = checkbox
        .closest(".multi-select-dropdown")
        .querySelectorAll('input[name="interviewer_username[]"]');
      namedBoxes.forEach(function (cb) { cb.checked = false; });
      checkbox.checked = false;
      findMatchingInterviewer();
    }
    updateLabel(checkbox.closest(".multi-select-wrapper"));
  }

  function findMatchingInterviewer() {
    var candidateSelect = document.getElementById("candidateSelect");
    var autoSuggestBtn = document.querySelector('[data-auto-suggest]');
        if (autoSuggestBtn && autoSuggestBtn.dataset.hasCandidates === 'false') {
          showMatchModal(null);
          return;
        }

        if (!candidateSelect.value) {
          showMatchModal(null);
          return;
        }

    var selectedOption = candidateSelect.options[candidateSelect.selectedIndex];
    var candidateSkills = (selectedOption.dataset.skills || "")
      .split(",").map(function (s) { return s.trim().toLowerCase(); }).filter(Boolean);

    if (candidateSkills.length === 0) { showMatchModal([]); return; }

    var seniors = document.querySelectorAll('input[name="interviewer_username[]"]');
    var matches = [];
    seniors.forEach(function (cb) {
      var seniorSkills = (cb.dataset.skills || "")
        .split(",").map(function (s) { return s.trim().toLowerCase(); }).filter(Boolean);
      var matched = candidateSkills.filter(function (s) { return seniorSkills.indexOf(s) !== -1; });
      if (matched.length > 0) {
        var pct = Math.round((matched.length / candidateSkills.length) * 100);
        matches.push({
          username: cb.value,
          label: cb.closest("label").textContent.trim(),
          matched: matched,
          pct: pct
        });
      }
    });
    matches.sort(function (a, b) { return b.pct - a.pct; });
    showMatchModal(matches);
  }

  function showMatchModal(matches) {
    var list = document.getElementById("matchList");
    if (matches === null) {
    list.innerHTML = '<p class="muted">No eligible candidates available for interview scheduling.</p>';
    } else if (matches.length === 0) {
        list.innerHTML = '<p class="muted">No matching senior found based on skills. Please select manually from the dropdown.</p>';
      }
      else {
      list.innerHTML = matches.map(function (m) {
        return (
          '<div class="match-card">' +
            '<div class="match-head"><strong>' + escapeHtml(m.label) + '</strong>' +
              '<span class="badge badge-success">' + m.pct + '% match</span>' +
            '</div>' +
            '<div class="match-skills">Matched skills: ' + escapeHtml(m.matched.join(", ")) + '</div>' +
            '<button type="button" class="btn btn-dark btn-sm mt-2" data-select-interviewer="' +
              escapeAttr(m.username) + '">Select</button>' +
          '</div>'
        );
      }).join("");
      list.querySelectorAll("[data-select-interviewer]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          selectInterviewer(btn.getAttribute("data-select-interviewer"));
        });
      });
    }
    document.getElementById("matchModal").classList.add("is-active");
  }

  function selectInterviewer(username) {
    document.querySelectorAll('input[name="interviewer_username[]"]').forEach(function (cb) {
      cb.checked = false;
    });
    var autoBox = document.querySelector('input[data-auto-suggest]');
    if (autoBox) autoBox.checked = false;
    var target = document.querySelector('input[value="' + username + '"]');
    if (target) {
      target.checked = true;
      updateLabel(target.closest(".multi-select-wrapper"));
    }
    document.getElementById("matchModal").classList.remove("is-active");
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c];
    });
  }
  function escapeAttr(s) { return escapeHtml(s); }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".multi-select-trigger").forEach(function (trigger) {
      trigger.addEventListener("click", function () { toggleDropdown(trigger); });
    });
    document.querySelectorAll('input[data-auto-suggest]').forEach(function (cb) {
      cb.addEventListener("change", function () { handleAutoSuggest(cb); });
    });
    document.querySelectorAll('input[name="interviewer_username[]"]').forEach(function (cb) {
      cb.addEventListener("change", function () { updateLabel(cb.closest(".multi-select-wrapper")); });
    });
    // match modal close buttons
    document.querySelectorAll('[data-match-close]').forEach(function (btn) {
      btn.addEventListener('click', function () { var m = document.getElementById('matchModal'); if (m) m.classList.remove('is-active'); });
    });
  });
})();
