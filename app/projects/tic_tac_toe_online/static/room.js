(function () {
    "use strict";

    var POLL_MS = 1000;
    var PLAYER_KEY = "ttto_player_id";

    var pollTimer = null;
    var isMoving = false;
    var isSavingName = false;
    var isSavingSymbol = false;
    var isJoining = false;
    var hasJoined = false;
    var nameDirty = false;
    var pendingName = null;
    var pendingSymbol = null;
    var lastState = null;
    var symbolPickerBuilt = false;

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
    var symbolRow = document.getElementById("tttoSymbolRow");
    var symbolPicker = document.getElementById("tttoSymbolPicker");
    var opponentLabel = document.getElementById("tttoOpponentLabel");
    var joinPanel = document.getElementById("tttoJoinPanel");
    var joinBtn = document.getElementById("tttoJoinBtn");

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

    function boardSymbol(state, seat) {
        if (state.symbols && state.symbols[seat]) {
            return state.symbols[seat];
        }
        return seat === "X" ? "\u274C" : "\u2B55";
    }

    function opponentSeat(state) {
        if (!state.your_seat) {
            return null;
        }
        return state.your_seat === "X" ? "O" : "X";
    }

    function bothSeatsFull(state) {
        return !!(state.seats && state.seats.X && state.seats.O);
    }

    function canTakeSeat(state) {
        return !state.your_seat && !bothSeatsFull(state);
    }

    function showGameBoard(state) {
        return !!state.your_seat || bothSeatsFull(state);
    }

    function statusText(state) {
        if (canTakeSeat(state)) {
            return "Tap Join game to take the open seat.";
        }
        if (state.status === "waiting") {
            if (state.your_seat) {
                return "Waiting for an opponent to join\u2026 share the link above.";
            }
            return "Both seats are full.";
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
            return "Your turn (" + boardSymbol(state, state.your_seat) + ")";
        }
        return "Waiting for " + turnName + "\u2026";
    }

    function updateSymbolPicker(state) {
        if (!state.your_seat) {
            symbolRow.hidden = true;
            return;
        }
        symbolRow.hidden = false;

        var current = state.your_symbol || boardSymbol(state, state.your_seat);
        var opponent = state.opponent_symbol;
        var buttons = symbolPicker.querySelectorAll(".ttto-symbol-btn");

        if (!symbolPickerBuilt && state.allowed_symbols && state.allowed_symbols.length) {
            state.allowed_symbols.forEach(function (sym) {
                var btn = document.createElement("button");
                btn.type = "button";
                btn.className = "ttto-symbol-btn";
                btn.textContent = sym;
                btn.dataset.symbol = sym;
                btn.addEventListener("click", function () {
                    pickSymbol(sym);
                });
                symbolPicker.appendChild(btn);
            });
            symbolPickerBuilt = true;
            buttons = symbolPicker.querySelectorAll(".ttto-symbol-btn");
        }

        buttons.forEach(function (btn) {
            var sym = btn.dataset.symbol;
            btn.classList.toggle("ttto-symbol-selected", sym === current);
            var taken = sym === opponent;
            btn.disabled = taken || isSavingSymbol;
            btn.classList.toggle("ttto-symbol-taken", taken);
            btn.title = taken ? "Taken by your opponent" : "";
        });
    }

    function render(state) {
        lastState = state;
        statusEl.textContent = statusText(state);
        statusEl.className = "ttto-status-message ttto-status-" + state.status;

        cells.forEach(function (cell) {
            var idx = parseInt(cell.getAttribute("data-index"), 10);
            var value = state.board[idx];
            cell.textContent = value ? boardSymbol(state, value) : "";
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
        joinPanel.hidden = !canTakeSeat(state);
        joinBtn.disabled = isJoining;
        spectatorBadge.hidden = isPlayer || !bothSeatsFull(state);
        shareRow.hidden = !isPlayer;
        nameRow.hidden = !isPlayer;
        boardEl.hidden = !showGameBoard(state);

        if (isPlayer) {
            nameInput.placeholder = "Player " + state.your_seat;
            if (!nameDirty && document.activeElement !== nameInput) {
                nameInput.value = state.your_name || "";
            }
            updateSymbolPicker(state);
            var opp = opponentSeat(state);
            if (opp && state.seats[opp]) {
                opponentLabel.textContent =
                    "Playing against: " +
                    seatName(state, opp) +
                    " (" +
                    boardSymbol(state, opp) +
                    ")";
                opponentLabel.hidden = false;
            } else {
                opponentLabel.hidden = true;
            }
        } else {
            symbolRow.hidden = true;
            opponentLabel.hidden = true;
        }
    }

    function poll() {
        apiRequest("GET", "/state").then(render).catch(function () {
            statusEl.textContent = "Connection issue \u2014 retrying\u2026";
        });
    }

    function flushPending(state) {
        var chain = Promise.resolve(state);
        if (pendingName !== null) {
            var name = pendingName;
            pendingName = null;
            chain = chain.then(function () {
                return apiRequest("POST", "/name", { name: name });
            });
        }
        if (pendingSymbol !== null) {
            var symbol = pendingSymbol;
            pendingSymbol = null;
            chain = chain.then(function () {
                return apiRequest("POST", "/symbol", { symbol: symbol });
            });
        }
        return chain.then(render);
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
        var name = nameInput.value;
        nameDirty = true;
        if (!hasJoined) {
            pendingName = name;
            return;
        }
        isSavingName = true;
        nameSaveBtn.disabled = true;
        apiRequest("POST", "/name", { name: name })
            .then(function (state) {
                nameDirty = false;
                render(state);
            })
            .catch(function (err) {
                statusEl.textContent = err.message;
            })
            .then(function () {
                isSavingName = false;
                nameSaveBtn.disabled = false;
            });
    }

    function pickSymbol(symbol) {
        if (isSavingSymbol) {
            return;
        }
        if (lastState && symbol === lastState.your_symbol) {
            return;
        }
        if (!hasJoined) {
            pendingSymbol = symbol;
            if (lastState) {
                render(lastState);
            }
            return;
        }
        isSavingSymbol = true;
        if (lastState) {
            updateSymbolPicker(lastState);
        }
        apiRequest("POST", "/symbol", { symbol: symbol })
            .then(render)
            .catch(function (err) {
                statusEl.textContent = err.message;
            })
            .then(function () {
                isSavingSymbol = false;
                if (lastState) {
                    updateSymbolPicker(lastState);
                }
            });
    }

    nameSaveBtn.addEventListener("click", saveName);
    nameInput.addEventListener("input", function () {
        nameDirty = true;
    });
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

    function initRoom() {
        apiRequest("GET", "/state")
            .then(function (state) {
                if (state.your_seat) {
                    hasJoined = true;
                }
                return flushPending(state);
            })
            .then(function () {
                startPolling();
            })
            .catch(function (err) {
                statusEl.textContent = err.message || "Could not load this room.";
            });
    }

    function handleJoinClick() {
        if (isJoining) {
            return;
        }
        isJoining = true;
        joinBtn.disabled = true;
        apiRequest("POST", "/join")
            .then(function (state) {
                if (state.your_seat) {
                    hasJoined = true;
                }
                return flushPending(state);
            })
            .catch(function (err) {
                statusEl.textContent = err.message || "Could not join this room.";
            })
            .then(function () {
                isJoining = false;
                if (lastState) {
                    joinBtn.disabled = !canTakeSeat(lastState);
                }
            });
    }

    joinBtn.addEventListener("click", handleJoinClick);

    initRoom();
})();
