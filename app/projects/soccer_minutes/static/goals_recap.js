(function () {
  var side = document.getElementById("scm-goal-add-side");
  var usFields = document.getElementById("scm-goal-add-us-fields");
  var scorer = document.getElementById("scm-goal-add-scorer");
  if (!side || !usFields) {
    return;
  }

  function sync() {
    var ours = side.value !== "them";
    usFields.hidden = !ours;
    if (scorer) {
      scorer.required = ours;
    }
  }

  side.addEventListener("change", sync);
  sync();
})();
