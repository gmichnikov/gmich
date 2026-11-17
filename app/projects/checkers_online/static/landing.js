(function () {
    "use strict";

    var PLAYER_KEY = "chk_player_id";
    var createBtn = document.getElementById("chkCreateBtn");
    var vsCpuBtn = document.getElementById("chkVsCpuBtn");
    var difficulty = "medium";
    var pieceColor = "black";
    var firstMove = "you";
    var joinForm = document.getElementById("chkJoinForm");
    var joinInput = document.getElementById("chkJoinCode");
    var errorEl = document.getElementById("chkLandingError");

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
            } catch (err2) {
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
        window.location.href = "/checkers-online/room/" + encodeURIComponent(code);
    }

    function markSegment(group, attribute, value) {
        group.querySelectorAll(".chk-segment-btn").forEach(function (btn) {
            var selected = btn.dataset[attribute] === value;
            btn.classList.toggle("chk-segment-active", selected);
            btn.setAttribute("aria-pressed", selected ? "true" : "false");
        });
    }

    document.getElementById("chkDifficulty").addEventListener("click", function (event) {
        var choice = event.target.dataset.difficulty;
        if (!choice) {
            return;
        }
        difficulty = choice;
        markSegment(event.currentTarget, "difficulty", difficulty);
    });

    document.getElementById("chkColor").addEventListener("click", function (event) {
        var choice = event.target.dataset.color;
        if (!choice) {
            return;
        }
        pieceColor = choice;
        markSegment(event.currentTarget, "color", pieceColor);
    });

    document.getElementById("chkFirst").addEventListener("click", function (event) {
        var choice = event.target.dataset.first;
        if (!choice) {
            return;
        }
        firstMove = choice;
        markSegment(event.currentTarget, "first", firstMove);
    });

    function createRoom(vsCpu) {
        var button = vsCpu ? vsCpuBtn : createBtn;
        button.disabled = true;
        var body = vsCpu
            ? { vs_cpu: true, difficulty: difficulty, first: firstMove, color: pieceColor }
            : {};
        fetch("/checkers-online/rooms", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": CHK_CSRF_TOKEN,
                "X-CHK-Player-Id": getPlayerId(),
            },
            credentials: "same-origin",
            body: JSON.stringify(body),
        })
            .then(function (response) {
                return response.json().catch(function () { return {}; });
            })
            .then(function (data) {
                if (data.code) {
                    goToRoom(data.code);
                } else {
                    showError(data.error || "Could not create a game. Please try again.");
                    button.disabled = false;
                }
            })
            .catch(function () {
                showError("Could not create a game. Please try again.");
                button.disabled = false;
            });
    }

    createBtn.addEventListener("click", function () {
        createRoom(false);
    });

    vsCpuBtn.addEventListener("click", function () {
        createRoom(true);
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
