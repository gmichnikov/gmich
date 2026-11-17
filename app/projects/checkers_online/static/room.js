(function () {
    "use strict";

    var PLAYER_KEY = "chk_player_id";
    var POLL_MS = 1000;
    var boardEl = document.getElementById("chkBoard");
    var statusEl = document.getElementById("chkStatusMessage");
    var shareRow = document.getElementById("chkShareRow");
    var shareLinkInput = document.getElementById("chkShareLink");
    var copyBtn = document.getElementById("chkCopyBtn");
    var spectatorBadge = document.getElementById("chkSpectatorBadge");
    var nameRow = document.getElementById("chkNameRow");
    var nameInput = document.getElementById("chkNameInput");
    var nameSaveBtn = document.getElementById("chkNameSaveBtn");
    var colorRow = document.getElementById("chkColorRow");
    var colorBlackBtn = document.getElementById("chkColorBlack");
    var colorRedBtn = document.getElementById("chkColorRed");
    var opponentLabel = document.getElementById("chkOpponentLabel");
    var infoHint = document.getElementById("chkInfoHint");
    var cpuSettings = document.getElementById("chkCpuSettings");
    var roomDifficulty = document.getElementById("chkRoomDifficulty");
    var roomFirst = document.getElementById("chkRoomFirst");
    var joinPanel = document.getElementById("chkJoinPanel");
    var joinBtn = document.getElementById("chkJoinBtn");
    var rematchBtn = document.getElementById("chkRematchBtn");

    var lastState = null;
    var selected = null;
    var nameDirty = false;
    var pollTimer = null;
    var isMoving = false;
    var isJoining = false;

    shareLinkInput.value = window.location.origin + "/checkers-online/room/" + CHK_ROOM_CODE;

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

    function apiRequest(method, path, body) {
        var options = {
            method: method,
            headers: {
                "X-CSRFToken": CHK_CSRF_TOKEN,
                "X-CHK-Player-Id": getPlayerId(),
            },
            credentials: "same-origin",
        };
        if (body !== undefined) {
            options.headers["Content-Type"] = "application/json";
            options.body = JSON.stringify(body);
        }
        return fetch("/checkers-online/room/" + encodeURIComponent(CHK_ROOM_CODE) + path, options)
            .then(function (response) {
                return response.json().catch(function () { return {}; }).then(function (data) {
                    if (!response.ok) {
                        throw new Error(data.error || "Something went wrong.");
                    }
                    return data;
                });
            });
    }

    function seatForColor(state, color) {
        if (state.colors.X === color) {
            return "X";
        }
        if (state.colors.O === color) {
            return "O";
        }
        return null;
    }

    function colorName(color) {
        return color === "red" ? "Red" : "Black";
    }

    function statusText(state) {
        if (!state.your_seat && state.seats.X && state.seats.O) {
            return "Both seats are full.";
        }
        if (!state.your_seat && (!state.seats.X || !state.seats.O)) {
            return "Tap Join game to take the open seat.";
        }
        if (state.status === "waiting") {
            return "Waiting for an opponent… share the link above.";
        }
        if (state.status === "draw") {
            return state.result_text || "Draw.";
        }
        if (state.status === "won") {
            if (state.vs_cpu) {
                return state.your_color === state.winner ? "You win!" : "Computer wins";
            }
            var winnerSeat = seatForColor(state, state.winner);
            var winnerName = winnerSeat ? state.names[winnerSeat] : colorName(state.winner);
            if (state.your_color === state.winner) {
                return "You win!";
            }
            return winnerName + " wins";
        }
        if (state.your_color === state.turn) {
            return "Your turn";
        }
        if (state.vs_cpu) {
            return "Computer's turn";
        }
        var turnSeat = seatForColor(state, state.turn);
        var turnLabel = turnSeat ? state.names[turnSeat] : colorName(state.turn);
        return turnLabel + "'s turn";
    }

    function orientation(state) {
        if (state.your_color === "red") {
            return {
                row: function (visual) { return visual; },
                col: function (visual) { return 7 - visual; },
            };
        }
        return {
            row: function (visual) { return 7 - visual; },
            col: function (visual) { return visual; },
        };
    }

    function pieceClass(cell) {
        if (!cell) {
            return "";
        }
        var king = cell === "B" || cell === "R";
        var color = cell === "b" || cell === "B" ? "black" : "red";
        return "chk-piece chk-piece-" + color + (king ? " chk-king" : "");
    }

    function movesFrom(state, row, col) {
        var moves = [];
        (state.legal_moves || []).forEach(function (move) {
            if (move.from[0] === row && move.from[1] === col) {
                moves.push(move);
            }
        });
        return moves;
    }

    function landingMove(moves, row, col) {
        var found = null;
        moves.forEach(function (move) {
            if (move.to[0] !== row || move.to[1] !== col) {
                return;
            }
            if (!found || move.captures.length > found.captures.length) {
                found = move;
            }
        });
        return found;
    }

    function render(state) {
        if (!lastState || lastState.version !== state.version || lastState.turn !== state.turn) {
            selected = null;
        }
        lastState = state;

        statusEl.textContent = statusText(state);
        var openSeat = !state.your_seat && (!state.seats.X || !state.seats.O);
        joinPanel.hidden = !openSeat;
        joinBtn.disabled = isJoining;

        var isPlayer = !!state.your_seat;
        shareRow.hidden = !isPlayer || !!state.vs_cpu;
        if (infoHint) {
            infoHint.textContent = state.vs_cpu ? "Settings" : "Share & settings";
        }
        cpuSettings.hidden = !state.vs_cpu || !isPlayer;
        updateCpuSettings(state);
        spectatorBadge.hidden = isPlayer || openSeat;
        nameRow.hidden = !isPlayer;
        colorRow.hidden = !isPlayer;
        rematchBtn.hidden = !(isPlayer && (state.status === "won" || state.status === "draw"));
        boardEl.hidden = false;

        if (isPlayer && !nameDirty && document.activeElement !== nameInput) {
            nameInput.value = state.your_name || "";
        }

        colorBlackBtn.classList.toggle("chk-color-active", state.your_color === "black");
        colorRedBtn.classList.toggle("chk-color-active", state.your_color === "red");
        colorBlackBtn.disabled = !state.can_pick_color;
        colorRedBtn.disabled = !state.can_pick_color;

        var oppSeat = state.your_seat === "X" ? "O" : state.your_seat === "O" ? "X" : null;
        if (oppSeat && state.seats[oppSeat]) {
            opponentLabel.hidden = false;
            opponentLabel.textContent =
                "Playing against: " + state.names[oppSeat] + " (" + colorName(state.colors[oppSeat]) + ")";
        } else {
            opponentLabel.hidden = true;
        }

        var orient = orientation(state);
        var selectedMoves = selected ? movesFrom(state, selected.row, selected.col) : [];
        boardEl.innerHTML = "";
        for (var visualRow = 0; visualRow < 8; visualRow += 1) {
            for (var visualCol = 0; visualCol < 8; visualCol += 1) {
                var row = orient.row(visualRow);
                var col = orient.col(visualCol);
                var cell = document.createElement("button");
                cell.type = "button";
                var dark = (row + col) % 2 === 0;
                cell.className = "chk-square " + (dark ? "chk-dark" : "chk-light");
                cell.setAttribute("data-row", String(row));
                cell.setAttribute("data-col", String(col));
                var occupant = state.board[row][col];
                if (occupant) {
                    var piece = document.createElement("span");
                    piece.className = pieceClass(occupant);
                    cell.appendChild(piece);
                }
                if (selected && selected.row === row && selected.col === col) {
                    cell.classList.add("chk-selected");
                }
                var landing = landingMove(selectedMoves, row, col);
                if (landing) {
                    cell.classList.add(landing.captures.length ? "chk-landing-jump" : "chk-landing");
                }
                if (!dark) {
                    cell.disabled = true;
                }
                cell.addEventListener("click", onSquareClick);
                boardEl.appendChild(cell);
            }
        }
    }

    function onSquareClick(event) {
        if (!lastState || lastState.your_color !== lastState.turn || lastState.status !== "active") {
            return;
        }
        var row = parseInt(event.currentTarget.getAttribute("data-row"), 10);
        var col = parseInt(event.currentTarget.getAttribute("data-col"), 10);
        var occupant = lastState.board[row][col];
        var ownPiece = occupant && (
            (lastState.your_color === "black" && (occupant === "b" || occupant === "B")) ||
            (lastState.your_color === "red" && (occupant === "r" || occupant === "R"))
        );
        if (ownPiece) {
            if (selected && selected.row === row && selected.col === col) {
                selected = null;
            } else {
                selected = { row: row, col: col };
            }
            render(lastState);
            return;
        }
        if (!selected) {
            return;
        }
        var move = landingMove(movesFrom(lastState, selected.row, selected.col), row, col);
        if (!move || isMoving) {
            return;
        }
        isMoving = true;
        selected = null;
        var snapshot = lastState;
        var preview = applyLocal(lastState, move);
        render(preview);
        apiRequest("POST", "/move", {
            from: move.from,
            to: move.to,
            captures: move.captures,
        })
            .then(function (state) {
                var cpuMoved = state.vs_cpu && boardsDiffer(preview.board, state.board);
                if (!cpuMoved) {
                    render(state);
                    isMoving = false;
                    return;
                }
                setTimeout(function () {
                    render(state);
                    isMoving = false;
                }, 450);
            })
            .catch(function (err) {
                render(snapshot);
                statusEl.textContent = err.message;
                isMoving = false;
            });
    }

    function boardsDiffer(left, right) {
        for (var row = 0; row < 8; row += 1) {
            for (var col = 0; col < 8; col += 1) {
                if (left[row][col] !== right[row][col]) {
                    return true;
                }
            }
        }
        return false;
    }

    function applyLocal(state, move) {
        var board = state.board.map(function (row) {
            return row.slice();
        });
        var piece = board[move.from[0]][move.from[1]];
        board[move.from[0]][move.from[1]] = null;
        move.captures.forEach(function (cell) {
            board[cell[0]][cell[1]] = null;
        });
        if (move.promote) {
            piece = piece === "b" || piece === "B" ? "B" : "R";
        }
        board[move.to[0]][move.to[1]] = piece;
        var next = Object.assign({}, state);
        next.board = board;
        next.turn = state.turn === "black" ? "red" : "black";
        next.legal_moves = [];
        return next;
    }

    function markSegment(group, attribute, value) {
        if (!group) {
            return;
        }
        group.querySelectorAll(".chk-segment-btn").forEach(function (btn) {
            btn.classList.toggle("chk-segment-active", btn.dataset[attribute] === value);
        });
    }

    function updateCpuSettings(state) {
        if (!state.vs_cpu) {
            return;
        }
        markSegment(roomDifficulty, "difficulty", state.difficulty || "medium");
        markSegment(roomFirst, "first", state.cpu_first ? "computer" : "you");
        var locked = state.status === "active";
        cpuSettings.classList.toggle("chk-cpu-locked", locked);
        cpuSettings.querySelectorAll("button").forEach(function (btn) {
            btn.disabled = locked;
        });
    }

    function postCpuSettings(difficulty, first) {
        if (!lastState || !lastState.vs_cpu || lastState.status === "active") {
            return;
        }
        apiRequest("POST", "/cpu-settings", { difficulty: difficulty, first: first })
            .then(render)
            .catch(function (err) {
                statusEl.textContent = err.message;
            });
    }

    function poll() {
        if (isMoving) {
            return;
        }
        apiRequest("GET", "/state").then(render).catch(function () {
            statusEl.textContent = "Connection issue — retrying…";
        });
    }

    function startPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
        }
        pollTimer = setInterval(poll, POLL_MS);
    }

    joinBtn.addEventListener("click", function () {
        if (isJoining) {
            return;
        }
        isJoining = true;
        joinBtn.disabled = true;
        apiRequest("POST", "/join", {})
            .then(render)
            .catch(function (err) {
                statusEl.textContent = err.message;
            })
            .then(function () {
                isJoining = false;
            });
    });

    copyBtn.addEventListener("click", function () {
        var restore = copyBtn.textContent;
        function showCopied() {
            copyBtn.textContent = "Copied!";
            setTimeout(function () {
                copyBtn.textContent = restore;
            }, 1500);
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(shareLinkInput.value).then(showCopied);
        } else {
            shareLinkInput.select();
        }
    });

    nameInput.addEventListener("input", function () {
        nameDirty = true;
    });

    nameSaveBtn.addEventListener("click", function () {
        nameSaveBtn.disabled = true;
        apiRequest("POST", "/name", { name: nameInput.value })
            .then(function (state) {
                nameDirty = false;
                render(state);
            })
            .catch(function (err) {
                statusEl.textContent = err.message;
            })
            .then(function () {
                nameSaveBtn.disabled = false;
            });
    });

    function chooseColor(color) {
        if (!lastState || !lastState.can_pick_color || lastState.your_color === color) {
            return;
        }
        apiRequest("POST", "/color", { color: color })
            .then(render)
            .catch(function (err) {
                statusEl.textContent = err.message;
            });
    }

    colorBlackBtn.addEventListener("click", function () { chooseColor("black"); });
    colorRedBtn.addEventListener("click", function () { chooseColor("red"); });

    roomDifficulty.addEventListener("click", function (event) {
        var choice = event.target.dataset.difficulty;
        if (!choice || !lastState) {
            return;
        }
        postCpuSettings(choice, lastState.cpu_first ? "computer" : "you");
    });

    roomFirst.addEventListener("click", function (event) {
        var choice = event.target.dataset.first;
        if (!choice || !lastState) {
            return;
        }
        postCpuSettings(lastState.difficulty || "medium", choice);
    });

    rematchBtn.addEventListener("click", function () {
        rematchBtn.disabled = true;
        apiRequest("POST", "/rematch")
            .then(render)
            .catch(function (err) {
                statusEl.textContent = err.message;
            })
            .then(function () {
                rematchBtn.disabled = false;
            });
    });

    apiRequest("GET", "/state")
        .then(function (state) {
            render(state);
            startPolling();
        })
        .catch(function (err) {
            statusEl.textContent = err.message || "Could not load this room.";
        });
})();
