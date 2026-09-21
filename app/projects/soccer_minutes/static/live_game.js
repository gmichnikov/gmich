(function () {
  var stateNode = document.getElementById("scm-game-state");
  var pitchRoot = document.getElementById("scm-field-pitch");
  var benchRoot = document.getElementById("scm-bench");
  var statusNode = document.getElementById("scm-field-status");
  var csrfNode = document.getElementById("scm-csrf");
  var offButton = document.getElementById("scm-send-off");
  var clockDisplay = document.getElementById("scm-clock-display");
  var clockPeriod = document.getElementById("scm-clock-period");
  var clockScore = document.getElementById("scm-clock-score");
  var goalUs = document.getElementById("scm-goal-us");
  var goalThem = document.getElementById("scm-goal-them");
  var goalConfirm = document.getElementById("scm-goal-confirm");
  var goalConfirmTitle = document.getElementById("scm-goal-confirm-title");
  var goalUsFields = document.getElementById("scm-goal-us-fields");
  var goalScorer = document.getElementById("scm-goal-scorer");
  var goalAssist = document.getElementById("scm-goal-assist");
  var goalClock = document.getElementById("scm-goal-clock");
  var goalConfirmBtn = document.getElementById("scm-goal-confirm-btn");
  var goalCancel = document.getElementById("scm-goal-cancel");
  var goalList = document.getElementById("scm-goal-list");
  var pauseResume = document.getElementById("scm-pause-resume");
  var endPeriod = document.getElementById("scm-end-period");
  var setForm = document.getElementById("scm-set-clock-form");
  var setInput = document.getElementById("scm-set-clock");
  var goButton = document.getElementById("scm-go");
  var resetButton = document.getElementById("scm-reset");
  var goConfirm = document.getElementById("scm-go-confirm");
  var goClock = document.getElementById("scm-go-clock");
  var goConfirmBtn = document.getElementById("scm-go-confirm-btn");
  var goCancel = document.getElementById("scm-go-cancel");
  var diffRoot = document.getElementById("scm-diff");
  var warnRoot = document.getElementById("scm-warnings");
  var minutesRoot = document.getElementById("scm-minutes");
  var undoButton = document.getElementById("scm-undo");
  var fieldTitle = document.getElementById("scm-field-title");
  var spellsToggle = document.getElementById("scm-toggle-spells");
  var fieldCard = document.getElementById("scm-pending-field");
  if (!stateNode || !pitchRoot) {
    return;
  }

  var state = JSON.parse(stateNode.textContent);
  var selected = null;
  var saving = false;
  var goTimeDirty = false;
  var goalTimeDirty = false;
  var goalSide = "us";
  var wakeSentinel = null;
  var showSpells = false;
  try {
    showSpells = localStorage.getItem("scm-show-spells") === "1";
  } catch (err) {
    showSpells = false;
  }

  function csrfToken() {
    if (csrfNode && csrfNode.value) {
      return csrfNode.value;
    }
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  }

  function showStatus(text, isError) {
    if (!statusNode) {
      return;
    }
    if (!text) {
      statusNode.hidden = true;
      statusNode.textContent = "";
      statusNode.classList.remove("scm-roster-status-error");
      return;
    }
    statusNode.hidden = false;
    statusNode.textContent = text;
    statusNode.classList.toggle("scm-roster-status-error", !!isError);
  }

  function postJson(url, body) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": csrfToken(),
      },
      body: JSON.stringify(body || {}),
    }).then(function (response) {
      return response.text().then(function (text) {
        var data;
        try {
          data = JSON.parse(text);
        } catch (err) {
          data = { ok: false, error: "Could not save. Try again." };
        }
        if (!response.ok) {
          data.ok = false;
          data.error = data.error || "Could not save. Try again.";
        }
        return data;
      });
    });
  }

  function displayedMs() {
    var clock = state.clock || {};
    if (!clock.running || !clock.last_resumed_at) {
      return clock.elapsed_ms || 0;
    }
    var resumed = Date.parse(clock.last_resumed_at);
    if (isNaN(resumed)) {
      return clock.elapsed_ms || 0;
    }
    return Math.max(0, (clock.elapsed_ms || 0) + (Date.now() - resumed));
  }

  function formatMs(ms) {
    var total = Math.max(0, Math.floor(ms / 1000));
    var minutes = Math.floor(total / 60);
    var seconds = total % 60;
    return minutes + ":" + (seconds < 10 ? "0" : "") + seconds;
  }

  function spellFor(playerId) {
    if (!playerId || !showSpells) {
      return "";
    }
    var spells = state.spells || {};
    var spell = spells[playerId] || spells[String(playerId)];
    if (!spell) {
      return "";
    }
    var ms = Math.max(0, displayedMs() - (spell.since_ms || 0));
    return " (" + formatMs(ms) + ")";
  }

  function syncSpellsToggle() {
    if (fieldCard) {
      fieldCard.classList.toggle("scm-show-spells", showSpells);
    }
    if (spellsToggle) {
      spellsToggle.setAttribute("aria-pressed", showSpells ? "true" : "false");
      spellsToggle.textContent = showSpells ? "Times on" : "Times";
    }
  }

  function appendSpell(parent, playerId) {
    if (!playerId) {
      return;
    }
    var spell = document.createElement("span");
    spell.className = "scm-spell";
    spell.setAttribute("data-spell-player", String(playerId));
    spell.textContent = spellFor(playerId);
    parent.appendChild(spell);
  }

  function tickClock() {
    if (clockDisplay) {
      clockDisplay.textContent = formatMs(displayedMs());
    }
    if (goClock && goConfirm && !goConfirm.hidden && !goTimeDirty) {
      goClock.value = formatMs(displayedMs());
    }
    if (goalClock && goalConfirm && !goalConfirm.hidden && !goalTimeDirty) {
      goalClock.value = formatMs(displayedMs());
    }
    if (showSpells) {
      document.querySelectorAll("[data-spell-player]").forEach(function (node) {
        var playerId = parseInt(node.getAttribute("data-spell-player"), 10);
        node.textContent = spellFor(playerId);
      });
    }
  }

  function syncWakeLock() {
    var want =
      document.visibilityState === "visible" &&
      state.clock &&
      state.clock.running;
    if (!want) {
      if (wakeSentinel) {
        wakeSentinel.release().catch(function () {});
        wakeSentinel = null;
      }
      return;
    }
    if (wakeSentinel || !navigator.wakeLock || !navigator.wakeLock.request) {
      return;
    }
    navigator.wakeLock
      .request("screen")
      .then(function (lock) {
        wakeSentinel = lock;
        lock.addEventListener("release", function () {
          if (wakeSentinel === lock) {
            wakeSentinel = null;
          }
        });
      })
      .catch(function () {});
  }

  function hideGoConfirm() {
    if (goConfirm) {
      goConfirm.hidden = true;
    }
    goTimeDirty = false;
  }

  function hideGoalConfirm() {
    if (goalConfirm) {
      goalConfirm.hidden = true;
    }
    goalTimeDirty = false;
  }

  function fillGoalPlayers() {
    var people = state.goal_players || [];
    function fill(select, includeBlank, blankLabel) {
      if (!select) {
        return;
      }
      var current = select.value;
      select.innerHTML = "";
      if (includeBlank) {
        var blank = document.createElement("option");
        blank.value = "";
        blank.textContent = blankLabel;
        select.appendChild(blank);
      }
      people.forEach(function (person) {
        var option = document.createElement("option");
        option.value = String(person.id);
        option.textContent = person.on_field
          ? person.label
          : person.label + " (bench)";
        select.appendChild(option);
      });
      if (current) {
        select.value = current;
      }
    }
    fill(goalScorer, true, "Who scored?");
    fill(goalAssist, true, "No assist");
  }

  function renderGoals() {
    if (clockScore) {
      clockScore.textContent = (state.score && state.score.displayed) || "0–0";
    }
    if (!goalList) {
      return;
    }
    goalList.innerHTML = "";
    (state.goals || []).forEach(function (goal) {
      var li = document.createElement("li");
      li.className = "scm-goal-row";
      var line = document.createElement("span");
      line.className = "scm-goal-line";
      line.textContent = "P" + goal.period + " · " + goal.clock + " · " + goal.label;
      li.appendChild(line);
      if (goal.warning) {
        var warn = document.createElement("span");
        warn.className = "scm-goal-warning";
        warn.textContent = goal.warning;
        li.appendChild(warn);
      }
      if (goal.deleteUrl) {
        var remove = document.createElement("button");
        remove.type = "button";
        remove.className = "scm-btn scm-btn-secondary scm-btn-small";
        remove.textContent = "Remove";
        remove.addEventListener("click", function () {
          if (saving) {
            return;
          }
          if (!window.confirm("Remove this goal?")) {
            return;
          }
          runAction(goal.deleteUrl, {});
        });
        li.appendChild(remove);
      }
      goalList.appendChild(li);
    });
  }

  function openGoalConfirm(side) {
    hideGoConfirm();
    goalSide = side;
    goalTimeDirty = false;
    if (goalConfirmTitle) {
      goalConfirmTitle.textContent = side === "them" ? "They scored" : "We scored";
    }
    if (goalUsFields) {
      goalUsFields.hidden = side === "them";
    }
    fillGoalPlayers();
    if (goalScorer) {
      goalScorer.value = "";
    }
    if (goalAssist) {
      goalAssist.value = "";
    }
    if (goalClock) {
      goalClock.value = formatMs(displayedMs());
    }
    if (goalConfirm) {
      goalConfirm.hidden = false;
    }
  }

  function applyState(next) {
    if (next.reload || (next.phase && next.phase !== "live")) {
      window.location.reload();
      return;
    }
    state = next;
    selected = null;
    hideGoConfirm();
    hideGoalConfirm();
    render();
    tickClock();
    syncWakeLock();
  }

  function runAction(url, body) {
    if (saving) {
      return;
    }
    saving = true;
    showStatus("Saving…");
    postJson(url, body)
      .then(function (data) {
        saving = false;
        if (!data.ok) {
          showStatus(data.error || "Could not save. Try again.", true);
          return;
        }
        applyState(data);
        showStatus("");
      })
      .catch(function () {
        saving = false;
        showStatus("Could not save. Check your connection.", true);
      });
  }

  function pendingMap() {
    var copy = {};
    var source = (state.pending && state.pending.assignments) || {};
    Object.keys(source).forEach(function (key) {
      copy[key] = source[key];
    });
    return copy;
  }

  function removePlayer(map, playerId) {
    Object.keys(map).forEach(function (key) {
      if (Number(map[key]) === Number(playerId)) {
        delete map[key];
      }
    });
  }

  function savePending(map) {
    runAction(state.pendingUrl, { assignments: map });
  }

  function slotByKey(key) {
    var found = null;
    var bands = (state.pending && state.pending.bands) || [];
    bands.forEach(function (band) {
      band.slots.forEach(function (slot) {
        if (slot.key === key) {
          found = slot;
        }
      });
    });
    return found;
  }

  function renderPitch() {
    var bands = (state.pending && state.pending.bands) || [];
    var maxLine = 1;
    pitchRoot.innerHTML = "";
    bands.forEach(function (band) {
      maxLine = Math.max(maxLine, (band.slots || []).length);
      var bandEl = document.createElement("div");
      bandEl.className = "scm-pitch-band scm-pitch-band-" + band.group;
      if ((band.slots || []).length >= 4) {
        bandEl.classList.add("scm-pitch-band-crowded");
      }
      var label = document.createElement("span");
      label.className = "scm-pitch-band-label";
      label.textContent = band.label;
      var slots = document.createElement("div");
      slots.className = "scm-pitch-slots";
      if (!band.slots.length) {
        var none = document.createElement("span");
        none.className = "scm-pitch-empty";
        none.textContent = "None";
        slots.appendChild(none);
      }
      band.slots.forEach(function (slot) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "scm-pitch-slot scm-field-slot";
        if (slot.player_id) {
          btn.classList.add("scm-slot-filled");
        }
        if (slot.changed) {
          btn.classList.add("scm-slot-changed");
        }
        if (slot.emptied) {
          btn.classList.add("scm-slot-emptied");
        }
        btn.setAttribute("data-slot-key", slot.key);
        btn.setAttribute("data-player-id", slot.player_id || "");
        if (slot.player_label) {
          btn.title = slot.player_label;
        }
        var pos = document.createElement("span");
        pos.className = "scm-slot-pos";
        pos.textContent = slot.name;
        var who = document.createElement("span");
        who.className = "scm-slot-who";
        var full = document.createElement("span");
        full.className = "scm-slot-who-full";
        full.textContent = slot.player_label || "—";
        var compact = document.createElement("span");
        compact.className = "scm-slot-who-compact";
        compact.textContent = slot.player_compact_label || slot.player_label || "—";
        who.appendChild(full);
        who.appendChild(compact);
        appendSpell(who, slot.player_id);
        btn.appendChild(pos);
        btn.appendChild(who);
        if (
          selected &&
          selected.kind === "slot" &&
          selected.slotKey === slot.key
        ) {
          btn.classList.add("scm-is-selected");
        }
        slots.appendChild(btn);
      });
      bandEl.appendChild(label);
      bandEl.appendChild(slots);
      pitchRoot.appendChild(bandEl);
    });
    pitchRoot.style.setProperty("--scm-line-n", String(Math.max(4, maxLine)));
  }

  function renderBench() {
    if (!benchRoot) {
      return;
    }
    var bench = ((state.pending && state.pending.bench) || []).slice().sort(function (a, b) {
      var byName = (a.first_name || "").localeCompare(b.first_name || "", undefined, {
        sensitivity: "base",
      });
      if (byName) {
        return byName;
      }
      return (a.full_name || a.label || "").localeCompare(
        b.full_name || b.label || "",
        undefined,
        { sensitivity: "base" }
      );
    });
    benchRoot.innerHTML = "";
    if (!bench.length) {
      var empty = document.createElement("p");
      empty.className = "scm-muted scm-bench-empty";
      empty.textContent = "No one on the bench.";
      benchRoot.appendChild(empty);
      return;
    }
    bench.forEach(function (person) {
      var chip = document.createElement("button");
      chip.type = "button";
      chip.className = "scm-bench-chip";
      chip.setAttribute("data-player-id", String(person.id));
      chip.appendChild(document.createTextNode(person.label));
      appendSpell(chip, person.id);
      if (
        selected &&
        selected.kind === "bench" &&
        selected.playerId === person.id
      ) {
        chip.classList.add("scm-is-selected");
      }
      benchRoot.appendChild(chip);
    });
  }

  function renderDiff() {
    if (!diffRoot) {
      return;
    }
    diffRoot.innerHTML = "";
    var lines = state.diff || [];
    lines.forEach(function (line) {
      var li = document.createElement("li");
      li.textContent = line;
      diffRoot.appendChild(li);
    });
    diffRoot.hidden = lines.length === 0;
    if (warnRoot) {
      warnRoot.textContent = (state.warnings || []).join(" · ");
      warnRoot.hidden = !(state.warnings && state.warnings.length);
    }
  }

  function renderMinutes() {
    if (!minutesRoot) {
      return;
    }
    minutesRoot.innerHTML = "";
    (state.minutes || []).forEach(function (row) {
      var li = document.createElement("li");
      li.className = "scm-minutes-row";
      li.setAttribute("data-name", row.first_name || row.label || "");
      li.setAttribute("data-ms", String(row.total_ms || 0));
      var name = document.createElement("span");
      name.className = "scm-minutes-name";
      name.textContent = row.label;
      var total = document.createElement("span");
      total.className = "scm-minutes-total";
      total.textContent = row.total;
      var groups = document.createElement("span");
      groups.className = "scm-minutes-groups";
      groups.textContent =
        "GK " +
        row.groups.gk +
        " · DEF " +
        row.groups.def +
        " · MID " +
        row.groups.mid +
        " · FWD " +
        row.groups.fwd;
      li.appendChild(name);
      li.appendChild(total);
      li.appendChild(groups);
      minutesRoot.appendChild(li);
    });
    if (typeof window.scmSortMinutes === "function") {
      window.scmSortMinutes();
    }
  }

  function render() {
    renderPitch();
    renderBench();
    renderDiff();
    renderMinutes();
    renderGoals();
    fillGoalPlayers();
    if (fieldTitle) {
      fieldTitle.textContent = state.can_go ? "Pending field" : "Field";
    }
    syncSpellsToggle();
    if (clockPeriod) {
      clockPeriod.textContent =
        "Period " + state.current_period + " of " + state.period_count;
    }
    if (pauseResume) {
      pauseResume.textContent = state.clock && state.clock.running ? "Pause" : "Resume";
    }
    if (goButton) {
      goButton.disabled = !state.can_go;
    }
    if (resetButton) {
      resetButton.disabled = !state.can_go;
    }
    if (endPeriod) {
      endPeriod.disabled = !!state.can_go;
    }
    if (offButton) {
      offButton.disabled = !(selected && selected.kind === "slot" && selected.slotKey);
    }
    if (undoButton) {
      if (state.undo_label) {
        undoButton.hidden = false;
        undoButton.textContent = state.undo_label;
      } else {
        undoButton.hidden = true;
      }
    }
    if (setInput && document.activeElement !== setInput) {
      setInput.placeholder = formatMs(displayedMs());
    }
  }

  function onSlotTap(slotKey) {
    if (saving) {
      return;
    }
    var slot = slotByKey(slotKey);
    if (!slot) {
      return;
    }
    if (selected && selected.kind === "slot" && selected.slotKey === slotKey) {
      selected = null;
      render();
      return;
    }
    if (selected && selected.kind === "bench") {
      var map = pendingMap();
      removePlayer(map, selected.playerId);
      map[slotKey] = selected.playerId;
      savePending(map);
      return;
    }
    if (selected && selected.kind === "slot" && selected.slotKey !== slotKey) {
      var current = pendingMap();
      if (slot.player_id) {
        var a = current[selected.slotKey];
        var b = current[slotKey];
        if (a) {
          current[slotKey] = a;
        } else {
          delete current[slotKey];
        }
        if (b) {
          current[selected.slotKey] = b;
        } else {
          delete current[selected.slotKey];
        }
        savePending(current);
      } else {
        var mover = current[selected.slotKey];
        if (mover) {
          delete current[selected.slotKey];
          current[slotKey] = mover;
          savePending(current);
        } else {
          selected = { kind: "slot", slotKey: slotKey, playerId: null };
          render();
        }
      }
      return;
    }
    selected = {
      kind: "slot",
      slotKey: slotKey,
      playerId: slot.player_id || null,
    };
    render();
  }

  function onBenchTap(playerId) {
    if (saving) {
      return;
    }
    if (selected && selected.kind === "bench" && selected.playerId === playerId) {
      selected = null;
      render();
      return;
    }
    if (selected && selected.kind === "slot" && selected.slotKey) {
      var map = pendingMap();
      removePlayer(map, playerId);
      map[selected.slotKey] = playerId;
      savePending(map);
      return;
    }
    selected = { kind: "bench", playerId: playerId };
    render();
  }

  pitchRoot.addEventListener("click", function (event) {
    var btn = event.target.closest(".scm-field-slot");
    if (!btn || !pitchRoot.contains(btn)) {
      return;
    }
    onSlotTap(btn.getAttribute("data-slot-key"));
  });

  if (benchRoot) {
    benchRoot.addEventListener("click", function (event) {
      var btn = event.target.closest(".scm-bench-chip");
      if (!btn || !benchRoot.contains(btn)) {
        return;
      }
      onBenchTap(parseInt(btn.getAttribute("data-player-id"), 10));
    });
  }

  if (offButton) {
    offButton.addEventListener("click", function () {
      if (saving || !selected || selected.kind !== "slot") {
        return;
      }
      var map = pendingMap();
      delete map[selected.slotKey];
      savePending(map);
    });
  }

  if (pauseResume) {
    pauseResume.addEventListener("click", function () {
      var running = state.clock && state.clock.running;
      runAction(running ? state.pauseUrl : state.resumeUrl, {});
    });
  }

  if (endPeriod) {
    endPeriod.addEventListener("click", function () {
      runAction(state.endUrl, {});
    });
  }

  if (setForm) {
    setForm.addEventListener("submit", function (event) {
      event.preventDefault();
      runAction(state.setClockUrl, { clock: setInput.value });
    });
  }

  if (resetButton) {
    resetButton.addEventListener("click", function () {
      runAction(state.resetUrl, {});
    });
  }

  if (goButton) {
    goButton.addEventListener("click", function () {
      if (!state.can_go || !goConfirm) {
        return;
      }
      goConfirm.hidden = false;
      goTimeDirty = false;
      goClock.value = formatMs(displayedMs());
    });
  }

  if (goClock) {
    goClock.addEventListener("input", function () {
      goTimeDirty = true;
    });
  }

  if (goConfirmBtn) {
    goConfirmBtn.addEventListener("click", function () {
      runAction(state.goUrl, { clock: goClock.value });
    });
  }

  if (goCancel) {
    goCancel.addEventListener("click", hideGoConfirm);
  }

  if (undoButton) {
    undoButton.addEventListener("click", function () {
      runAction(state.undoUrl, {});
    });
  }

  if (goalUs) {
    goalUs.addEventListener("click", function () {
      openGoalConfirm("us");
    });
  }

  if (goalThem) {
    goalThem.addEventListener("click", function () {
      openGoalConfirm("them");
    });
  }

  if (goalClock) {
    goalClock.addEventListener("input", function () {
      goalTimeDirty = true;
    });
  }

  if (goalConfirmBtn) {
    goalConfirmBtn.addEventListener("click", function () {
      if (!state.goalUrl) {
        return;
      }
      var body = { side: goalSide };
      if (goalTimeDirty && goalClock && goalClock.value) {
        body.clock = goalClock.value;
      }
      if (goalSide === "us") {
        body.scorer_id = goalScorer ? goalScorer.value : "";
        body.assist_id = goalAssist ? goalAssist.value : "";
      }
      runAction(state.goalUrl, body);
    });
  }

  if (goalCancel) {
    goalCancel.addEventListener("click", hideGoalConfirm);
  }

  if (spellsToggle) {
    spellsToggle.addEventListener("click", function () {
      showSpells = !showSpells;
      try {
        localStorage.setItem("scm-show-spells", showSpells ? "1" : "0");
      } catch (err) {
        /* ignore */
      }
      syncSpellsToggle();
      tickClock();
    });
  }

  document.addEventListener("visibilitychange", function () {
    tickClock();
    syncWakeLock();
  });

  render();
  tickClock();
  syncWakeLock();
  setInterval(tickClock, 250);
})();
