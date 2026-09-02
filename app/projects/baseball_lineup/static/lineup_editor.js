(function () {
  "use strict";

  var root = document.getElementById("blu-lineup-editor");
  var dataEl = document.getElementById("blu-lineup-data");
  if (!root || !dataEl) {
    return;
  }

  var state = JSON.parse(dataEl.textContent);
  var thead = document.getElementById("blu-lineup-thead");
  var tbody = document.getElementById("blu-lineup-tbody");
  var warningsPanel = document.getElementById("blu-lineup-warnings");
  var warningsList = document.getElementById("blu-warnings-list");
  var saveBtn = document.getElementById("blu-lineup-save");
  var saveStatus = document.getElementById("blu-save-status");
  var fillAllBtn = document.getElementById("blu-fill-all-bench");

  var CATEGORY_BY_CODE = {
    C: "infield",
    "1B": "infield",
    "2B": "infield",
    "3B": "infield",
    SS: "infield",
    LF: "outfield",
    CF: "outfield",
    RF: "outfield",
    P: "infield",
    PH: "infield",
    Bench: "bench",
  };

  function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  }

  function expectedCount(code, inning) {
    var row = state.expected_counts[code] || [];
    var idx = inning - 1;
    if (idx >= 0 && idx < row.length) {
      return row[idx] || 0;
    }
    return 0;
  }

  function fieldSpotsForInning(inning) {
    var total = 0;
    state.editor_field_codes.forEach(function (item) {
      total += expectedCount(item.code, inning);
    });
    return total;
  }

  function summarizeRow(cells) {
    var summary = { outfield: 0, infield: 0, bench: 0, blank: 0 };
    for (var inning = 1; inning <= state.inning_count; inning += 1) {
      var code = cells[String(inning)] || "";
      var category = CATEGORY_BY_CODE[code];
      if (!category) {
        summary.blank += 1;
      } else {
        summary[category] += 1;
      }
    }
    return summary;
  }

  function repeatedPositions(cells) {
    var counts = {};
    Object.keys(cells).forEach(function (key) {
      var code = cells[key];
      if (!code || code === "Bench") {
        return;
      }
      counts[code] = (counts[code] || 0) + 1;
    });
    var repeats = {};
    Object.keys(counts).forEach(function (code) {
      if (counts[code] > 1) {
        repeats[code] = counts[code];
      }
    });
    return repeats;
  }

  function computeWarnings() {
    var warnings = [];
    var presentCount = state.rows.length;

    for (var inning = 1; inning <= state.inning_count; inning += 1) {
      var actualByCode = {};
      var unassigned = 0;

      state.rows.forEach(function (row) {
        var code = row.cells[String(inning)] || "";
        if (!code) {
          unassigned += 1;
        } else {
          actualByCode[code] = (actualByCode[code] || 0) + 1;
        }
      });

      state.editor_field_codes.forEach(function (item) {
        var expected = expectedCount(item.code, inning);
        var actual = actualByCode[item.code] || 0;
        if (actual !== expected) {
          if (actual === 0) {
            warnings.push(
              "Inning " + inning + ": expected " + expected + " " + item.label + ", found none"
            );
          } else {
            warnings.push(
              "Inning " + inning + ": expected " + expected + " " + item.label + ", found " + actual
            );
          }
        }
      });

      if (unassigned) {
        warnings.push(
          "Inning " + inning + ": " + unassigned + (unassigned === 1 ? " player" : " players") + " unassigned"
        );
      }

      var fieldSpots = fieldSpotsForInning(inning);
      if (fieldSpots > presentCount) {
        warnings.push(
          "Inning " + inning + ": " + fieldSpots + " field spots but only " + presentCount + " players present"
        );
      }
    }

    return warnings;
  }

  function renderHeader() {
    var row1 = document.createElement("tr");
    row1.innerHTML = '<th class="blu-lineup-player-col" rowspan="2">Player</th>';
    for (var inning = 1; inning <= state.inning_count; inning += 1) {
      row1.innerHTML += '<th class="blu-lineup-inning-col">' + inning + "</th>";
    }
    row1.innerHTML +=
      '<th class="blu-lineup-summary-col" rowspan="2">OF</th>' +
      '<th class="blu-lineup-summary-col" rowspan="2">Bench</th>' +
      '<th class="blu-lineup-summary-col" rowspan="2">IF</th>' +
      '<th class="blu-lineup-summary-col" rowspan="2">Blank</th>';

    var row2 = document.createElement("tr");
    for (var fillInning = 1; fillInning <= state.inning_count; fillInning += 1) {
      row2.innerHTML +=
        '<th class="blu-lineup-fill-col">' +
        '<button type="button" class="blu-btn blu-btn-secondary blu-btn-tiny blu-fill-inning" data-inning="' +
        fillInning +
        '">Fill Bench</button></th>';
    }

    thead.innerHTML = "";
    thead.appendChild(row1);
    thead.appendChild(row2);

    thead.querySelectorAll(".blu-fill-inning").forEach(function (btn) {
      btn.addEventListener("click", function () {
        fillBlanksWithBench(parseInt(btn.getAttribute("data-inning"), 10));
      });
    });
  }

  function buildSelect(playerId, inning, value, repeats) {
    var select = document.createElement("select");
    select.className = "blu-lineup-select";
    select.dataset.playerId = String(playerId);
    select.dataset.inning = String(inning);

    var empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "—";
    select.appendChild(empty);

    state.position_codes.forEach(function (item) {
      var option = document.createElement("option");
      option.value = item.code;
      option.textContent = item.code;
      if (value === item.code) {
        option.selected = true;
      }
      select.appendChild(option);
    });

    if (value && repeats[value]) {
      select.classList.add("blu-cell-repeat");
      select.title = value + " — " + repeats[value] + " innings this game";
    }

    select.addEventListener("change", function () {
      var row = state.rows.find(function (r) {
        return r.player_id === playerId;
      });
      if (row) {
        row.cells[String(inning)] = select.value;
        renderBody();
      }
    });

    return select;
  }

  function renderBody() {
    tbody.innerHTML = "";

    state.rows.forEach(function (row) {
      var tr = document.createElement("tr");
      var repeats = repeatedPositions(row.cells);
      var summary = summarizeRow(row.cells);

      var nameCell = document.createElement("th");
      nameCell.scope = "row";
      nameCell.className = "blu-lineup-player-col";
      nameCell.textContent = row.player_name;
      tr.appendChild(nameCell);

      for (var inning = 1; inning <= state.inning_count; inning += 1) {
        var td = document.createElement("td");
        var value = row.cells[String(inning)] || "";
        td.appendChild(buildSelect(row.player_id, inning, value, repeats));
        tr.appendChild(td);
      }

      ["outfield", "bench", "infield", "blank"].forEach(function (key) {
        var sumTd = document.createElement("td");
        sumTd.className = "blu-lineup-summary-col blu-lineup-summary-value";
        sumTd.textContent = String(summary[key]);
        tr.appendChild(sumTd);
      });

      tbody.appendChild(tr);
    });

    renderWarnings();
  }

  function renderWarnings() {
    var warnings = computeWarnings();
    warningsList.innerHTML = "";
    warnings.forEach(function (text) {
      var li = document.createElement("li");
      li.textContent = text;
      warningsList.appendChild(li);
    });
    warningsPanel.classList.toggle("blu-warnings-panel-empty", warnings.length === 0);
  }

  function fillBlanksWithBench(inning) {
    state.rows.forEach(function (row) {
      if (inning) {
        if (!row.cells[String(inning)]) {
          row.cells[String(inning)] = "Bench";
        }
      } else {
        for (var i = 1; i <= state.inning_count; i += 1) {
          if (!row.cells[String(i)]) {
            row.cells[String(i)] = "Bench";
          }
        }
      }
    });
    renderBody();
  }

  function collectCellsPayload() {
    var cells = [];
    state.rows.forEach(function (row) {
      for (var inning = 1; inning <= state.inning_count; inning += 1) {
        var code = row.cells[String(inning)] || "";
        if (!code) {
          continue;
        }
        cells.push({
          player_id: row.player_id,
          inning: inning,
          position_code: code,
        });
      }
    });
    return cells;
  }

  function saveLineup() {
    saveBtn.disabled = true;
    saveStatus.textContent = "Saving…";

    var headers = {
      Accept: "application/json",
      "Content-Type": "application/json",
    };
    var token = getCsrfToken();
    if (token) {
      headers["X-CSRFToken"] = token;
    }

    fetch(root.dataset.saveUrl, {
      method: "POST",
      headers: headers,
      credentials: "same-origin",
      body: JSON.stringify({ cells: collectCellsPayload() }),
    })
      .then(function (response) {
        return response.json().then(function (data) {
          return { ok: response.ok, data: data };
        });
      })
      .then(function (result) {
        if (!result.ok || !result.data.ok) {
          throw new Error((result.data && result.data.error) || "Save failed.");
        }
        saveStatus.textContent = "Saved.";
        window.location.href = result.data.redirect || root.dataset.cancelUrl;
      })
      .catch(function (err) {
        saveStatus.textContent = err.message || "Save failed.";
        saveBtn.disabled = false;
      });
  }

  if (fillAllBtn) {
    fillAllBtn.addEventListener("click", function () {
      fillBlanksWithBench(null);
    });
  }

  if (saveBtn) {
    saveBtn.addEventListener("click", saveLineup);
  }

  renderHeader();
  renderBody();
})();
