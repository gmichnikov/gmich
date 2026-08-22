(function () {
    "use strict";

    var POLL_MS = 1000;
    var SYMBOLS = { X: "\u274C", O: "\u2B55" };
    var PLAYER_KEY = "ttto_player_id";

    var pollTimer = null;
    var isMoving = false;
    var isSavingName = false;
    var lastState = null;

    var boardEl = document.getElementById("tttoBoard");
    var cells = boardEl.querySelectorAll(".ttto-cell");
    var statusEl = document.getElementById("tttoStatusMessage");
    var shareLinkInput = document.getElementById("tttoShareLink");
    var shareRow = document.getElementById("tttoShareRow");
    var copyBtn = document.getElementById("tttoCopyBtn");
    var spectatorBadge = document.getElementById("tttoSpectatorBadge");
    var rematchBtn = document.getElementById("tttoRematchBtn");
    var nameRow = document.getElementById("tttoNameRow");
    var nameInput = document.getElementById("tttoNameInput");
    var nameSaveBtn = document.getElementById("tttoNameSaveBtn");
    var opponentLabel = document.getElementById("tttoOpponentLabel");

    shareLinkInput.value = window.location.href;

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

    function apiUrl(path) {
        return "/tic-tac-toe-online/room/" + encodeURIComponent(TTTO_ROOM_CODE) + path;
    }

    function apiRequest(method, path, body) {
        var headers = {
            Accept: "application/json",
            "X-TTTO-Player-Id": getPlayerId(),
        };
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

    function seatName(state, seat) {
        if (state.names && state.names[seat]) {
            return state.names[seat];
        }
        return "Player " + seat;
    }

    function opponentSeat(state) {
        if (!state.your_seat) {
            return null;
        }
        return state.your_seat === "X" ? "O" : "X";
    }

    function statusText(state) {
        if (state.status === "waiting") {
            return "Waiting for an opponent to join\u2026 share the link above.";
        }
        if (state.status === "won") {
            var winnerName = seatName(state, state.winner);
            if (state.your_seat && state.winner === state.your_seat) {
                return "You win!";
            }
            if (state.your_seat) {
                return winnerName + " wins!";
            }
            return winnerName + " wins!";
        }
        if (state.status === "draw") {
            return "It's a draw!";
        }
        var turnName = seatName(state, state.turn);
        if (!state.your_seat) {
            return "Spectating \u2014 " + turnName + "'s turn";
        }
        if (state.turn === state.your_seat) {
            return "Your turn (" + SYMBOLS[state.your_seat] + ")";
        }
        return "Waiting for " + turnName + "\u2026";
    }

    function render(state) {
        lastState = state;
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

        boardEl.classList.toggle("ttto-board-interactive", canMoveNow());

        var isPlayer = !!state.your_seat;
        var isFinished = state.status === "won" || state.status === "draw";
        rematchBtn.hidden = !(isPlayer && isFinished);
        spectatorBadge.hidden = isPlayer;
        shareRow.hidden = !isPlayer;
        nameRow.hidden = !isPlayer;

        if (isPlayer) {
            nameInput.placeholder = "Player " + state.your_seat;
            if (document.activeElement !== nameInput) {
                nameInput.value = state.your_name || "";
            }
            var opp = opponentSeat(state);
            if (opp && state.seats[opp]) {
                opponentLabel.textContent = "Playing against: " + seatName(state, opp);
                opponentLabel.hidden = false;
            } else {
                opponentLabel.hidden = true;
            }
        } else {
            opponentLabel.hidden = true;
        }
    }

    function poll() {
        apiRequest("GET", "/state").then(render).catch(function () {
            statusEl.textContent = "Connection issue \u2014 retrying\u2026";
        });
    }

    function joinThenStart() {
        apiRequest("POST", "/join")
            .then(function (state) {
                render(state);
                startPolling();
            })
            .catch(function (err) {
                statusEl.textContent = err.message || "Could not join this room.";
            });
    }

    function canMoveNow() {
        return (
            !!lastState &&
            lastState.status === "active" &&
            lastState.turn === lastState.your_seat
        );
    }

    function handleCellClick(event) {
        if (isMoving || !canMoveNow()) {
            return;
        }
        var idx = parseInt(event.currentTarget.getAttribute("data-index"), 10);
        if (lastState.board[idx]) {
            return;
        }
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

    function handleCopyClick() {
        var restoreLabel = copyBtn.textContent;
        function showCopied() {
            copyBtn.textContent = "Copied!";
            setTimeout(function () {
                copyBtn.textContent = restoreLabel;
            }, 1500);
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(shareLinkInput.value).then(showCopied).catch(function () {
                shareLinkInput.select();
            });
        } else {
            shareLinkInput.select();
            shareLinkInput.setSelectionRange(0, 99999);
            try {
                document.execCommand("copy");
                showCopied();
            } catch (err) {
                /* selection is already visible for manual copy */
            }
        }
    }

    copyBtn.addEventListener("click", handleCopyClick);

    function saveName() {
        if (isSavingName) {
            return;
        }
        isSavingName = true;
        nameSaveBtn.disabled = true;
        apiRequest("POST", "/name", { name: nameInput.value })
            .then(render)
            .catch(function (err) {
                statusEl.textContent = err.message;
            })
            .then(function () {
                isSavingName = false;
                nameSaveBtn.disabled = false;
            });
    }

    nameSaveBtn.addEventListener("click", saveName);
    nameInput.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
            event.preventDefault();
            saveName();
        }
    });

    function handleRematchClick() {
        rematchBtn.disabled = true;
        apiRequest("POST", "/rematch")
            .then(render)
            .catch(function (err) {
                statusEl.textContent = err.message;
            })
            .then(function () {
                rematchBtn.disabled = false;
            });
    }

    rematchBtn.addEventListener("click", handleRematchClick);

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

    joinThenStart();
})();
