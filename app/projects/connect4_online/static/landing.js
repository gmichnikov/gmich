(function () {
    "use strict";

    var PLAYER_KEY = "c4o_player_id";
    var createBtn = document.getElementById("c4oCreateBtn");
    var vsCpuBtn = document.getElementById("c4oVsCpuBtn");
    var difficulty = "hard";
    var firstMove = "you";
    var joinForm = document.getElementById("c4oJoinForm");
    var joinInput = document.getElementById("c4oJoinCode");
    var errorEl = document.getElementById("c4oLandingError");

    function getPlayerId() {
        var id = null;
        try {
            id = localStorage.getItem(PLAYER_KEY);
        } catch (err) {
            /* ignore */
        }
        if (!id || !/^[a-f0-9]{32}$/.test(id)) {
            id = Array.from(crypto.getRandomValues(new Uint8Array(16)))
                .map(function (b) {
                    return b.toString(16).padStart(2, "0");
                })
                .join("");
            try {
                localStorage.setItem(PLAYER_KEY, id);
            } catch (err) {
                /* ignore */
            }
        }
        return id;
    }

    function showError(message) {
        errorEl.textContent = message;
        errorEl.hidden = false;
    }

    function goToRoom(code) {
        window.location.href = "/connect4-online/room/" + encodeURIComponent(code);
    }

    function markSegment(group, attribute, value) {
        group.querySelectorAll(".c4o-segment-btn").forEach(function (btn) {
            var selected = btn.dataset[attribute] === value;
            btn.classList.toggle("c4o-segment-active", selected);
            btn.setAttribute("aria-pressed", selected ? "true" : "false");
        });
    }

    document.getElementById("c4oDifficulty").addEventListener("click", function (event) {
        var choice = event.target.dataset.difficulty;
        if (!choice) {
            return;
        }
        difficulty = choice;
        markSegment(event.currentTarget, "difficulty", difficulty);
    });

    document.getElementById("c4oFirst").addEventListener("click", function (event) {
        var choice = event.target.dataset.first;
        if (!choice) {
            return;
        }
        firstMove = choice;
        markSegment(event.currentTarget, "first", firstMove);
    });

    vsCpuBtn.addEventListener("click", function () {
        vsCpuBtn.disabled = true;
        fetch("/connect4-online/rooms", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": C4O_CSRF_TOKEN,
                "X-C4O-Player-Id": getPlayerId(),
            },
            credentials: "same-origin",
            body: JSON.stringify({
                vs_cpu: true,
                difficulty: difficulty,
                first: firstMove,
            }),
        })
            .then(function (response) {
                return response.json().catch(function () { return {}; });
            })
            .then(function (data) {
                if (data.code) {
                    goToRoom(data.code);
                } else {
                    showError(data.error || "Could not start a computer game. Please try again.");
                    vsCpuBtn.disabled = false;
                }
            })
            .catch(function () {
                showError("Could not start a computer game. Please try again.");
                vsCpuBtn.disabled = false;
            });
    });

    createBtn.addEventListener("click", function () {
        createBtn.disabled = true;
        fetch("/connect4-online/rooms", {
            method: "POST",
            headers: {
                "X-CSRFToken": C4O_CSRF_TOKEN,
                "X-C4O-Player-Id": getPlayerId(),
            },
            credentials: "same-origin",
        })
            .then(function (response) {
                return response.json().catch(function () { return {}; });
            })
            .then(function (data) {
                if (data.code) {
                    goToRoom(data.code);
                } else {
                    showError(data.error || "Could not create a game. Please try again.");
                    createBtn.disabled = false;
                }
            })
            .catch(function () {
                showError("Could not create a game. Please try again.");
                createBtn.disabled = false;
            });
    });

    joinForm.addEventListener("submit", function (event) {
        event.preventDefault();
        var code = joinInput.value.trim().toUpperCase();
        if (!code) {
            showError("Enter a room code first.");
            return;
        }
        goToRoom(code);
    });
})();
