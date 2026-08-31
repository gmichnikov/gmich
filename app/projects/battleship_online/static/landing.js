(function () {
    "use strict";

    var PLAYER_KEY = "bso_player_id";
    var CODE_RE = /^[A-HJ-NP-Z2-9]{6}$/;
    var createBtn = document.getElementById("bsoCreateBtn");
    var vsCpuBtn = document.getElementById("bsoVsCpuBtn");
    var joinForm = document.getElementById("bsoJoinForm");
    var joinInput = document.getElementById("bsoJoinCode");
    var errorEl = document.getElementById("bsoLandingError");

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

    function clearError() {
        errorEl.hidden = true;
    }

    function goToRoom(code) {
        window.location.href = "/battleship-online/room/" + encodeURIComponent(code);
    }

    function createRoom(vsCpu) {
        var btn = vsCpu ? vsCpuBtn : createBtn;
        btn.disabled = true;
        fetch("/battleship-online/rooms", {
            method: "POST",
            headers: {
                "X-CSRFToken": BSO_CSRF_TOKEN,
                "X-BSO-Player-Id": getPlayerId(),
                "Content-Type": "application/json",
            },
            credentials: "same-origin",
            body: JSON.stringify({ vs_cpu: !!vsCpu }),
        })
            .then(function (response) {
                return response.json().catch(function () { return {}; });
            })
            .then(function (data) {
                if (data.code) {
                    goToRoom(data.code);
                } else {
                    showError(data.error || "Could not create a game. Please try again.");
                    btn.disabled = false;
                }
            })
            .catch(function () {
                showError("Could not create a game. Please try again.");
                btn.disabled = false;
            });
    }

    createBtn.addEventListener("click", function () {
        createRoom(false);
    });

    vsCpuBtn.addEventListener("click", function () {
        createRoom(true);
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
        clearError();
        goToRoom(code);
    });
})();
