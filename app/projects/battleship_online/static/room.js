(function () {
    "use strict";

    var POLL_MS = 1000;
    var GRID_SIZE = 10;
    var COLUMN_LABELS = "ABCDEFGHIJ".split("");
    var SHIP_NAMES = ["Carrier", "Battleship", "Cruiser", "Submarine", "Destroyer"];
    var PLAYER_KEY = "bso_player_id";

    var pollTimer = null;
    var sinkToastTimer = null;
    var isFiring = false;
    var isSavingName = false;
    var isPlacementAction = false;
    var hasJoined = false;
    var nameDirty = false;
    var pendingName = null;
    var lastState = null;
    var selectedShipId = 0;

    var statusEl = document.getElementById("bsoStatusMessage");
    var sinkToastEl = document.getElementById("bsoSinkToast");
    var shareLinkInput = document.getElementById("bsoShareLink");
    var shareRow = document.getElementById("bsoShareRow");
    var copyBtn = document.getElementById("bsoCopyBtn");
    var spectatorBadge = document.getElementById("bsoSpectatorBadge");
    var rematchBtn = document.getElementById("bsoRematchBtn");
    var nameRow = document.getElementById("bsoNameRow");
    var nameInput = document.getElementById("bsoNameInput");
    var nameSaveBtn = document.getElementById("bsoNameSaveBtn");
    var opponentLabel = document.getElementById("bsoOpponentLabel");
    var placementActions = document.getElementById("bsoPlacementActions");
    var shipList = document.getElementById("bsoShipList");
    var shuffleBtn = document.getElementById("bsoShuffleBtn");
    var readyBtn = document.getElementById("bsoReadyBtn");
    var rotateBtn = document.getElementById("bsoRotateBtn");
    var moveUpBtn = document.getElementById("bsoMoveUp");
    var moveDownBtn = document.getElementById("bsoMoveDown");
    var moveLeftBtn = document.getElementById("bsoMoveLeft");
    var moveRightBtn = document.getElementById("bsoMoveRight");
    var playerBoards = document.getElementById("bsoPlayerBoards");
    var ownPanel = document.getElementById("bsoOwnPanel");
    var ownTitle = document.getElementById("bsoOwnTitle");
    var ownGrid = document.getElementById("bsoOwnGrid");
    var targetPanel = document.getElementById("bsoTargetPanel");
    var targetGrid = document.getElementById("bsoTargetGrid");
    var spectatorBoards = document.getElementById("bsoSpectatorBoards");

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
        return "/battleship-online/room/" + encodeURIComponent(BSO_ROOM_CODE) + path;
    }

    function apiRequest(method, path, body) {
        var headers = {
            Accept: "application/json",
            "X-BSO-Player-Id": getPlayerId(),
        };
        var options = { method: method, headers: headers, credentials: "same-origin" };
        if (method !== "GET") {
            headers["X-CSRFToken"] = BSO_CSRF_TOKEN;
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
        return (state.names && state.names[seat]) || ("Player " + seat);
    }

    function opponentSeat(state) {
        if (!state.your_seat) {
            return null;
        }
        return state.your_seat === "X" ? "O" : "X";
    }

    function showSinkToast(message) {
        sinkToastEl.textContent = message;
        sinkToastEl.hidden = false;
        if (sinkToastTimer) {
            clearTimeout(sinkToastTimer);
        }
        sinkToastTimer = setTimeout(function () {
            sinkToastEl.hidden = true;
        }, 3500);
    }

    function handleEvent(data) {
        if (data.event && data.event.type === "sink") {
            showSinkToast("You sunk their " + data.event.ship_name + "!");
        }
    }

    function statusText(state) {
        if (state.status === "waiting") {
            return "Waiting for an opponent\u2026 share the link above.";
        }
        if (state.status === "placement") {
            if (!state.your_seat) {
                return "Players are placing ships\u2026";
            }
            if (state.your_ready && !state.opponent_ready) {
                return "Waiting for your opponent to ready up\u2026";
            }
            if (!state.your_ready) {
                return "Place your ships, then hit Ready.";
            }
            return "Both players ready\u2026";
        }
        if (state.status === "won") {
            if (state.your_seat && state.winner === state.your_seat) {
                return "You sank their fleet!";
            }
            if (state.your_seat) {
                return seatName(state, state.winner) + " wins!";
            }
            return seatName(state, state.winner) + " wins!";
        }
        if (state.status === "battle") {
            var turnName = seatName(state, state.turn);
            if (!state.your_seat) {
                return "Spectating \u2014 " + turnName + "'s turn";
            }
            if (state.turn === state.your_seat) {
                return "Your turn \u2014 fire on the enemy grid.";
            }
            return "Waiting for " + turnName + "\u2026";
        }
        return "";
    }

    function cellClass(cellState) {
        return "bso-cell bso-" + cellState;
    }

    function boardWithSelection(board, selectedId) {
        if (selectedId === null || !board) {
            return board;
        }
        return board.map(function (row) {
            return row.map(function (cell) {
                if (cell.indexOf("ship-") === 0) {
                    var shipId = parseInt(cell.split("-")[1], 10);
                    if (shipId === selectedId) {
                        return "ship-selected";
                    }
                }
                return cell;
            });
        });
    }

    function shipAtCell(state, row, col) {
        if (!state.your_ships) {
            return null;
        }
        for (var i = 0; i < state.your_ships.length; i += 1) {
            var ship = state.your_ships[i];
            for (var j = 0; j < ship.cells.length; j += 1) {
                if (ship.cells[j][0] === row && ship.cells[j][1] === col) {
                    return ship.id;
                }
            }
        }
        return null;
    }

    function renderGrid(container, board, mode, onCellClick) {
        container.innerHTML = "";
        container.style.gridTemplateColumns = "repeat(" + (GRID_SIZE + 1) + ", 1fr)";

        var corner = document.createElement("div");
        corner.className = "bso-label bso-label-corner";
        container.appendChild(corner);

        COLUMN_LABELS.forEach(function (label) {
            var el = document.createElement("div");
            el.className = "bso-label bso-label-col";
            el.textContent = label;
            container.appendChild(el);
        });

        for (var row = 0; row < GRID_SIZE; row += 1) {
            var rowLabel = document.createElement("div");
            rowLabel.className = "bso-label bso-label-row";
            rowLabel.textContent = String(row + 1);
            container.appendChild(rowLabel);

            for (var col = 0; col < GRID_SIZE; col += 1) {
                var cellState = board[row][col];
                var cell = document.createElement("button");
                cell.type = "button";
                cell.className = cellClass(cellState);
                cell.setAttribute("data-row", String(row));
                cell.setAttribute("data-col", String(col));

                if (mode === "target") {
                    cell.disabled = cellState !== "unknown";
                    if (cellState === "unknown") {
                        cell.addEventListener("click", onCellClick);
                    }
                } else if (mode === "placement") {
                    cell.disabled = !!lastState.your_ready;
                    cell.addEventListener("click", onCellClick);
                } else {
                    cell.disabled = true;
                }

                container.appendChild(cell);
            }
        }
    }

    function renderShipList(state) {
        shipList.innerHTML = "";
        if (!state.your_ships) {
            return;
        }
        state.your_ships.forEach(function (ship) {
            var btn = document.createElement("button");
            btn.type = "button";
            btn.className = "bso-ship-btn";
            if (ship.id === selectedShipId) {
                btn.classList.add("bso-ship-btn-selected");
            }
            btn.textContent = SHIP_NAMES[ship.id] + " (" + ship.size + ")";
            btn.disabled = !!state.your_ready || isPlacementAction;
            btn.addEventListener("click", function () {
                selectedShipId = ship.id;
                render(state);
            });
            shipList.appendChild(btn);
        });
    }

    function renderSpectatorBoards(state) {
        spectatorBoards.innerHTML = "";
        var panels = [
            { title: seatName(state, "X") + " fleet", board: state.board_x },
            { title: seatName(state, "X") + " shots", board: state.targeting_x },
            { title: seatName(state, "O") + " fleet", board: state.board_o },
            { title: seatName(state, "O") + " shots", board: state.targeting_o },
        ];
        panels.forEach(function (panel) {
            var wrap = document.createElement("div");
            wrap.className = "bso-board-panel";
            var title = document.createElement("h2");
            title.className = "bso-board-title";
            title.textContent = panel.title;
            var grid = document.createElement("div");
            grid.className = "bso-grid bso-spectator-grid";
            wrap.appendChild(title);
            wrap.appendChild(grid);
            spectatorBoards.appendChild(wrap);
            renderGrid(grid, panel.board, "view", null);
        });
    }

    function canFireNow() {
        return (
            !!lastState &&
            lastState.status === "battle" &&
            lastState.turn === lastState.your_seat
        );
    }

    function inPlacement() {
        return !!lastState && lastState.status === "placement" && !!lastState.your_seat;
    }

    function updatePlacementControls(state) {
        var locked = !!state.your_ready || isPlacementAction;
        shuffleBtn.disabled = locked;
        readyBtn.disabled = locked;
        rotateBtn.disabled = locked || selectedShipId === null;
        moveUpBtn.disabled = locked || selectedShipId === null;
        moveDownBtn.disabled = locked || selectedShipId === null;
        moveLeftBtn.disabled = locked || selectedShipId === null;
        moveRightBtn.disabled = locked || selectedShipId === null;
    }

    function render(state) {
        lastState = state;
        statusEl.textContent = statusText(state);
        statusEl.className = "bso-status-message bso-status-" + state.status;

        var isPlayer = !!state.your_seat;
        var isFinished = state.status === "won";
        rematchBtn.hidden = !(isPlayer && isFinished);
        spectatorBadge.hidden = isPlayer;
        shareRow.hidden = !isPlayer;
        nameRow.hidden = !isPlayer;

        if (isPlayer) {
            nameInput.placeholder = "Player " + state.your_seat;
            if (!nameDirty && document.activeElement !== nameInput) {
                nameInput.value = state.your_name || "";
            }
            var opp = opponentSeat(state);
            if (opp && state.seats[opp]) {
                opponentLabel.textContent = "Playing against: " + seatName(state, opp);
                opponentLabel.hidden = false;
            } else {
                opponentLabel.hidden = true;
            }

            playerBoards.hidden = state.status === "waiting";
            spectatorBoards.hidden = true;

            var placing = state.status === "placement";
            placementActions.hidden = !placing;
            targetPanel.hidden = placing;

            if (state.status !== "waiting") {
                if (placing) {
                    ownTitle.textContent = "Place your fleet";
                    if (state.your_ships && state.your_ships.length && selectedShipId === null) {
                        selectedShipId = state.your_ships[0].id;
                    }
                    renderShipList(state);
                    updatePlacementControls(state);
                    renderGrid(
                        ownGrid,
                        boardWithSelection(state.your_board, selectedShipId),
                        "placement",
                        handlePlacementClick
                    );
                } else {
                    ownTitle.textContent = "Your fleet";
                    selectedShipId = null;
                    renderGrid(ownGrid, state.your_board, "view", null);
                    renderGrid(
                        targetGrid,
                        state.targeting,
                        "target",
                        handleTargetClick
                    );
                }
            }
        } else {
            opponentLabel.hidden = true;
            nameRow.hidden = true;
            placementActions.hidden = true;
            playerBoards.hidden = true;
            spectatorBoards.hidden = state.status === "waiting";
            if (state.spectator && state.status !== "waiting") {
                renderSpectatorBoards(state);
            }
        }
    }

    function handlePlacementClick(event) {
        if (!inPlacement() || lastState.your_ready) {
            return;
        }
        var row = parseInt(event.currentTarget.getAttribute("data-row"), 10);
        var col = parseInt(event.currentTarget.getAttribute("data-col"), 10);
        var shipId = shipAtCell(lastState, row, col);
        if (shipId !== null) {
            selectedShipId = shipId;
            render(lastState);
        }
    }

    function handleTargetClick(event) {
        if (isFiring || !canFireNow()) {
            return;
        }
        var row = parseInt(event.currentTarget.getAttribute("data-row"), 10);
        var col = parseInt(event.currentTarget.getAttribute("data-col"), 10);
        isFiring = true;
        apiRequest("POST", "/fire", { row: row, col: col })
            .then(function (data) {
                handleEvent(data);
                render(data);
            })
            .catch(function (err) {
                statusEl.textContent = err.message;
            })
            .then(function () {
                isFiring = false;
            });
    }

    function adjustSelectedShip(action) {
        if (!inPlacement() || lastState.your_ready || selectedShipId === null || isPlacementAction) {
            return;
        }
        isPlacementAction = true;
        updatePlacementControls(lastState);
        apiRequest("POST", "/ship", {
            ship_index: selectedShipId,
            action: action,
        })
            .then(render)
            .catch(function (err) {
                statusEl.textContent = err.message;
            })
            .then(function () {
                isPlacementAction = false;
                if (lastState) {
                    updatePlacementControls(lastState);
                }
            });
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

    function placementRequest(path) {
        if (isPlacementAction) {
            return;
        }
        isPlacementAction = true;
        updatePlacementControls(lastState || {});
        apiRequest("POST", path)
            .then(function (state) {
                if (path === "/shuffle") {
                    selectedShipId = 0;
                }
                render(state);
            })
            .catch(function (err) {
                statusEl.textContent = err.message;
            })
            .then(function () {
                isPlacementAction = false;
                if (lastState) {
                    updatePlacementControls(lastState);
                }
            });
    }

    shuffleBtn.addEventListener("click", function () {
        placementRequest("/shuffle");
    });
    readyBtn.addEventListener("click", function () {
        placementRequest("/ready");
    });
    rotateBtn.addEventListener("click", function () {
        adjustSelectedShip("rotate");
    });
    moveUpBtn.addEventListener("click", function () {
        adjustSelectedShip("up");
    });
    moveDownBtn.addEventListener("click", function () {
        adjustSelectedShip("down");
    });
    moveLeftBtn.addEventListener("click", function () {
        adjustSelectedShip("left");
    });
    moveRightBtn.addEventListener("click", function () {
        adjustSelectedShip("right");
    });

    document.addEventListener("keydown", function (event) {
        if (!inPlacement() || lastState.your_ready || document.activeElement === nameInput) {
            return;
        }
        var key = event.key;
        if (key === "ArrowUp") {
            event.preventDefault();
            adjustSelectedShip("up");
        } else if (key === "ArrowDown") {
            event.preventDefault();
            adjustSelectedShip("down");
        } else if (key === "ArrowLeft") {
            event.preventDefault();
            adjustSelectedShip("left");
        } else if (key === "ArrowRight") {
            event.preventDefault();
            adjustSelectedShip("right");
        } else if (key === " " || key === "Spacebar") {
            event.preventDefault();
            adjustSelectedShip("rotate");
        }
    });

    rematchBtn.addEventListener("click", function () {
        rematchBtn.disabled = true;
        apiRequest("POST", "/rematch")
            .then(function (state) {
                selectedShipId = 0;
                render(state);
            })
            .catch(function (err) {
                statusEl.textContent = err.message;
            })
            .then(function () {
                rematchBtn.disabled = false;
            });
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

    joinThenStart();
})();
