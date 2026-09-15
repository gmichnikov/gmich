(function () {
  document.querySelectorAll("[data-ns-sort-table]").forEach(initTable);

  function initTable(table) {
    var tbody = table.querySelector("tbody");
    if (!tbody) return;
    var headers = table.querySelectorAll("th[data-ns-sort]");
    if (!headers.length) return;

    var initial = table.querySelector(
      'th[aria-sort="ascending"], th[aria-sort="descending"]'
    );
    var state = {
      col: initial ? initial.getAttribute("data-ns-sort") : null,
      dir:
        initial && initial.getAttribute("aria-sort") === "descending"
          ? "desc"
          : "asc",
    };

    function attr(row, key) {
      return row.getAttribute("data-ns-" + key) || "";
    }

    function headerFor(col) {
      return table.querySelector('th[data-ns-sort="' + col + '"]');
    }

    function isEmpty(val, th) {
      if (!val) return true;
      var markers = th && th.getAttribute("data-ns-empty");
      if (!markers) return false;
      return markers.split("|").indexOf(val) !== -1;
    }

    function compare(a, b) {
      var mul = state.dir === "asc" ? 1 : -1;
      var th = headerFor(state.col);
      var av = attr(a, state.col);
      var bv = attr(b, state.col);
      if (th && th.hasAttribute("data-ns-empty-last")) {
        var aEmpty = isEmpty(av, th);
        var bEmpty = isEmpty(bv, th);
        if (aEmpty !== bEmpty) return aEmpty ? 1 : -1;
      }
      var primary;
      if (th && th.getAttribute("data-ns-sort-type") === "number") {
        primary = (Number(av) || 0) - (Number(bv) || 0);
      } else {
        primary = av.localeCompare(bv, undefined, {
          sensitivity: "base",
          numeric: true,
        });
      }
      if (primary !== 0) return primary * mul;
      var tieCol = table.getAttribute("data-ns-sort-tie") || "entry";
      return attr(a, tieCol).localeCompare(attr(b, tieCol), undefined, {
        sensitivity: "base",
      });
    }

    function apply() {
      if (!state.col) return;
      var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
      rows.sort(compare);
      rows.forEach(function (row) {
        tbody.appendChild(row);
      });
      headers.forEach(function (th) {
        var active = th.getAttribute("data-ns-sort") === state.col;
        th.setAttribute(
          "aria-sort",
          active ? (state.dir === "asc" ? "ascending" : "descending") : "none"
        );
      });
    }

    headers.forEach(function (th) {
      var btn = th.querySelector(".ns-sort-btn");
      if (!btn) return;
      btn.addEventListener("click", function () {
        var col = th.getAttribute("data-ns-sort");
        if (state.col === col) {
          state.dir = state.dir === "asc" ? "desc" : "asc";
        } else {
          state.col = col;
          state.dir = "asc";
        }
        apply();
      });
    });
  }
})();
