(function () {
    "use strict";

    var POLL_MS = 1000;
    var PLAYER_KEY = "c4o_player_id";
    var ROWS = 6;
    var COLS = 7;

    var pollTimer = null;
    var isMoving = false;
    var isSavingName = false;
    var isSavingColor = false;
    var hasJoined = false;
    var nameDirty = false;
    var pendingName = null;
    var pendingColor = null;
    var lastState = null;
    var colorPickerBuilt = false;
    var boardBuilt = false;
    var lastVersion = null;
    var lastMoveCol = null;
    var hoverCol = null;

    var boardEl = document.getElementById("c4oBoard");
    var statusEl = document.getElementById("c4oStatusMessage");
    var shareLinkInput = document.getElementById("c4oShareLink");
    var shareRow = document.getElementById("c4oShareRow");
    var copyBtn = document.getElementById("c4oCopyBtn");
    var spectatorBadge = document.getElementById("c4oSpectatorBadge");
    var rematchBtn = document.getElementById("c4oRematchBtn");
    var nameRow = document.getElementById("c4oNameRow");
    var nameInput = document.getElementById("c4oNameInput");
    var nameSaveBtn = document.getElementById("c4oNameSaveBtn");
    var colorRow = document.getElementById("c4oColorRow");
    var colorPicker = document.getElementById("c4oColorPicker");
    var opponentLabel = document.getElementById("c4oOpponentLabel");

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
        return "/connect4-online/room/" + encodeURIComponent(C4O_ROOM_CODE) + path;
    }

    function apiRequest(method, path, body) {
        var headers = {
            Accept: "application/json",
            "X-C4O-Player-Id": getPlayerId(),
        };
        var options = { method: method, headers: headers, credentials: "same-origin" };
        if (method !== "GET") {
            headers["X-CSRFToken"] = C4O_CSRF_TOKEN;
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

    function seatColor(state, seat) {
        if (state.colors && state.colors[seat]) {
            return state.colors[seat];
        }
        return seat === "X" ? "red" : "yellow";
    }

    function colorLabel(state, colorId) {
        if (state.color_labels && state.color_labels[colorId]) {
            return state.color_labels[colorId];
        }
        return colorId.charAt(0).toUpperCase() + colorId.slice(1);
    }

    function discClass(colorId) {
        return "c4o-disc-" + colorId;
    }

    function opponentSeat(state) {
        if (!state.your_seat) {
            return null;
        }
        return state.your_seat === "X" ? "O" : "X";
    }

    function lowestEmptyRow(board, col) {
        for (var row = ROWS - 1; row >= 0; row--) {
            if (!board[row][col]) {
                return row;
            }
        }
        return -1;
    }

    function columnPlayable(board, col) {
        return lowestEmptyRow(board, col) !== -1;
    }

    function isWinningCell(state, row, col) {
        if (!state.winning_cells) {
            return false;
        }
        return state.winning_cells.some(function (cell) {
            return cell[0] === row && cell[1] === col;
        });
    }

    function buildBoardOnce() {
        if (boardBuilt) {
            return;
        }
        for (var row = 0; row < ROWS; row++) {
            for (var col = 0; col < COLS; col++) {
                var cell = document.createElement("div");
                cell.className = "c4o-cell";
                cell.dataset.row = String(row);
                cell.dataset.col = String(col);
                cell.addEventListener("click", function (event) {
                    handleColumnClick(parseInt(event.currentTarget.dataset.col, 10));
                });
                cell.addEventListener("mouseenter", function (event) {
                    handleColumnHover(parseInt(event.currentTarget.dataset.col, 10), true);
                });
                cell.addEventListener("mouseleave", function (event) {
                    handleColumnHover(parseInt(event.currentTarget.dataset.col, 10), false);
                });
                boardEl.appendChild(cell);
            }
        }
        boardBuilt = true;
    }

    function getCell(row, col) {
        return boardEl.querySelector(
            '.c4o-cell[data-row="' + row + '"][data-col="' + col + '"]'
        );
    }

    function clearPreview() {
        boardEl.querySelectorAll(".c4o-cell.c4o-preview").forEach(function (cell) {
            cell.classList.remove("c4o-preview");
            ["red", "yellow", "orange", "green", "blue", "purple"].forEach(function (c) {
                cell.classList.remove("c4o-disc-" + c);
            });
        });
    }

    function statusText(state) {
        if (state.status === "waiting") {
            return "Waiting for an opponent to join\u2026 share the link above.";
        }
        if (state.status === "won") {
            var winnerName = seatName(state, state.winner);
            var winnerColor = colorLabel(state, seatColor(state, state.winner));
            if (state.your_seat && state.winner === state.your_seat) {
                return "You win!";
            }
            if (state.your_seat) {
                return winnerName + " (" + winnerColor + ") wins!";
            }
            return winnerName + " (" + winnerColor + ") wins!";
        }
        if (state.status === "draw") {
            return "It's a draw!";
        }
        var turnName = seatName(state, state.turn);
        var turnColor = colorLabel(state, seatColor(state, state.turn));
        if (!state.your_seat) {
            return "Spectating \u2014 " + turnName + "'s turn (" + turnColor + ")";
        }
        if (state.turn === state.your_seat) {
            return "Your turn";
        }
        return "Waiting for " + turnName + "\u2026";
    }

    function updateStatusBar(state) {
        statusEl.textContent = "";
        statusEl.className = "c4o-status-message c4o-status-" + state.status;

        if (state.status === "active" || state.status === "won") {
            var turnSeat = state.status === "won" ? state.winner : state.turn;
            if (turnSeat) {
                var disc = document.createElement("span");
                disc.className = "c4o-turn-disc " + discClass(seatColor(state, turnSeat));
                statusEl.appendChild(disc);
            }
        }

        var text = document.createElement("span");
        text.textContent = statusText(state);
        statusEl.appendChild(text);
    }

    function updateColorPicker(state) {
        if (!state.your_seat) {
            colorRow.hidden = true;
            return;
        }
        colorRow.hidden = false;

        var current = state.your_color || seatColor(state, state.your_seat);
        var opponent = state.opponent_color;
        var buttons = colorPicker.querySelectorAll(".c4o-color-btn");

        if (!colorPickerBuilt && state.allowed_colors && state.allowed_colors.length) {
            state.allowed_colors.forEach(function (colorId) {
                var btn = document.createElement("button");
                btn.type = "button";
                btn.className = "c4o-color-btn c4o-disc-" + colorId;
                btn.dataset.color = colorId;
                btn.title = colorLabel(state, colorId);
                btn.addEventListener("click", function () {
                    pickColor(colorId);
                });
                colorPicker.appendChild(btn);
            });
            colorPickerBuilt = true;
            buttons = colorPicker.querySelectorAll(".c4o-color-btn");
        }

        buttons.forEach(function (btn) {
            var colorId = btn.dataset.color;
            btn.classList.toggle("c4o-color-selected", colorId === current);
            var taken = colorId === opponent;
            btn.disabled = taken || isSavingColor;
            btn.classList.toggle("c4o-color-taken", taken);
            btn.title = taken ? "Taken by your opponent" : colorLabel(state, colorId);
        });
    }

    function renderBoard(state) {
        buildBoardOnce();
        var board = state.board;
        var animateDrop = state.version !== lastVersion && lastVersion !== null;

        boardEl.querySelectorAll(".c4o-cell").forEach(function (cell) {
            var row = parseInt(cell.dataset.row, 10);
            var col = parseInt(cell.dataset.col, 10);
            var seat = board[row][col];
            var colorClasses = ["c4o-disc-red", "c4o-disc-yellow", "c4o-disc-orange", "c4o-disc-green", "c4o-disc-blue", "c4o-disc-purple"];

            colorClasses.forEach(function (cls) {
                cell.classList.remove(cls);
            });
            cell.classList.remove("c4o-winning", "c4o-dropped", "c4o-col-playable", "c4o-preview");

            if (seat) {
                cell.classList.add(discClass(seatColor(state, seat)));
                if (isWinningCell(state, row, col)) {
                    cell.classList.add("c4o-winning");
                }
            } else if (canMoveNow(state) && columnPlayable(board, col)) {
                cell.classList.add("c4o-col-playable");
            }
        });

        if (animateDrop && lastMoveCol !== null) {
            for (var r = ROWS - 1; r >= 0; r--) {
                if (board[r][lastMoveCol]) {
                    var landed = getCell(r, lastMoveCol);
                    if (landed) {
                        landed.classList.add("c4o-dropped");
                    }
                    break;
                }
            }
        }

        if (hoverCol !== null && canMoveNow(state)) {
            showPreview(state, hoverCol);
        }

        boardEl.classList.toggle("c4o-board-interactive", canMoveNow(state));
        lastVersion = state.version;
        lastMoveCol = null;
    }

    function showPreview(state, col) {
        clearPreview();
        if (!canMoveNow(state)) {
            return;
        }
        var row = lowestEmptyRow(state.board, col);
        if (row === -1) {
            return;
        }
        var cell = getCell(row, col);
        if (cell && !state.board[row][col]) {
            cell.classList.add("c4o-preview", discClass(state.your_color || seatColor(state, state.your_seat)));
        }
    }

    function render(state) {
        lastState = state;
        updateStatusBar(state);
        renderBoard(state);

        var isPlayer = !!state.your_seat;
        var isFinished = state.status === "won" || state.status === "draw";
        rematchBtn.hidden = !(isPlayer && isFinished);
        spectatorBadge.hidden = isPlayer;
        shareRow.hidden = !isPlayer;
        nameRow.hidden = !isPlayer;

        if (isPlayer) {
            nameInput.placeholder = "Player " + state.your_seat;
            if (!nameDirty && document.activeElement !== nameInput) {
                nameInput.value = state.your_name || "";
            }
            updateColorPicker(state);
            var opp = opponentSeat(state);
            if (opp && state.seats[opp]) {
                opponentLabel.textContent =
                    "Playing against: " +
                    seatName(state, opp) +
                    " (" +
                    colorLabel(state, seatColor(state, opp)) +
                    ")";
                opponentLabel.hidden = false;
            } else {
                opponentLabel.hidden = true;
            }
        } else {
            colorRow.hidden = true;
            opponentLabel.hidden = true;
        }
    }

    function canMoveNow(state) {
        state = state || lastState;
        return (
            !!state &&
            state.status === "active" &&
            state.turn === state.your_seat
        );
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
        if (pendingColor !== null) {
            var color = pendingColor;
            pendingColor = null;
            chain = chain.then(function () {
                return apiRequest("POST", "/color", { color: color });
            });
        }
        return chain.then(render);
    }

    function joinThenStart() {
        apiRequest("POST", "/join")
            .then(function (state) {
                hasJoined = true;
                return flushPending(state);
            })
            .then(function () {
                startPolling();
            })
            .catch(function (err) {
                statusEl.textContent = err.message || "Could not join this room.";
            });
    }

    function handleColumnClick(col) {
        if (isMoving || !canMoveNow()) {
            return;
        }
        if (!columnPlayable(lastState.board, col)) {
            return;
        }
        isMoving = true;
        lastMoveCol = col;
        hoverCol = null;
        clearPreview();
        apiRequest("POST", "/move", { col: col })
            .then(render)
            .catch(function (err) {
                statusEl.textContent = err.message;
                lastMoveCol = null;
            })
            .then(function () {
                isMoving = false;
            });
    }

    function handleColumnHover(col, isEntering) {
        if (!canMoveNow()) {
            return;
        }
        if (isEntering) {
            hoverCol = col;
            showPreview(lastState, col);
        } else if (hoverCol === col) {
            hoverCol = null;
            clearPreview();
        }
    }

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
                /* selection visible for manual copy */
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

    function pickColor(colorId) {
        if (isSavingColor) {
            return;
        }
        if (lastState && colorId === lastState.your_color) {
            return;
        }
        if (!hasJoined) {
            pendingColor = colorId;
            if (lastState) {
                render(lastState);
            }
            return;
        }
        isSavingColor = true;
        if (lastState) {
            updateColorPicker(lastState);
        }
        apiRequest("POST", "/color", { color: colorId })
            .then(render)
            .catch(function (err) {
                statusEl.textContent = err.message;
            })
            .then(function () {
                isSavingColor = false;
                if (lastState) {
                    updateColorPicker(lastState);
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
        lastVersion = null;
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
