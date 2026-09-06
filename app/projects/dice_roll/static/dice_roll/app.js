/**
 * dice_roll — 1, 2, or 5 six-sided dice; large roll surface; per-die hold (Yahtzee).
 */
(function () {
    "use strict";

    var STORAGE_KEY = "dice_roll_count";
    var SCATTER_KEY = "dice_roll_scatter";
    var PLAYERS_KEY = "dice_roll_players";
    var VALID_COUNTS = [1, 2, 5];
    var VALID_PLAYER_COUNTS = [0, 2, 3, 4, 5, 6];

    function getCount() {
        var raw = localStorage.getItem(STORAGE_KEY);
        var n = parseInt(raw, 10);
        return VALID_COUNTS.indexOf(n) !== -1 ? n : 5;
    }

    function setCount(n) {
        if (VALID_COUNTS.indexOf(n) !== -1) {
            localStorage.setItem(STORAGE_KEY, String(n));
        }
    }

    /** Default on: missing key means enabled. */
    function getScatter() {
        var raw = localStorage.getItem(SCATTER_KEY);
        return raw === null ? true : raw === "1";
    }

    function setScatter(on) {
        localStorage.setItem(SCATTER_KEY, on ? "1" : "0");
    }

    function defaultPlayers() {
        return { n: 0, names: [], extraSix: false };
    }

    function getPlayers() {
        try {
            var raw = localStorage.getItem(PLAYERS_KEY);
            if (!raw) {
                return defaultPlayers();
            }
            var data = JSON.parse(raw);
            var n = parseInt(data.n, 10);
            if (VALID_PLAYER_COUNTS.indexOf(n) === -1) {
                n = 0;
            }
            var names = Array.isArray(data.names) ? data.names.slice() : [];
            while (names.length < 6) {
                names.push("");
            }
            return {
                n: n,
                names: names,
                extraSix: !!data.extraSix,
            };
        } catch (err) {
            return defaultPlayers();
        }
    }

    function setPlayers(partial) {
        var cur = getPlayers();
        if (partial.n !== undefined) {
            var n = parseInt(partial.n, 10);
            cur.n = VALID_PLAYER_COUNTS.indexOf(n) !== -1 ? n : 0;
        }
        if (partial.names) {
            var i;
            for (i = 0; i < partial.names.length && i < 6; i++) {
                cur.names[i] = String(partial.names[i] || "");
            }
        }
        if (partial.extraSix !== undefined) {
            cur.extraSix = !!partial.extraSix;
        }
        localStorage.setItem(PLAYERS_KEY, JSON.stringify(cur));
    }

    function displayPlayerName(index) {
        var p = getPlayers();
        var name = (p.names[index] || "").trim();
        return name || "Player " + (index + 1);
    }

    /** 3×3 grid cell indices (0–8) that show a pip for each face value */
    var PIP_MAP = {
        1: [4],
        2: [0, 8],
        3: [0, 4, 8],
        4: [0, 2, 6, 8],
        5: [0, 2, 4, 6, 8],
        6: [0, 2, 3, 5, 6, 8],
    };

    function randomFace() {
        return 1 + Math.floor(Math.random() * 6);
    }

    /**
     * New random pastel backdrop each time (like Sorry! card draw) — works on mobile
     * because values snap; no gradient interpolation needed.
     */
    function randomPastelBackdrop(surface) {
        var h = Math.floor(Math.random() * 360);
        var h2 = (h + 32 + Math.floor(Math.random() * 28)) % 360;
        var h3 = (h + 155 + Math.floor(Math.random() * 55)) % 360;
        surface.style.setProperty(
            "--diceroll-bg-1",
            "hsl(" + h + ", 70%, 76%)"
        );
        surface.style.setProperty(
            "--diceroll-bg-2",
            "hsl(" + h2 + ", 48%, 93%)"
        );
        surface.style.setProperty(
            "--diceroll-bg-3",
            "hsl(" + h3 + ", 58%, 83%)"
        );
        surface.style.setProperty(
            "--diceroll-angle",
            154 + Math.floor(Math.random() * 34) + "deg"
        );
    }

    function buildPips(value) {
        var on = {};
        var cells = PIP_MAP[value] || PIP_MAP[1];
        for (var i = 0; i < cells.length; i++) {
            on[cells[i]] = true;
        }
        var frag = document.createDocumentFragment();
        for (var c = 0; c < 9; c++) {
            var pip = document.createElement("span");
            pip.className =
                "diceroll-pip" + (on[c] ? " diceroll-pip--on" : "");
            frag.appendChild(pip);
        }
        return frag;
    }

    function initPlay() {
        var root = document.getElementById("diceroll-play-root");
        var surface = document.getElementById("diceroll-roll-surface");
        var row = document.getElementById("diceroll-dice-row");
        if (!root || !surface || !row) {
            return;
        }

        var state = [];
        var rollCount = 0;
        var rollHistory = [];
        var rollPingTimer = null;
        var badge = document.getElementById("diceroll-roll-badge");
        var historyToggle = document.getElementById("diceroll-history-toggle");
        var historyRoot = document.getElementById("diceroll-history");
        var historyList = document.getElementById("diceroll-history-list");
        var historyEmpty = document.getElementById("diceroll-history-empty");
        var historyClose = document.getElementById("diceroll-history-close");
        var historyCount = document.getElementById("diceroll-history-count");
        var historyOpen = false;
        var turnRoot = document.getElementById("diceroll-turn");
        var turnNow = document.getElementById("diceroll-turn-now");
        var turnNowName = document.getElementById("diceroll-turn-now-name");
        var turnNext = document.getElementById("diceroll-turn-next");
        var turnNextLabel = document.getElementById("diceroll-turn-next-label");
        var turnNextName = document.getElementById("diceroll-turn-next-name");
        var currentPlayer = 0;
        var nextPlayer = 0;
        var hasRolled = false;

        function rollHasSix(indices) {
            for (var i = 0; i < indices.length; i++) {
                var cell = state[indices[i]];
                if (cell && cell.value === 6) {
                    return true;
                }
            }
            return false;
        }

        function advanceTurn(bumped) {
            var players = getPlayers();
            if (players.n < 2) {
                hasRolled = false;
                currentPlayer = 0;
                nextPlayer = 0;
                return;
            }
            if (!hasRolled) {
                currentPlayer = 0;
            } else {
                currentPlayer = nextPlayer;
            }
            hasRolled = true;
            var again = players.extraSix && rollHasSix(bumped);
            nextPlayer = again
                ? currentPlayer
                : (currentPlayer + 1) % players.n;
        }

        function updateTurnBanner() {
            var players = getPlayers();
            var usingTurns = players.n >= 2;
            surface.classList.toggle("diceroll-roll-surface--turn", usingTurns);
            surface.classList.toggle(
                "diceroll-roll-surface--turn-both",
                usingTurns && hasRolled
            );
            if (!turnRoot) {
                return;
            }
            if (!usingTurns) {
                turnRoot.hidden = true;
                surface.setAttribute(
                    "aria-label",
                    "Roll dice. Tap a die to hold or release it for the next roll."
                );
                return;
            }
            turnRoot.hidden = false;
            if (turnNow && turnNowName) {
                if (hasRolled) {
                    turnNow.hidden = false;
                    turnNowName.textContent = displayPlayerName(currentPlayer);
                } else {
                    turnNow.hidden = true;
                    turnNowName.textContent = "";
                }
            }
            if (turnNextName) {
                var nextName = displayPlayerName(hasRolled ? nextPlayer : 0);
                if (hasRolled && nextPlayer === currentPlayer) {
                    turnNextName.textContent = nextName + " · goes again";
                } else {
                    turnNextName.textContent = nextName;
                }
            }
            if (turnNextLabel) {
                turnNextLabel.textContent = hasRolled ? "Next" : "First up";
            }
            if (turnNext) {
                turnNext.hidden = false;
            }
            if (hasRolled) {
                surface.setAttribute(
                    "aria-label",
                    "This roll is " +
                        displayPlayerName(currentPlayer) +
                        ". Next is " +
                        displayPlayerName(nextPlayer) +
                        ". Tap to roll, or tap a die to hold."
                );
            } else {
                surface.setAttribute(
                    "aria-label",
                    displayPlayerName(0) +
                        " is first. Tap to roll, or tap a die to hold."
                );
            }
        }

        function updateHistoryCount() {
            if (!historyCount || !historyToggle) {
                return;
            }
            if (rollHistory.length === 0) {
                historyCount.hidden = true;
                historyCount.textContent = "";
                historyToggle.setAttribute("aria-label", "Open roll history");
                return;
            }
            historyCount.hidden = false;
            historyCount.textContent = String(rollHistory.length);
            historyToggle.setAttribute(
                "aria-label",
                "Open roll history, " + rollHistory.length + " rolls"
            );
        }

        function renderHistory() {
            if (!historyList) {
                return;
            }
            historyList.innerHTML = "";
            if (historyEmpty) {
                historyEmpty.hidden = rollHistory.length > 0;
            }
            for (var i = rollHistory.length - 1; i >= 0; i--) {
                var entry = rollHistory[i];
                var item = document.createElement("li");
                item.className = "diceroll-history-item";

                var meta = document.createElement("div");
                meta.className = "diceroll-history-item-meta";

                var num = document.createElement("span");
                num.className = "diceroll-history-item-n";
                num.textContent = "Roll " + entry.n;
                meta.appendChild(num);

                if (entry.player) {
                    var who = document.createElement("span");
                    who.className = "diceroll-history-item-who";
                    who.textContent = entry.player;
                    meta.appendChild(who);
                }
                item.appendChild(meta);

                var diceRow = document.createElement("div");
                diceRow.className = "diceroll-history-item-dice";
                diceRow.setAttribute("aria-hidden", "true");
                for (var d = 0; d < entry.values.length; d++) {
                    var die = document.createElement("div");
                    die.className = "diceroll-history-die";
                    var pips = document.createElement("div");
                    pips.className = "diceroll-pips";
                    pips.appendChild(buildPips(entry.values[d]));
                    die.appendChild(pips);
                    diceRow.appendChild(die);
                }
                item.appendChild(diceRow);
                item.setAttribute(
                    "aria-label",
                    "Roll " +
                        entry.n +
                        (entry.player ? ", " + entry.player : "") +
                        ", dice showing " +
                        entry.values.join(", ")
                );

                historyList.appendChild(item);
            }
        }

        function recordRoll() {
            var values = [];
            for (var i = 0; i < state.length; i++) {
                values.push(state[i].value);
            }
            var players = getPlayers();
            rollHistory.push({
                n: rollCount,
                values: values,
                player: players.n >= 2 ? displayPlayerName(currentPlayer) : null,
            });
            updateHistoryCount();
            if (historyOpen) {
                renderHistory();
            }
        }

        function setHistoryOpen(open) {
            historyOpen = !!open;
            if (!historyRoot || !historyToggle) {
                return;
            }
            historyRoot.hidden = !historyOpen;
            surface.inert = historyOpen;
            historyToggle.setAttribute(
                "aria-expanded",
                historyOpen ? "true" : "false"
            );
            if (historyOpen) {
                renderHistory();
                historyToggle.setAttribute(
                    "aria-label",
                    rollHistory.length === 0
                        ? "Close roll history"
                        : "Close roll history, " +
                              rollHistory.length +
                              " rolls"
                );
            } else {
                updateHistoryCount();
            }
        }

        function syncStateLength() {
            var n = getCount();
            if (state.length === n) {
                return;
            }
            state = [];
            for (var i = 0; i < n; i++) {
                state.push({ value: randomFace(), held: false, nx: null, ny: null });
            }
        }

        function measureDieSize() {
            var existing = row.querySelector(".diceroll-die");
            if (existing) {
                return existing.offsetWidth;
            }
            var probe = document.createElement("button");
            probe.type = "button";
            probe.className = "diceroll-die";
            probe.style.visibility = "hidden";
            probe.style.position = "absolute";
            row.appendChild(probe);
            var size = probe.offsetWidth || 72;
            row.removeChild(probe);
            return size;
        }

        function getLayoutMetrics() {
            var size = measureDieSize();
            var tagReserve = 24;
            var areaW = row.clientWidth;
            var areaH = row.clientHeight;
            return {
                areaW: areaW,
                areaH: areaH,
                size: size,
                maxX: Math.max(0, areaW - size),
                maxY: Math.max(0, areaH - size - tagReserve),
            };
        }

        function posToPx(cell, m) {
            return {
                x: (cell.nx == null ? 0.5 : cell.nx) * m.maxX,
                y: (cell.ny == null ? 0.5 : cell.ny) * m.maxY,
            };
        }

        function setPosFromPx(cell, x, y, m) {
            cell.nx = m.maxX > 0 ? x / m.maxX : 0.5;
            cell.ny = m.maxY > 0 ? y / m.maxY : 0.5;
        }

        function boxesOverlap(a, b, size, pad) {
            return (
                Math.abs(a.x - b.x) < size + pad &&
                Math.abs(a.y - b.y) < size + pad
            );
        }

        function pickNewPosition(m, occupied, prev) {
            var pad = Math.max(8, m.size * 0.12);
            var minDist = Math.max(
                m.size * 1.15,
                Math.min(m.areaW, m.areaH) * 0.22
            );
            var attempts = 55;

            function tryPick(requireDist, requireClear) {
                var best = null;
                var bestDist = -1;
                for (var i = 0; i < attempts; i++) {
                    var x = m.maxX > 0 ? Math.random() * m.maxX : 0;
                    var y = m.maxY > 0 ? Math.random() * m.maxY : 0;
                    var cand = { x: x, y: y };
                    if (requireClear) {
                        var blocked = false;
                        for (var j = 0; j < occupied.length; j++) {
                            if (boxesOverlap(cand, occupied[j], m.size, pad)) {
                                blocked = true;
                                break;
                            }
                        }
                        if (blocked) {
                            continue;
                        }
                    }
                    var dist = prev
                        ? Math.hypot(x - prev.x, y - prev.y)
                        : minDist;
                    if (requireDist && prev && dist < minDist) {
                        continue;
                    }
                    if (dist > bestDist) {
                        bestDist = dist;
                        best = cand;
                    }
                    if (requireClear && dist >= minDist) {
                        return cand;
                    }
                }
                return best;
            }

            return (
                tryPick(true, true) ||
                tryPick(false, true) ||
                tryPick(false, false) ||
                { x: 0, y: 0 }
            );
        }

        function layoutInitialRow(m) {
            if (m.areaW < 8 || m.areaH < 8) {
                return;
            }
            var n = state.length;
            var gap = Math.min(18, Math.max(8, m.size * 0.16));
            var cols = n;
            var rowW = cols * m.size + Math.max(0, cols - 1) * gap;
            while (cols > 1 && rowW > m.areaW) {
                cols -= 1;
                rowW = cols * m.size + Math.max(0, cols - 1) * gap;
            }
            var rows = Math.ceil(n / Math.max(cols, 1));
            var totalH = rows * m.size + Math.max(0, rows - 1) * gap;
            var startY = Math.max(0, (m.maxY - (totalH - m.size)) / 2);
            for (var i = 0; i < n; i++) {
                var r = Math.floor(i / cols);
                var c = i % cols;
                var inRow = Math.min(cols, n - r * cols);
                var lineW = inRow * m.size + Math.max(0, inRow - 1) * gap;
                var startX = Math.max(0, (m.areaW - lineW) / 2);
                var x = Math.min(m.maxX, startX + c * (m.size + gap));
                var y = Math.min(m.maxY, startY + r * (m.size + gap));
                setPosFromPx(state[i], x, y, m);
            }
        }

        function relocateIndices(indices) {
            var m = getLayoutMetrics();
            if (m.areaW < 8 || m.areaH < 8 || indices.length === 0) {
                return;
            }
            var occupied = [];
            var i;
            for (i = 0; i < state.length; i++) {
                if (indices.indexOf(i) !== -1) {
                    continue;
                }
                if (state[i].nx == null) {
                    continue;
                }
                occupied.push(posToPx(state[i], m));
            }
            for (i = 0; i < indices.length; i++) {
                var cell = state[indices[i]];
                var prev = cell.nx != null ? posToPx(cell, m) : null;
                var next = pickNewPosition(m, occupied, prev);
                setPosFromPx(cell, next.x, next.y, m);
                occupied.push(next);
            }
        }

        function applyPositions() {
            if (!getScatter()) {
                return;
            }
            var m = getLayoutMetrics();
            if (m.areaW < 8 || m.areaH < 8) {
                return;
            }
            var dice = row.querySelectorAll(".diceroll-die");
            for (var i = 0; i < dice.length; i++) {
                var cell = state[i];
                if (!cell || cell.nx == null) {
                    continue;
                }
                var px = posToPx(cell, m);
                dice[i].style.left = Math.round(px.x) + "px";
                dice[i].style.top = Math.round(px.y) + "px";
            }
        }

        function ensureScatterPositions() {
            if (!getScatter()) {
                return;
            }
            var missing = false;
            for (var i = 0; i < state.length; i++) {
                if (state[i].nx == null || state[i].ny == null) {
                    missing = true;
                    break;
                }
            }
            var m = getLayoutMetrics();
            if (missing) {
                layoutInitialRow(m);
            }
            applyPositions();
        }

        function render() {
            var scatter = getScatter();
            surface.classList.toggle("diceroll-roll-surface--scatter", scatter);
            row.innerHTML = "";
            for (var i = 0; i < state.length; i++) {
                (function (index) {
                    var cell = state[index];
                    var btn = document.createElement("button");
                    btn.type = "button";
                    btn.className = "diceroll-die";
                    btn.dataset.index = String(index);
                    if (cell.held) {
                        btn.classList.add("diceroll-die--held");
                    }
                    btn.setAttribute(
                        "aria-label",
                        "Die " +
                            (index + 1) +
                            ", showing " +
                            cell.value +
                            (cell.held ? ", held — tap to release" : " — tap to hold")
                    );
                    btn.setAttribute("aria-pressed", cell.held ? "true" : "false");

                    var pips = document.createElement("div");
                    pips.className = "diceroll-pips";
                    pips.setAttribute("aria-hidden", "true");
                    pips.appendChild(buildPips(cell.value));
                    btn.appendChild(pips);

                    if (cell.held) {
                        var tag = document.createElement("span");
                        tag.className = "diceroll-held-tag";
                        tag.textContent = "Held";
                        btn.appendChild(tag);
                    }

                    row.appendChild(btn);
                })(i);
            }
            ensureScatterPositions();
        }

        function roll() {
            if (historyOpen) {
                return;
            }
            syncStateLength();
            var bumped = [];
            for (var i = 0; i < state.length; i++) {
                if (state[i].held) {
                    continue;
                }
                state[i].value = randomFace();
                bumped.push(i);
            }
            if (bumped.length > 0) {
                advanceTurn(bumped);
                updateTurnBanner();
                randomPastelBackdrop(surface);
                rollCount += 1;
                if (badge) {
                    badge.textContent = "Roll " + rollCount;
                }
                recordRoll();
                if (rollPingTimer !== null) {
                    window.clearTimeout(rollPingTimer);
                    rollPingTimer = null;
                }
                surface.classList.remove("diceroll-roll-surface--roll-ping");
                void surface.offsetWidth;
                surface.classList.add("diceroll-roll-surface--roll-ping");
                rollPingTimer = window.setTimeout(function () {
                    rollPingTimer = null;
                    surface.classList.remove(
                        "diceroll-roll-surface--roll-ping"
                    );
                }, 520);
                if (getScatter()) {
                    surface.classList.add("diceroll-roll-surface--scatter");
                    relocateIndices(bumped);
                }
            }
            render();
            requestAnimationFrame(function () {
                var dice = row.querySelectorAll(".diceroll-die");
                for (var j = 0; j < bumped.length; j++) {
                    var idx = bumped[j];
                    var el = dice[idx];
                    if (!el) {
                        continue;
                    }
                    el.classList.remove("diceroll-die--bump");
                    void el.offsetWidth;
                    el.classList.add("diceroll-die--bump");
                }
            });
        }

        function toggleHold(index) {
            syncStateLength();
            if (index < 0 || index >= state.length) {
                return;
            }
            state[index].held = !state[index].held;
            render();
        }

        function onSurfacePointerDown(ev) {
            if (ev.button !== undefined && ev.button !== 0) {
                return;
            }
            var t = ev.target;
            if (t && t.closest && t.closest(".diceroll-die")) {
                return;
            }
            surface.classList.add("diceroll-roll-surface--pressed");
        }

        function onSurfacePointerUp(ev) {
            surface.classList.remove("diceroll-roll-surface--pressed");
        }

        surface.addEventListener("pointerdown", onSurfacePointerDown);
        surface.addEventListener("pointerup", onSurfacePointerUp);
        surface.addEventListener("pointerleave", onSurfacePointerUp);

        surface.addEventListener("click", function (ev) {
            var die = ev.target.closest && ev.target.closest(".diceroll-die");
            if (die) {
                ev.preventDefault();
                toggleHold(parseInt(die.dataset.index, 10));
                return;
            }
            roll();
        });

        surface.addEventListener("keydown", function (ev) {
            if (ev.key === " " || ev.key === "Enter") {
                ev.preventDefault();
                roll();
            }
        });

        if (historyToggle) {
            historyToggle.addEventListener("click", function (ev) {
                ev.preventDefault();
                ev.stopPropagation();
                setHistoryOpen(!historyOpen);
            });
        }

        if (historyClose) {
            historyClose.addEventListener("click", function (ev) {
                ev.preventDefault();
                ev.stopPropagation();
                setHistoryOpen(false);
                if (historyToggle) {
                    historyToggle.focus();
                }
            });
        }

        if (historyRoot) {
            historyRoot.addEventListener("click", function (ev) {
                if (ev.target === historyRoot) {
                    setHistoryOpen(false);
                    if (historyToggle) {
                        historyToggle.focus();
                    }
                }
            });
        }

        document.addEventListener("keydown", function (ev) {
            if (ev.key === "Escape" && historyOpen) {
                ev.preventDefault();
                setHistoryOpen(false);
                if (historyToggle) {
                    historyToggle.focus();
                }
            }
        });

        updateHistoryCount();

        function onViewportChange() {
            if (getScatter()) {
                applyPositions();
            }
        }

        window.addEventListener("resize", onViewportChange);

        syncStateLength();
        randomPastelBackdrop(surface);
        updateTurnBanner();
        render();
        requestAnimationFrame(function () {
            ensureScatterPositions();
        });

        window.addEventListener("pageshow", function () {
            syncStateLength();
            updateTurnBanner();
            render();
        });
    }

    function initSetup() {
        var root = document.getElementById("diceroll-setup-root");
        if (!root) {
            return;
        }

        var countButtons = root.querySelectorAll(".diceroll-setup-choice[data-count]");
        var scatterButtons = root.querySelectorAll(".diceroll-setup-choice[data-scatter]");
        var playerCountButtons = root.querySelectorAll(".diceroll-setup-player-count");
        var extraSixButtons = root.querySelectorAll(".diceroll-setup-choice[data-extra-six]");
        var playersBlock = document.getElementById("diceroll-setup-players");
        var namesRoot = document.getElementById("diceroll-setup-names");

        function updateSelected() {
            var n = getCount();
            for (var i = 0; i < countButtons.length; i++) {
                var b = countButtons[i];
                var c = parseInt(b.getAttribute("data-count"), 10);
                var sel = c === n;
                b.classList.toggle("diceroll-setup-choice--selected", sel);
                b.setAttribute("aria-pressed", sel ? "true" : "false");
            }
        }

        function updateScatterChoices() {
            var on = getScatter();
            for (var i = 0; i < scatterButtons.length; i++) {
                var b = scatterButtons[i];
                var sel = (b.getAttribute("data-scatter") === "1") === on;
                b.classList.toggle("diceroll-setup-choice--selected", sel);
                b.setAttribute("aria-pressed", sel ? "true" : "false");
            }
        }

        function updateExtraSixChoices() {
            var on = getPlayers().extraSix;
            for (var i = 0; i < extraSixButtons.length; i++) {
                var b = extraSixButtons[i];
                var sel = (b.getAttribute("data-extra-six") === "1") === on;
                b.classList.toggle("diceroll-setup-choice--selected", sel);
                b.setAttribute("aria-pressed", sel ? "true" : "false");
            }
        }

        function renderNameFields() {
            if (!namesRoot || !playersBlock) {
                return;
            }
            var players = getPlayers();
            var using = players.n >= 2;
            playersBlock.hidden = !using;
            namesRoot.innerHTML = "";
            if (!using) {
                return;
            }
            for (var i = 0; i < players.n; i++) {
                (function (index) {
                    var row = document.createElement("label");
                    row.className = "diceroll-setup-name";
                    var num = document.createElement("span");
                    num.className = "diceroll-setup-name-num";
                    num.textContent = String(index + 1);
                    var input = document.createElement("input");
                    input.type = "text";
                    input.className = "diceroll-setup-name-input";
                    input.maxLength = 18;
                    input.autocomplete = "off";
                    input.autocapitalize = "words";
                    input.spellcheck = false;
                    input.placeholder = "Player " + (index + 1);
                    input.value = players.names[index] || "";
                    input.setAttribute("aria-label", "Name for player " + (index + 1));
                    input.addEventListener("input", function () {
                        var names = getPlayers().names;
                        names[index] = this.value;
                        setPlayers({ names: names });
                    });
                    input.addEventListener("keydown", function (ev) {
                        if (ev.key === "Enter") {
                            ev.preventDefault();
                            this.blur();
                        }
                    });
                    row.appendChild(num);
                    row.appendChild(input);
                    namesRoot.appendChild(row);
                })(i);
            }
        }

        function updatePlayerCounts() {
            var n = getPlayers().n;
            for (var i = 0; i < playerCountButtons.length; i++) {
                var b = playerCountButtons[i];
                var c = parseInt(b.getAttribute("data-players"), 10);
                var sel = c === n;
                b.classList.toggle("diceroll-setup-player-count--selected", sel);
                b.setAttribute("aria-pressed", sel ? "true" : "false");
            }
            renderNameFields();
            updateExtraSixChoices();
        }

        for (var j = 0; j < countButtons.length; j++) {
            countButtons[j].addEventListener("click", function () {
                var c = parseInt(this.getAttribute("data-count"), 10);
                setCount(c);
                updateSelected();
            });
        }

        for (var k = 0; k < scatterButtons.length; k++) {
            scatterButtons[k].addEventListener("click", function () {
                setScatter(this.getAttribute("data-scatter") === "1");
                updateScatterChoices();
            });
        }

        for (var p = 0; p < playerCountButtons.length; p++) {
            playerCountButtons[p].addEventListener("click", function () {
                setPlayers({ n: parseInt(this.getAttribute("data-players"), 10) });
                updatePlayerCounts();
            });
        }

        for (var x = 0; x < extraSixButtons.length; x++) {
            extraSixButtons[x].addEventListener("click", function () {
                setPlayers({ extraSix: this.getAttribute("data-extra-six") === "1" });
                updateExtraSixChoices();
            });
        }

        updateSelected();
        updateScatterChoices();
        updatePlayerCounts();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            initPlay();
            initSetup();
        });
    } else {
        initPlay();
        initSetup();
    }
})();
