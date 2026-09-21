(function () {
  var stateNode = document.getElementById("scm-game-state");
  var pitchRoot = document.getElementById("scm-field-pitch");
  var benchRoot = document.getElementById("scm-bench");
  var statusNode = document.getElementById("scm-field-status");
  var filledNode = document.getElementById("scm-filled-n");
  var headerFilled = document.getElementById("scm-header-filled");
  var headerSize = document.getElementById("scm-header-size");
  var csrfNode = document.getElementById("scm-csrf");
  var offButton = document.getElementById("scm-send-off");
  if (!stateNode || !pitchRoot) {
    return;
  }

  var state = JSON.parse(stateNode.textContent);
  var selected = null;
  var saving = false;

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
      body: JSON.stringify(body),
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

  function applyState(next) {
    if (next.reload || next.phase === "live") {
      window.location.reload();
      return;
    }
    state.assignments = next.assignments;
    state.bands = next.bands;
    state.bench = next.bench;
    state.filled = next.filled;
    state.field_size = next.field_size;
    state.phase = next.phase;
    state.locked = next.locked;
    state.undo_label = next.undo_label;
    state.minutes = next.minutes;
    state.score = next.score;
    selected = null;
    render();
  }

  function render() {
    var maxLine = 1;
    pitchRoot.innerHTML = "";
    state.bands.forEach(function (band) {
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

    if (benchRoot) {
      benchRoot.innerHTML = "";
      if (!state.bench.length) {
        var empty = document.createElement("p");
        empty.className = "scm-muted scm-bench-empty";
        empty.textContent = "No one on the bench.";
        benchRoot.appendChild(empty);
      } else {
        state.bench
          .slice()
          .sort(function (a, b) {
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
          })
          .forEach(function (person) {
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
    }

    if (filledNode) {
      filledNode.textContent = String(state.filled);
    }
    if (headerFilled) {
      headerFilled.textContent = String(state.filled);
    }
    if (headerSize) {
      headerSize.textContent = String(state.field_size);
    }
    var headerScore = document.getElementById("scm-header-score");
    if (headerScore && state.score) {
      headerScore.textContent = state.score.displayed;
    }
    if (offButton) {
      offButton.disabled = !(selected && selected.kind === "slot" && selected.slotKey);
    }
  }

  function slotByKey(key) {
    var found = null;
    state.bands.forEach(function (band) {
      band.slots.forEach(function (slot) {
        if (slot.key === key) {
          found = slot;
        }
      });
    });
    return found;
  }

  function nextAssignments() {
    var copy = {};
    Object.keys(state.assignments || {}).forEach(function (key) {
      copy[key] = state.assignments[key];
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

  function saveAssignments(map) {
    if (saving) {
      return;
    }
    saving = true;
    showStatus("Saving…");
    postJson(state.fieldUrl, { assignments: map })
      .then(function (data) {
        saving = false;
        if (!data.ok) {
          showStatus(data.error || "Could not save the field.", true);
          return;
        }
        applyState(data);
        showStatus("");
      })
      .catch(function () {
        saving = false;
        showStatus("Could not save the field. Check your connection.", true);
      });
  }

  function placePlayer(playerId, slotKey) {
    var map = nextAssignments();
    removePlayer(map, playerId);
    map[slotKey] = playerId;
    saveAssignments(map);
  }

  function clearSlot(slotKey) {
    var map = nextAssignments();
    delete map[slotKey];
    saveAssignments(map);
  }

  function swapSlots(keyA, keyB) {
    var map = nextAssignments();
    var a = map[keyA];
    var b = map[keyB];
    if (a) {
      map[keyB] = a;
    } else {
      delete map[keyB];
    }
    if (b) {
      map[keyA] = b;
    } else {
      delete map[keyA];
    }
    saveAssignments(map);
  }

  function onSlotTap(slotKey) {
    if (saving || state.locked) {
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
      placePlayer(selected.playerId, slotKey);
      return;
    }
    if (selected && selected.kind === "slot" && selected.slotKey !== slotKey) {
      if (slot.player_id) {
        swapSlots(selected.slotKey, slotKey);
      } else {
        var mover = state.assignments[selected.slotKey];
        if (mover) {
          var map = nextAssignments();
          delete map[selected.slotKey];
          map[slotKey] = mover;
          saveAssignments(map);
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
    if (saving || state.locked) {
      return;
    }
    if (selected && selected.kind === "bench" && selected.playerId === playerId) {
      selected = null;
      render();
      return;
    }
    if (selected && selected.kind === "slot" && selected.slotKey) {
      placePlayer(playerId, selected.slotKey);
      return;
    }
    selected = { kind: "bench", playerId: playerId };
    render();
  }

  function onSendOff() {
    if (saving || state.locked) {
      return;
    }
    if (selected && selected.kind === "slot" && selected.slotKey) {
      clearSlot(selected.slotKey);
    }
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
    offButton.addEventListener("click", onSendOff);
  }

  var startButton = document.getElementById("scm-start-period");
  var undoButton = document.getElementById("scm-undo");

  function runSetupAction(url) {
    if (saving) {
      return;
    }
    saving = true;
    showStatus("Saving…");
    postJson(url, {})
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

  if (startButton) {
    startButton.addEventListener("click", function () {
      runSetupAction(state.startUrl);
    });
  }

  if (undoButton) {
    undoButton.addEventListener("click", function () {
      runSetupAction(state.undoUrl);
    });
  }

  render();
})();
