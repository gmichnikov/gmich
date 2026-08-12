(function () {
    "use strict";

    var POLL_MS = 1000;
    var SYMBOLS = { X: "\u274C", O: "\u2B55" };

    var pollTimer = null;
    var isMoving = false;

    var boardEl = document.getElementById("tttoBoard");
    var cells = boardEl.querySelectorAll(".ttto-cell");
    var statusEl = document.getElementById("tttoStatusMessage");
    var shareLinkInput = document.getElementById("tttoShareLink");

    shareLinkInput.value = window.location.href;

    function apiUrl(path) {
        return "/tic-tac-toe-online/room/" + encodeURIComponent(TTTO_ROOM_CODE) + path;
    }

    function apiRequest(method, path, body) {
        var headers = { Accept: "application/json" };
        var options = { method: method, headers: headers, credentials: "same-origin" };
        if (method !== "GET") {
            headers["X-CSRFToken"] = TTTO_CSRF_TOKEN;
        }
        if (body !== undefined) {
            headers["Content-Type"] = "application/json";
            options.body = JSON.stringify(body);
        }
        return fetch(apiUrl(path), options).then(function (response) {
            return response
                .json()
                .catch(function () { return {}; })
                .then(function (data) {
                    if (!response.ok) {
                        throw new Error(data.error || "Something went wrong.");
                    }
                    return data;
                });
        });
    }

    function statusText(state) {
        if (state.status === "waiting") {
            return "Waiting for an opponent to join\u2026 share the link above.";
        }
        if (state.status === "won") {
            if (state.your_seat && state.winner === state.your_seat) {
                return "You win! (" + SYMBOLS[state.winner] + ")";
            }
            if (state.your_seat) {
                return "You lose. (" + SYMBOLS[state.winner] + " wins)";
            }
            return state.winner + " wins! (" + SYMBOLS[state.winner] + ")";
        }
        if (state.status === "draw") {
            return "It's a draw!";
        }
        // active
        if (!state.your_seat) {
            return "Spectating \u2014 " + state.turn + "'s turn";
        }
        if (state.turn === state.your_seat) {
            return "Your turn (" + SYMBOLS[state.your_seat] + ")";
        }
        return "Waiting for opponent's move\u2026";
    }

    function render(state) {
        statusEl.textContent = statusText(state);
        statusEl.className = "ttto-status-message ttto-status-" + state.status;

        cells.forEach(function (cell) {
            var idx = parseInt(cell.getAttribute("data-index"), 10);
            var value = state.board[idx];
            cell.textContent = value ? SYMBOLS[value] : "";
            cell.classList.toggle("ttto-taken", !!value);
            cell.classList.toggle(
                "ttto-winning",
                !!(state.winning_line && state.winning_line.indexOf(idx) !== -1)
            );
        });

        var canMove = state.status === "active" && state.turn === state.your_seat;
        boardEl.classList.toggle("ttto-board-interactive", canMove);
    }

    function poll() {
        apiRequest("GET", "/state").then(render).catch(function () {
            statusEl.textContent = "Connection issue \u2014 retrying\u2026";
        });
    }

    function handleCellClick(event) {
        if (isMoving) {
            return;
        }
        var idx = parseInt(event.currentTarget.getAttribute("data-index"), 10);
        isMoving = true;
        apiRequest("POST", "/move", { cell: idx })
            .then(render)
            .catch(function (err) {
                statusEl.textContent = err.message;
            })
            .then(function () {
                isMoving = false;
            });
    }

    cells.forEach(function (cell) {
        cell.addEventListener("click", handleCellClick);
    });

    function startPolling() {
        if (pollTimer) {
            return;
        }
        poll();
        pollTimer = setInterval(poll, POLL_MS);
    }

    function stopPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    document.addEventListener("visibilitychange", function () {
        if (document.hidden) {
            stopPolling();
        } else {
            startPolling();
        }
    });

    startPolling();
})();
