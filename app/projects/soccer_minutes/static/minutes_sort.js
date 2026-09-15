(function () {
  var STORAGE_KEY = "scm-minutes-sort";
  var ul = document.getElementById("scm-minutes");
  var bar = document.getElementById("scm-minutes-sort");
  if (!ul || !bar) {
    return;
  }

  function loadSpec() {
    try {
      var spec = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "null");
      if (spec && (spec.key === "name" || spec.key === "minutes")) {
        return spec;
      }
    } catch (err) {
      /* ignore */
    }
    return { key: null, dir: "asc" };
  }

  function saveSpec(spec) {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(spec));
  }

  function arrow(dir) {
    return dir === "asc" ? " ↑" : " ↓";
  }

  function updateButtons(spec) {
    bar.querySelectorAll("[data-sort]").forEach(function (btn) {
      var key = btn.getAttribute("data-sort");
      var label = key === "minutes" ? "Minutes" : "Name";
      if (spec.key === key) {
        btn.textContent = label + arrow(spec.dir);
        btn.classList.add("scm-is-active");
      } else {
        btn.textContent = label;
        btn.classList.remove("scm-is-active");
      }
    });
  }

  function sortMinutes() {
    var spec = loadSpec();
    updateButtons(spec);
    if (!spec.key) {
      return;
    }
    var items = Array.prototype.slice.call(ul.querySelectorAll(".scm-minutes-row"));
    items.sort(function (a, b) {
      var cmp;
      if (spec.key === "name") {
        cmp = (a.getAttribute("data-name") || "").localeCompare(
          b.getAttribute("data-name") || "",
          undefined,
          { sensitivity: "base" }
        );
      } else {
        cmp =
          (parseInt(a.getAttribute("data-ms"), 10) || 0) -
          (parseInt(b.getAttribute("data-ms"), 10) || 0);
      }
      return spec.dir === "asc" ? cmp : -cmp;
    });
    items.forEach(function (item) {
      ul.appendChild(item);
    });
  }

  bar.addEventListener("click", function (event) {
    var btn = event.target.closest("[data-sort]");
    if (!btn || !bar.contains(btn)) {
      return;
    }
    var key = btn.getAttribute("data-sort");
    var spec = loadSpec();
    if (spec.key === key) {
      spec.dir = spec.dir === "asc" ? "desc" : "asc";
    } else {
      spec.key = key;
      spec.dir = key === "minutes" ? "desc" : "asc";
    }
    saveSpec(spec);
    sortMinutes();
  });

  window.scmSortMinutes = sortMinutes;
  sortMinutes();
})();
