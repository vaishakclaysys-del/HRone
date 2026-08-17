document.addEventListener('DOMContentLoaded', function () {
  // Move to Offer handlers
  document.querySelectorAll('.offer-move-start').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var id = btn.dataset.candidateId;
      var confirmEl = document.getElementById('offer-confirm-' + id);
      if (confirmEl) {
        confirmEl.style.display = 'block';
      }
    });
  });

  document.querySelectorAll('.offer-move-cancel').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var id = btn.dataset.candidateId;
      var confirmEl = document.getElementById('offer-confirm-' + id);
      if (confirmEl) {
        confirmEl.style.display = 'none';
      }
    });
  });

  // Reject handlers
  document.querySelectorAll('.reject-move-start').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var id = btn.dataset.candidateId;
      var confirmEl = document.getElementById('reject-confirm-' + id);
      if (confirmEl) {
        confirmEl.style.display = 'block';
      }
    });
  });

  document.querySelectorAll('.reject-move-cancel').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var id = btn.dataset.candidateId;
      var confirmEl = document.getElementById('reject-confirm-' + id);
      if (confirmEl) {
        confirmEl.style.display = 'none';
      }
    });
  });

  // Toast message handling
  var toast = document.getElementById('toastMessage');
  if (toast) {
    var toastText = document.getElementById('toastMessageText');
    var message = toast.dataset.message || '';
    var error = toast.dataset.error || '';

    if (message || error) {
      toastText.textContent = message || error;
      toast.classList.remove('success', 'error', 'show');
      toast.classList.add(error ? 'error' : 'success');
      toast.style.display = 'block';

      requestAnimationFrame(function () {
        toast.classList.add('show');
      });

      setTimeout(function () {
        toast.classList.remove('show');
      }, 3500);

      setTimeout(function () {
        toast.style.display = 'none';
      }, 3900);

      try {
        var params = new URLSearchParams(window.location.search);
        params.delete('message');
        params.delete('error');
        var cleanUrl = window.location.pathname + (params.toString() ? '?' + params.toString() : '');
        history.replaceState(null, '', cleanUrl);
      } catch (e) {
        // ignore URL manipulation errors in older browsers
      }
    }
  }
});
