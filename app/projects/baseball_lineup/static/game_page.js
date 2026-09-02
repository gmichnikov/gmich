(function () {
  "use strict";

  var pageRoot = document.getElementById("blu-game-page");
  var dataEl = document.getElementById("blu-game-data");
  if (!pageRoot || !dataEl) {
    return;
  }

  var boot = JSON.parse(dataEl.textContent);
  var urls = boot.urls;
  var lineup = boot.state.lineup;
  var pageState = boot.state;

  var attendanceCollapse = document.getElementById("blu-attendance-collapse");
  var attendanceSummary = document.getElementById("blu-attendance-summary");
  var attendanceBody = document.getElementById("blu-attendance-body");
  var gameSubtitle = document.getElementById("blu-game-subtitle");
  var thead = document.getElementById("blu-lineup-thead");
  var tbody = document.getElementById("blu-lineup-tbody");
  var lineupScroll = document.getElementById("blu-lineup-scroll");
  var warningsPanel = document.getElementById("blu-lineup-warnings");
  var warningsTitle = document.getElementById("blu-warnings-title");
  var warningsFilters = document.getElementById("blu-warnings-filters");
  var warningsContent = document.getElementById("blu-warnings-content");
  var lineupEmpty = document.getElementById("blu-lineup-empty");
  var saveBtn = document.getElementById("blu-save-lineup");
  var saveStatus = document.getElementById("blu-save-status");
  var fillAllBtn = document.getElementById("blu-fill-all-bench");
  var randomizeBtn = document.getElementById("blu-randomize-order");
  var lineupToolbar = document.getElementById("blu-lineup-toolbar");

  var gameId = pageRoot.dataset.gameId;
  var collapseKey = "blu-game-" + gameId + "-attendance-open";
  var dirty = false;
  var warningFilterInning = "all";

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

  function urlFor(template, playerId) {
    return template.replace("{player_id}", String(playerId));
  }

  function apiPost(url, body) {
    var headers = {
      Accept: "application/json",
      "X-Requested-With": "XMLHttpRequest",
    };
    var token = getCsrfToken();
    if (token) {
      headers["X-CSRFToken"] = token;
    }
    var options = {
      method: "POST",
      headers: headers,
      credentials: "same-origin",
    };
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    return fetch(url, options).then(function (response) {
      return response.json().then(function (data) {
        if (!response.ok || !data.ok) {
          throw new Error((data && data.error) || "Request failed.");
        }
        return data;
      });
    });
  }

  function getActiveCell() {
    var el = document.activeElement;
    if (el && el.classList.contains("blu-lineup-select")) {
      return {
        playerId: el.dataset.playerId,
        inning: el.dataset.inning,
      };
    }
    return null;
  }

  function restoreActiveCell(target) {
    if (!target) {
      return;
    }
    var selector =
      '.blu-lineup-select[data-player-id="' +
      target.playerId +
      '"][data-inning="' +
      target.inning +
      '"]';
    var el = tbody.querySelector(selector);
    if (el) {
      el.focus();
    }
  }

  function expectedCount(code, inning) {
    var row = lineup.expected_counts[code] || [];
    var idx = inning - 1;
    if (idx >= 0 && idx < row.length) {
      return row[idx] || 0;
    }
    return 0;
  }

  function fieldSpotsForInning(inning) {
    var total = 0;
    lineup.editor_field_codes.forEach(function (item) {
      total += expectedCount(item.code, inning);
    });
    return total;
  }

  function summarizeRow(cells) {
    var summary = { outfield: 0, infield: 0, bench: 0, blank: 0 };
    for (var inning = 1; inning <= lineup.inning_count; inning += 1) {
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

  function computeOverassignedCells(rows) {
    var overassigned = {};

    for (var inning = 1; inning <= lineup.inning_count; inning += 1) {
      var actualByCode = {};
      var playerIdsByCode = {};

      rows.forEach(function (row) {
        var code = row.cells[String(inning)] || "";
        if (!code || code === "Bench") {
          return;
        }
        actualByCode[code] = (actualByCode[code] || 0) + 1;
        if (!playerIdsByCode[code]) {
          playerIdsByCode[code] = [];
        }
        playerIdsByCode[code].push(row.player_id);
      });

      Object.keys(actualByCode).forEach(function (code) {
        var expected = expectedCount(code, inning);
        if (actualByCode[code] > expected) {
          playerIdsByCode[code].forEach(function (playerId) {
            overassigned[playerId + "-" + inning] = {
              code: code,
              actual: actualByCode[code],
              expected: expected,
            };
          });
        }
      });
    }

    return overassigned;
  }

  function computeFairnessHighlights(rows) {
    var categories = ["outfield", "bench", "infield"];
    var highlights = {};

    if (rows.length < 2) {
      return highlights;
    }

    categories.forEach(function (key) {
      var valuesByPlayer = rows.map(function (row) {
        var summary = row.summary || summarizeRow(row.cells);
        return { playerId: row.player_id, value: summary[key] };
      });

      valuesByPlayer.forEach(function (item) {
        var skewed = valuesByPlayer.some(function (other) {
          return other.playerId !== item.playerId && Math.abs(item.value - other.value) > 1;
        });
        if (skewed) {
          if (!highlights[item.playerId]) {
            highlights[item.playerId] = {};
          }
          highlights[item.playerId][key] = true;
        }
      });
    });

    return highlights;
  }

  function computeWarnings() {
    var warnings = [];
    var presentCount = lineup.rows.length;

    for (var inning = 1; inning <= lineup.inning_count; inning += 1) {
      var actualByCode = {};
      var unassigned = 0;

      lineup.rows.forEach(function (row) {
        var code = row.cells[String(inning)] || "";
        if (!code) {
          unassigned += 1;
        } else {
          actualByCode[code] = (actualByCode[code] || 0) + 1;
        }
      });

      lineup.editor_field_codes.forEach(function (item) {
        var expected = expectedCount(item.code, inning);
        var actual = actualByCode[item.code] || 0;
        if (actual !== expected) {
          if (actual === 0) {
            warnings.push({
              inning: inning,
              text: "Expected " + expected + " " + item.label + ", found none",
            });
          } else {
            warnings.push({
              inning: inning,
              text: "Expected " + expected + " " + item.label + ", found " + actual,
            });
          }
        }
      });

      if (unassigned) {
        warnings.push({
          inning: inning,
          text: unassigned + (unassigned === 1 ? " player" : " players") + " unassigned",
        });
      }

      var fieldSpots = fieldSpotsForInning(inning);
      if (fieldSpots > presentCount) {
        warnings.push({
          inning: inning,
          text: fieldSpots + " field spots but only " + presentCount + " players present",
        });
      }
    }

    return warnings;
  }

  function warningsByInning(warnings) {
    var grouped = {};
    warnings.forEach(function (warning) {
      if (!grouped[warning.inning]) {
        grouped[warning.inning] = [];
      }
      grouped[warning.inning].push(warning);
    });
    return grouped;
  }

  function renderWarningFilters(warnings) {
    if (!warningsFilters) {
      return;
    }

    var grouped = warningsByInning(warnings);
    var innings = Object.keys(grouped)
      .map(function (value) {
        return parseInt(value, 10);
      })
      .sort(function (a, b) {
        return a - b;
      });

    warningsFilters.innerHTML = "";
    warningsFilters.hidden = innings.length <= 1;

    function addFilterButton(label, value) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "blu-warnings-filter";
      if (warningFilterInning === value) {
        btn.classList.add("blu-warnings-filter-active");
      }
      btn.textContent = label;
      btn.dataset.inningFilter = value;
      warningsFilters.appendChild(btn);
    }

    addFilterButton("All", "all");
    innings.forEach(function (inning) {
      addFilterButton("Inning " + inning + " (" + grouped[inning].length + ")", String(inning));
    });
  }

  function renderWarningList(items) {
    var list = document.createElement("ul");
    list.className = "blu-warnings-list";
    items.forEach(function (warning) {
      var li = document.createElement("li");
      li.textContent = warning.text;
      list.appendChild(li);
    });
    return list;
  }

  function renderWarnings() {
    var warnings = computeWarnings();
    if (warningFilterInning !== "all") {
      var hasInning = warnings.some(function (warning) {
        return String(warning.inning) === warningFilterInning;
      });
      if (!hasInning) {
        warningFilterInning = "all";
      }
    }
    if (warningsTitle) {
      warningsTitle.textContent =
        warnings.length === 0 ? "Warnings" : "Warnings (" + warnings.length + ")";
    }

    if (!warningsContent) {
      warningsPanel.classList.toggle("blu-warnings-panel-empty", warnings.length === 0);
      return;
    }

    warningsContent.innerHTML = "";
    renderWarningFilters(warnings);

    if (warnings.length === 0) {
      warningsPanel.classList.toggle("blu-warnings-panel-empty", true);
      return;
    }

    warningsPanel.classList.remove("blu-warnings-panel-empty");

    if (warningFilterInning !== "all") {
      var inning = parseInt(warningFilterInning, 10);
      var filtered = warnings.filter(function (warning) {
        return warning.inning === inning;
      });
      warningsContent.appendChild(renderWarningList(filtered));
      return;
    }

    var grouped = warningsByInning(warnings);
    var innings = Object.keys(grouped)
      .map(function (value) {
        return parseInt(value, 10);
      })
      .sort(function (a, b) {
        return a - b;
      });

    var groupsWrap = document.createElement("div");
    groupsWrap.className = "blu-warnings-groups";

    innings.forEach(function (inning) {
      var details = document.createElement("details");
      details.className = "blu-warnings-group";
      if (warnings.length <= 8) {
        details.open = true;
      }

      var summary = document.createElement("summary");
      summary.className = "blu-warnings-group-summary";
      summary.textContent = "Inning " + inning + " (" + grouped[inning].length + ")";
      details.appendChild(summary);
      details.appendChild(renderWarningList(grouped[inning]));
      groupsWrap.appendChild(details);
    });

    warningsContent.appendChild(groupsWrap);
  }

  function renderAttendance() {
    var html = '<p class="blu-muted">Everyone is present by default. Mark absent players before building the lineup.</p>';
    if (!pageState.attendance.length) {
      html = '<p class="blu-muted">Add players to the roster first.</p>';
    } else {
      html += '<ul class="blu-attendance-list">';
      pageState.attendance.forEach(function (row) {
        var absentClass = row.is_present ? "" : " blu-attendance-absent";
        var badgeClass = row.is_present
          ? "blu-attendance-badge-present"
          : "blu-attendance-badge-absent";
        var label = row.is_present ? "Present" : "Absent";
        var action = row.is_present ? "absent" : "present";
        html +=
          '<li class="blu-attendance-item' +
          absentClass +
          '">' +
          '<span class="blu-attendance-name">' +
          escapeHtml(row.name) +
          "</span>" +
          '<div class="blu-attendance-actions">' +
          '<span class="blu-attendance-badge ' +
          badgeClass +
          '">' +
          label +
          "</span>" +
          '<button type="button" class="blu-btn blu-btn-secondary blu-btn-small blu-attendance-toggle" data-player-id="' +
          row.player_id +
          '">Mark ' +
          action +
          "</button>" +
          "</div></li>";
      });
      html += "</ul>";
    }
    attendanceBody.innerHTML = html;
    attendanceSummary.textContent =
      "Attendance (" +
      pageState.present_count +
      " of " +
      pageState.roster_total +
      " present)";
  }

  function buildSelect(row, inning, value, overassigned) {
    var select = document.createElement("select");
    select.className = "blu-lineup-select";
    select.dataset.playerId = String(row.player_id);
    select.dataset.inning = String(inning);

    var empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "—";
    select.appendChild(empty);

    lineup.position_codes.forEach(function (item) {
      var option = document.createElement("option");
      option.value = item.code;
      option.textContent = item.code;
      if (value === item.code) {
        option.selected = true;
      }
      select.appendChild(option);
    });

    var overKey = row.player_id + "-" + inning;
    if (value && overassigned[overKey]) {
      var detail = overassigned[overKey];
      select.classList.add("blu-cell-overassigned");
      select.title =
        "Inning " +
        inning +
        ": " +
        detail.actual +
        " " +
        detail.code +
        " (expected " +
        detail.expected +
        ")";
    }

    select.addEventListener("change", function () {
      row.cells[String(inning)] = select.value;
      row.summary = summarizeRow(row.cells);
      row.repeats = repeatedPositions(row.cells);
      dirty = true;
      saveStatus.textContent = "Unsaved changes";
      renderLineupBody();
    });

    return select;
  }

  function renderLineupHeader() {
    var row1 = document.createElement("tr");
    row1.innerHTML =
      '<th class="blu-lineup-order-col" rowspan="2">#</th>' +
      '<th class="blu-lineup-reorder-col" rowspan="2"></th>' +
      '<th class="blu-lineup-player-col" rowspan="2">Player</th>';
    for (var inning = 1; inning <= lineup.inning_count; inning += 1) {
      row1.innerHTML += '<th class="blu-lineup-inning-col">' + inning + "</th>";
    }
    row1.innerHTML +=
      '<th class="blu-lineup-summary-col" rowspan="2">OF</th>' +
      '<th class="blu-lineup-summary-col" rowspan="2">Bench</th>' +
      '<th class="blu-lineup-summary-col" rowspan="2">IF</th>' +
      '<th class="blu-lineup-summary-col" rowspan="2">Blank</th>';

    var row2 = document.createElement("tr");
    for (var fillInning = 1; fillInning <= lineup.inning_count; fillInning += 1) {
      row2.innerHTML +=
        '<th class="blu-lineup-fill-col">' +
        '<button type="button" class="blu-btn blu-btn-secondary blu-btn-tiny blu-fill-inning" data-inning="' +
        fillInning +
        '">Bench</button></th>';
    }

    thead.innerHTML = "";
    thead.appendChild(row1);
    thead.appendChild(row2);
  }

  function renderLineupBody() {
    var activeCell = getActiveCell();
    var scrollLeft = lineupScroll ? lineupScroll.scrollLeft : 0;
    tbody.innerHTML = "";
    var fairnessHighlights = computeFairnessHighlights(lineup.rows);
    var overassignedCells = computeOverassignedCells(lineup.rows);

    lineup.rows.forEach(function (row, index) {
      var tr = document.createElement("tr");
      var summary = row.summary || summarizeRow(row.cells);
      row.summary = summary;

      var orderTd = document.createElement("td");
      orderTd.className = "blu-lineup-order-col";
      orderTd.textContent = String(row.batting_order);
      tr.appendChild(orderTd);

      var reorderTd = document.createElement("td");
      reorderTd.className = "blu-lineup-reorder-col";
      var reorderWrap = document.createElement("div");
      reorderWrap.className = "blu-lineup-reorder-buttons";

      var upBtn = document.createElement("button");
      upBtn.type = "button";
      upBtn.className = "blu-btn blu-btn-secondary blu-btn-tiny blu-move-up";
      upBtn.title = "Move up";
      upBtn.textContent = "\u25B2";
      upBtn.dataset.playerId = String(row.player_id);
      if (index === 0) {
        upBtn.disabled = true;
      }

      var downBtn = document.createElement("button");
      downBtn.type = "button";
      downBtn.className = "blu-btn blu-btn-secondary blu-btn-tiny blu-move-down";
      downBtn.title = "Move down";
      downBtn.textContent = "\u25BC";
      downBtn.dataset.playerId = String(row.player_id);
      if (index === lineup.rows.length - 1) {
        downBtn.disabled = true;
      }

      reorderWrap.appendChild(upBtn);
      reorderWrap.appendChild(downBtn);
      reorderTd.appendChild(reorderWrap);
      tr.appendChild(reorderTd);

      var nameCell = document.createElement("th");
      nameCell.scope = "row";
      nameCell.className = "blu-lineup-player-col";
      nameCell.textContent = row.player_name;
      tr.appendChild(nameCell);

      for (var inning = 1; inning <= lineup.inning_count; inning += 1) {
        var td = document.createElement("td");
        var value = row.cells[String(inning)] || "";
        td.appendChild(buildSelect(row, inning, value, overassignedCells));
        tr.appendChild(td);
      }

      ["outfield", "bench", "infield", "blank"].forEach(function (key) {
        var sumTd = document.createElement("td");
        sumTd.className = "blu-lineup-summary-col blu-lineup-summary-value";
        if (
          key !== "blank" &&
          fairnessHighlights[row.player_id] &&
          fairnessHighlights[row.player_id][key]
        ) {
          sumTd.classList.add("blu-lineup-summary-skewed");
          sumTd.title = "More than 1 inning off another player";
        }
        sumTd.textContent = String(summary[key]);
        tr.appendChild(sumTd);
      });

      tbody.appendChild(tr);
    });

    if (lineupScroll) {
      lineupScroll.scrollLeft = scrollLeft;
    }
    restoreActiveCell(activeCell);
    renderWarnings();
  }

  function renderLineup() {
    var hasRows = lineup.rows.length > 0;
    lineupEmpty.hidden = hasRows;
    lineupScroll.hidden = !hasRows;
    lineupToolbar.hidden = !hasRows;
    warningsPanel.hidden = !hasRows;

    if (!hasRows) {
      thead.innerHTML = "";
      tbody.innerHTML = "";
      return;
    }

    renderLineupHeader();
    renderLineupBody();
  }

  function renderSubtitle() {
    gameSubtitle.textContent =
      lineup.inning_count +
      " innings \u00b7 " +
      pageState.present_count +
      " of " +
      pageState.roster_total +
      " players present";
  }

  function renderAll() {
    renderSubtitle();
    renderAttendance();
    renderLineup();
  }

  function applyServerState(nextState, options) {
    options = options || {};
    var cellsByPlayer = {};
    if (options.preserveCells && dirty) {
      lineup.rows.forEach(function (row) {
        cellsByPlayer[row.player_id] = Object.assign({}, row.cells);
      });
    }

    pageState = nextState;
    lineup = nextState.lineup;

    if (options.preserveCells && Object.keys(cellsByPlayer).length) {
      lineup.rows.forEach(function (row) {
        if (cellsByPlayer[row.player_id]) {
          row.cells = cellsByPlayer[row.player_id];
          row.summary = summarizeRow(row.cells);
          row.repeats = repeatedPositions(row.cells);
        }
      });
      pageState.lineup = lineup;
    } else {
      dirty = false;
    }

    renderAll();
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function fillBlanksWithBench(inning) {
    lineup.rows.forEach(function (row) {
      if (inning) {
        if (!row.cells[String(inning)]) {
          row.cells[String(inning)] = "Bench";
        }
      } else {
        for (var i = 1; i <= lineup.inning_count; i += 1) {
          if (!row.cells[String(i)]) {
            row.cells[String(i)] = "Bench";
          }
        }
      }
    });
    dirty = true;
    saveStatus.textContent = "Unsaved changes";
    renderLineupBody();
  }

  function collectCellsPayload() {
    var cells = [];
    lineup.rows.forEach(function (row) {
      for (var inning = 1; inning <= lineup.inning_count; inning += 1) {
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
    saveStatus.textContent = "Saving\u2026";
    return apiPost(urls.lineup_save, { cells: collectCellsPayload() })
      .then(function (data) {
        applyServerState(data.state);
        saveStatus.textContent = "Saved.";
      })
      .catch(function (err) {
        saveStatus.textContent = err.message || "Save failed.";
      })
      .finally(function () {
        saveBtn.disabled = false;
      });
  }

  function postAction(url, preserveCells) {
    return apiPost(url).then(function (data) {
      applyServerState(data.state, { preserveCells: preserveCells });
    });
  }

  attendanceBody.addEventListener("click", function (event) {
    var btn = event.target.closest(".blu-attendance-toggle");
    if (!btn) {
      return;
    }
    btn.disabled = true;
    postAction(urlFor(urls.attendance_toggle, btn.dataset.playerId), true).catch(function (err) {
      saveStatus.textContent = err.message || "Update failed.";
    });
  });

  tbody.addEventListener("click", function (event) {
    var upBtn = event.target.closest(".blu-move-up");
    if (upBtn) {
      upBtn.disabled = true;
      postAction(urlFor(urls.batting_move_up, upBtn.dataset.playerId), true).catch(function (err) {
        saveStatus.textContent = err.message || "Update failed.";
      });
      return;
    }
    var downBtn = event.target.closest(".blu-move-down");
    if (downBtn) {
      downBtn.disabled = true;
      postAction(urlFor(urls.batting_move_down, downBtn.dataset.playerId), true).catch(function (err) {
        saveStatus.textContent = err.message || "Update failed.";
      });
    }
  });

  thead.addEventListener("click", function (event) {
    var btn = event.target.closest(".blu-fill-inning");
    if (btn) {
      fillBlanksWithBench(parseInt(btn.dataset.inning, 10));
    }
  });

  if (fillAllBtn) {
    fillAllBtn.addEventListener("click", function () {
      fillBlanksWithBench(null);
    });
  }

  if (randomizeBtn) {
    randomizeBtn.addEventListener("click", function () {
      randomizeBtn.disabled = true;
      postAction(urls.batting_randomize, true)
        .then(function () {
          saveStatus.textContent = "Order randomized.";
        })
        .catch(function (err) {
          saveStatus.textContent = err.message || "Update failed.";
        })
        .finally(function () {
          randomizeBtn.disabled = false;
        });
    });
  }

  if (saveBtn) {
    saveBtn.addEventListener("click", saveLineup);
  }

  if (warningsPanel) {
    warningsPanel.addEventListener("click", function (event) {
      var btn = event.target.closest(".blu-warnings-filter");
      if (!btn) {
        return;
      }
      warningFilterInning = btn.dataset.inningFilter || "all";
      renderWarnings();
    });
  }

  if (sessionStorage.getItem(collapseKey) === "closed") {
    attendanceCollapse.removeAttribute("open");
  }
  attendanceCollapse.addEventListener("toggle", function () {
    sessionStorage.setItem(
      collapseKey,
      attendanceCollapse.open ? "open" : "closed"
    );
  });

  window.addEventListener("beforeunload", function (event) {
    if (dirty) {
      event.preventDefault();
      event.returnValue = "";
    }
  });

  renderAll();
})();
