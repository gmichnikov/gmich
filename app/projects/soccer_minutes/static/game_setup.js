(function () {
  var stateNode = document.getElementById("scm-game-state");
  var pitchRoot = document.getElementById("scm-field-pitch");
  var benchRoot = document.getElementById("scm-bench");
  var attendanceRoot = document.getElementById("scm-attendance");
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
    state.assignments = next.assignments;
    state.bands = next.bands;
    state.bench = next.bench;
    state.attendance = next.attendance;
    state.filled = next.filled;
    state.field_size = next.field_size;
    selected = null;
    render();
  }

  function render() {
    pitchRoot.innerHTML = "";
    state.bands.forEach(function (band) {
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

    if (benchRoot) {
      benchRoot.innerHTML = "";
      if (!state.bench.length) {
        var empty = document.createElement("p");
        empty.className = "scm-muted scm-bench-empty";
        empty.textContent = "No one on the bench.";
        benchRoot.appendChild(empty);
      } else {
        state.bench.forEach(function (person) {
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

    if (attendanceRoot) {
      attendanceRoot.innerHTML = "";
      state.attendance.forEach(function (person) {
        var li = document.createElement("li");
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "scm-attendance-btn";
        if (!person.is_present) {
          btn.classList.add("scm-is-absent");
        }
        btn.setAttribute("data-player-id", String(person.id));
        btn.setAttribute("aria-pressed", person.is_present ? "false" : "true");
        if (person.jersey_number) {
          var jersey = document.createElement("span");
          jersey.className = "scm-jersey";
          jersey.textContent = person.jersey_number;
          btn.appendChild(jersey);
        }
        var name = document.createElement("span");
        name.className = "scm-attendance-name";
        name.textContent = person.full_name;
        btn.appendChild(name);
        var flagEl = document.createElement("span");
        flagEl.className = "scm-attendance-flag";
        flagEl.textContent = person.is_present ? "Here" : "Out";
        btn.appendChild(flagEl);
        li.appendChild(btn);
        attendanceRoot.appendChild(li);
      });
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

  function onAttendanceTap(playerId) {
    if (saving) {
      return;
    }
    var person = null;
    state.attendance.forEach(function (item) {
      if (item.id === playerId) {
        person = item;
      }
    });
    if (!person) {
      return;
    }
    saving = true;
    showStatus("Saving…");
    postJson(state.attendanceUrl, {
      player_id: playerId,
      present: !person.is_present,
    })
      .then(function (data) {
        saving = false;
        if (!data.ok) {
          showStatus(data.error || "Could not update attendance.", true);
          return;
        }
        applyState(data);
        showStatus("");
      })
      .catch(function () {
        saving = false;
        showStatus("Could not update attendance. Check your connection.", true);
      });
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

  if (attendanceRoot) {
    attendanceRoot.addEventListener("click", function (event) {
      var btn = event.target.closest(".scm-attendance-btn");
      if (!btn || !attendanceRoot.contains(btn)) {
        return;
      }
      onAttendanceTap(parseInt(btn.getAttribute("data-player-id"), 10));
    });
  }

  if (offButton) {
    offButton.addEventListener("click", onSendOff);
  }

  render();
})();
