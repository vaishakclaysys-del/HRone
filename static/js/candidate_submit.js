/* Candidate submit page: surface server message as alert */
document.addEventListener("DOMContentLoaded", function () {
  var el = document.getElementById("csMessage");
  if (el && el.dataset.message) {
    setTimeout(function () { alert(el.dataset.message); }, 100);
  }
});
