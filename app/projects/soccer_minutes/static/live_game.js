(function () {
  var stateNode = document.getElementById("scm-game-state");
  var pitchRoot = document.getElementById("scm-field-pitch");
  var benchRoot = document.getElementById("scm-bench");
  var statusNode = document.getElementById("scm-field-status");
  var csrfNode = document.getElementById("scm-csrf");
  var offButton = document.getElementById("scm-send-off");
  var clockDisplay = document.getElementById("scm-clock-display");
  var clockPeriod = document.getElementById("scm-clock-period");
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
  if (!stateNode || !pitchRoot) {
    return;
  }

  var state = JSON.parse(stateNode.textContent);
  var selected = null;
  var saving = false;
  var goTimeDirty = false;
  var wakeSentinel = null;

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

  function tickClock() {
    if (clockDisplay) {
      clockDisplay.textContent = formatMs(displayedMs());
    }
    if (goClock && goConfirm && !goConfirm.hidden && !goTimeDirty) {
      goClock.value = formatMs(displayedMs());
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

  function applyState(next) {
    if (next.reload || (next.phase && next.phase !== "live")) {
      window.location.reload();
      return;
    }
    state = next;
    selected = null;
    hideGoConfirm();
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
    pitchRoot.innerHTML = "";
    bands.forEach(function (band) {
      var bandEl = document.createElement("div");
      bandEl.className = "scm-pitch-band scm-pitch-band-" + band.group;
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
        var pos = document.createElement("span");
        pos.className = "scm-slot-pos";
        pos.textContent = slot.name;
        var who = document.createElement("span");
        who.className = "scm-slot-who";
        who.textContent = slot.player_label || "—";
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
  }

  function renderBench() {
    if (!benchRoot) {
      return;
    }
    var bench = (state.pending && state.pending.bench) || [];
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
      chip.textContent = person.label;
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
  }

  function render() {
    renderPitch();
    renderBench();
    renderDiff();
    renderMinutes();
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

  document.addEventListener("visibilitychange", function () {
    tickClock();
    syncWakeLock();
  });

  render();
  tickClock();
  syncWakeLock();
  setInterval(tickClock, 250);
})();
