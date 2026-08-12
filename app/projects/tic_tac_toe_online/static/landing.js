(function () {
    "use strict";

    var PLAYER_KEY = "ttto_player_id";
    var createBtn = document.getElementById("tttoCreateBtn");
    var joinForm = document.getElementById("tttoJoinForm");
    var joinInput = document.getElementById("tttoJoinCode");
    var errorEl = document.getElementById("tttoLandingError");

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
        window.location.href = "/tic-tac-toe-online/room/" + encodeURIComponent(code);
    }

    createBtn.addEventListener("click", function () {
        createBtn.disabled = true;
        fetch("/tic-tac-toe-online/rooms", {
            method: "POST",
            headers: {
                "X-CSRFToken": TTTO_CSRF_TOKEN,
                "X-TTTO-Player-Id": getPlayerId(),
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
