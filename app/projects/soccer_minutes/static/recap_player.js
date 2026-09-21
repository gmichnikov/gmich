(function () {
  var list = document.getElementById("scm-minutes");
  var dataNode = document.getElementById("scm-bench-details");
  var dialog = document.getElementById("scm-player-dialog");
  var title = document.getElementById("scm-player-dialog-title");
  var totals = document.getElementById("scm-player-dialog-totals");
  var stretches = document.getElementById("scm-player-dialog-list");
  var empty = document.getElementById("scm-player-dialog-empty");
  var closeBtn = document.getElementById("scm-player-dialog-close");
  if (!list || !dataNode || !dialog) {
    return;
  }

  var details = {};
  try {
    details = JSON.parse(dataNode.textContent || "{}") || {};
  } catch (err) {
    details = {};
  }

  function openPlayer(playerId) {
    var row = details[String(playerId)];
    if (!row) {
      return;
    }
    title.textContent = row.label || "Player";
    totals.textContent =
      "On field " + (row.on_field || "0:00") + " · Bench " + (row.bench || "0:00");
    stretches.innerHTML = "";
    var items = row.stretches || [];
    items.forEach(function (stretch) {
      var li = document.createElement("li");
      li.className = "scm-stretch";
      li.textContent =
        "Period " +
        stretch.period +
        " · " +
        stretch.start +
        "–" +
        stretch.end +
        " (" +
        stretch.duration +
        ")";
      stretches.appendChild(li);
    });
    if (empty) {
      empty.hidden = items.length > 0;
    }
    if (typeof dialog.showModal === "function") {
      dialog.showModal();
    } else {
      dialog.setAttribute("open", "open");
    }
  }

  function closeDialog() {
    if (typeof dialog.close === "function") {
      dialog.close();
    } else {
      dialog.removeAttribute("open");
    }
  }

  list.addEventListener("click", function (event) {
    var hit = event.target.closest("[data-player-id]");
    if (!hit || !list.contains(hit)) {
      return;
    }
    openPlayer(hit.getAttribute("data-player-id"));
  });

  if (closeBtn) {
    closeBtn.addEventListener("click", closeDialog);
  }

  dialog.addEventListener("click", function (event) {
    if (event.target === dialog) {
      closeDialog();
    }
  });
})();
