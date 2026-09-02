(function () {
  "use strict";

  var editor = document.getElementById("blu-structure-editor");
  if (!editor) {
    return;
  }

  var table = editor.querySelector(".blu-structure-table");
  var inningInput = document.getElementById("blu-inning-count");
  var applyButton = document.getElementById("blu-apply-inning-1");
  var batteryCodes = ["P", "PH"];

  function parseCount(value) {
    var n = parseInt(value, 10);
    return isNaN(n) || n < 0 ? 0 : n;
  }

  function clampInnings(raw) {
    var n = parseInt(raw, 10);
    if (isNaN(n)) {
      return 6;
    }
    return Math.max(1, Math.min(12, n));
  }

  function getPositionCodes() {
    var codes = [];
    table.querySelectorAll("tbody tr:not(.blu-structure-total-row)").forEach(function (row) {
      var input = row.querySelector(".blu-structure-input");
      if (input) {
        codes.push(input.getAttribute("data-code"));
      }
    });
    return codes;
  }

  function readCounts(codes, inningCount) {
    var counts = {};
    codes.forEach(function (code) {
      counts[code] = [];
      for (var inning = 1; inning <= inningCount; inning += 1) {
        var input = table.querySelector(
          'input[data-code="' + code + '"][data-inning="' + inning + '"]'
        );
        counts[code].push(input ? parseCount(input.value) : 0);
      }
    });
    return counts;
  }

  function resizeRow(row, inningCount) {
    if (!row.length) {
      return Array(inningCount).fill(0);
    }
    if (row.length < inningCount) {
      var last = row[row.length - 1];
      while (row.length < inningCount) {
        row.push(last);
      }
    }
    return row.slice(0, inningCount);
  }

  function columnTotal(counts, codes, inning) {
    var total = 0;
    codes.forEach(function (code) {
      total += counts[code][inning - 1] || 0;
    });
    return total;
  }

  function positionLabel(code) {
    var row = table.querySelector('input[data-code="' + code + '"]');
    if (!row) {
      return code;
    }
    var tr = row.closest("tr");
    var labelCell = tr ? tr.querySelector(".blu-structure-pos-col") : null;
    return labelCell ? labelCell.textContent.trim() : code;
  }

  function rebuildTable(inningCount, counts) {
    var codes = getPositionCodes();
    var theadRow = table.querySelector("thead tr");
    theadRow.innerHTML = '<th class="blu-structure-pos-col">Position</th>';
    for (var h = 1; h <= inningCount; h += 1) {
      theadRow.innerHTML += '<th class="blu-structure-inning-col">' + h + "</th>";
    }

    codes.forEach(function (code) {
      counts[code] = resizeRow(counts[code] || [], inningCount);
      var row = table.querySelector('input[data-code="' + code + '"]').closest("tr");
      var isBattery = batteryCodes.indexOf(code) !== -1;
      row.className = isBattery ? "blu-structure-battery-row" : "";
      row.innerHTML =
        '<th scope="row" class="blu-structure-pos-col">' + positionLabel(code) + "</th>";
      for (var inning = 1; inning <= inningCount; inning += 1) {
        row.innerHTML +=
          '<td><input type="number" class="blu-structure-input" name="count_' +
          code +
          "_" +
          inning +
          '" data-code="' +
          code +
          '" data-inning="' +
          inning +
          '" min="0" max="20" value="' +
          (counts[code][inning - 1] || 0) +
          '"></td>';
      }
    });

    var totalRow = table.querySelector(".blu-structure-total-row");
    totalRow.innerHTML = '<th scope="row" class="blu-structure-pos-col">Field spots</th>';
    for (var t = 1; t <= inningCount; t += 1) {
      totalRow.innerHTML +=
        '<td class="blu-structure-total" data-inning="' +
        t +
        '">' +
        columnTotal(counts, codes, t) +
        "</td>";
    }

    bindInputListeners();
  }

  function updateTotals() {
    var inningCount = clampInnings(inningInput.value);
    var codes = getPositionCodes();
    var counts = readCounts(codes, inningCount);
    table.querySelectorAll(".blu-structure-total").forEach(function (cell) {
      var inning = parseInt(cell.getAttribute("data-inning"), 10);
      cell.textContent = columnTotal(counts, codes, inning);
    });
  }

  function bindInputListeners() {
    table.querySelectorAll(".blu-structure-input").forEach(function (input) {
      input.removeEventListener("input", updateTotals);
      input.addEventListener("input", updateTotals);
    });
  }

  if (applyButton) {
    applyButton.addEventListener("click", function () {
      var inningCount = clampInnings(inningInput.value);
      var codes = getPositionCodes();
      codes.forEach(function (code) {
        var first = table.querySelector(
          'input[data-code="' + code + '"][data-inning="1"]'
        );
        if (!first) {
          return;
        }
        var value = first.value;
        for (var inning = 2; inning <= inningCount; inning += 1) {
          var input = table.querySelector(
            'input[data-code="' + code + '"][data-inning="' + inning + '"]'
          );
          if (input) {
            input.value = value;
          }
        }
      });
      updateTotals();
    });
  }

  if (inningInput) {
    inningInput.addEventListener("change", function () {
      var newCount = clampInnings(inningInput.value);
      inningInput.value = newCount;
      var codes = getPositionCodes();
      var oldCount = table.querySelectorAll(".blu-structure-inning-col").length;
      var counts = readCounts(codes, oldCount);
      rebuildTable(newCount, counts);
    });
  }

  bindInputListeners();
})();
