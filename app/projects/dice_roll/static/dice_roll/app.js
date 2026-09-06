/**
 * dice_roll — 1, 2, or 5 six-sided dice; large roll surface; per-die hold (Yahtzee).
 */
(function () {
    "use strict";

    var STORAGE_KEY = "dice_roll_count";
    var SCATTER_KEY = "dice_roll_scatter";
    var VALID_COUNTS = [1, 2, 5];

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
        var rollPingTimer = null;
        var badge = document.getElementById("diceroll-roll-badge");

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
                randomPastelBackdrop(surface);
                rollCount += 1;
                if (badge) {
                    badge.textContent = "Roll " + rollCount;
                }
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

        function onViewportChange() {
            if (getScatter()) {
                applyPositions();
            }
        }

        window.addEventListener("resize", onViewportChange);

        syncStateLength();
        randomPastelBackdrop(surface);
        render();
        requestAnimationFrame(function () {
            ensureScatterPositions();
        });

        window.addEventListener("pageshow", function () {
            syncStateLength();
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

        updateSelected();
        updateScatterChoices();
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
