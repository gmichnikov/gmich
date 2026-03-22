/**
 * dice_roll — 1, 2, or 5 six-sided dice; large roll surface; per-die hold (Yahtzee).
 */
(function () {
    "use strict";

    var STORAGE_KEY = "dice_roll_count";
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
                state.push({ value: randomFace(), held: false });
            }
        }

        function render() {
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

        syncStateLength();
        randomPastelBackdrop(surface);
        render();

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

        var buttons = root.querySelectorAll(".diceroll-setup-choice");

        function updateSelected() {
            var n = getCount();
            for (var i = 0; i < buttons.length; i++) {
                var b = buttons[i];
                var c = parseInt(b.getAttribute("data-count"), 10);
                var sel = c === n;
                b.classList.toggle("diceroll-setup-choice--selected", sel);
                b.setAttribute("aria-pressed", sel ? "true" : "false");
            }
        }

        for (var j = 0; j < buttons.length; j++) {
            buttons[j].addEventListener("click", function () {
                var c = parseInt(this.getAttribute("data-count"), 10);
                setCount(c);
                updateSelected();
            });
        }

        updateSelected();
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
