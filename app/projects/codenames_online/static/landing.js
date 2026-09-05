(function () {
    "use strict";

    var PLAYER_KEY = "cno_player_id";
    var CODE_RE = /^[A-HJ-NP-Z2-9]{6}$/;
    var createBtn = document.getElementById("cnoCreateBtn");
    var joinForm = document.getElementById("cnoJoinForm");
    var joinInput = document.getElementById("cnoJoinCode");
    var errorEl = document.getElementById("cnoLandingError");

    function normalizeCode(value) {
        return value.trim().toUpperCase();
    }

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

    function clearError() {
        errorEl.hidden = true;
    }

    function goToRoom(code) {
        window.location.href = "/codenames-online/room/" + encodeURIComponent(code);
    }

    createBtn.addEventListener("click", function () {
        createBtn.disabled = true;
        fetch("/codenames-online/rooms", {
            method: "POST",
            headers: {
                "X-CSRFToken": CNO_CSRF_TOKEN,
                "X-CNO-Player-Id": getPlayerId(),
                "Content-Type": "application/json",
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
                    showError(data.error || "Could not create a game.");
                    createBtn.disabled = false;
                }
            })
            .catch(function () {
                showError("Could not create a game.");
                createBtn.disabled = false;
            });
    });

    joinInput.addEventListener("input", function () {
        var normalized = normalizeCode(joinInput.value);
        if (normalized !== joinInput.value) {
            joinInput.value = normalized;
        }
        clearError();
    });

    joinForm.addEventListener("submit", function (event) {
        event.preventDefault();
        var code = normalizeCode(joinInput.value);
        if (!code) {
            showError("Enter a room code first.");
            return;
        }
        if (!CODE_RE.test(code)) {
            showError("Enter a valid 6-character room code.");
            return;
        }
        goToRoom(code);
    });
})();
