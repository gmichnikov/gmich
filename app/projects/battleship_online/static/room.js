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
    var mobileBoardTab = "enemy";
    var lastTurnSeen = null;
    var lastOpponentShot = null;
    var tabSwitchTimer = null;
    var TAB_SWITCH_DELAY_MS = 1200;
    var mobileLayout = window.matchMedia("(max-width: 820px)");

    var statusEl = document.getElementById("bsoStatusMessage");
    var sinkToastEl = document.getElementById("bsoSinkToast");
    var playBarEl = document.getElementById("bsoPlayBar");
    var turnBannerEl = document.getElementById("bsoTurnBanner");
    var wrapperEl = document.getElementById("bsoWrapper");
    var boardTabsEl = document.getElementById("bsoBoardTabs");
    var tabEnemyBtn = document.getElementById("bsoTabEnemy");
    var tabOwnBtn = document.getElementById("bsoTabOwn");
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
    var unreadyBtn = document.getElementById("bsoUnreadyBtn");
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
    var targetTitle = document.getElementById("bsoTargetTitle");
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

    function usesMobileBoardTabs(state) {
        return (
            mobileLayout.matches &&
            !!state.your_seat &&
            (state.status === "battle" || state.status === "won")
        );
    }

    function applyMobileBoardTabVisibility() {
        var showEnemy = mobileBoardTab === "enemy";
        targetPanel.classList.toggle("bso-board-panel-hidden", !showEnemy);
        ownPanel.classList.toggle("bso-board-panel-hidden", showEnemy);
        tabEnemyBtn.classList.toggle("bso-board-tab-active", showEnemy);
        tabOwnBtn.classList.toggle("bso-board-tab-active", !showEnemy);
    }

    function scheduleTabSwitchForTurn(state) {
        var targetTab = state.turn === state.your_seat ? "enemy" : "own";
        if (tabSwitchTimer) {
            clearTimeout(tabSwitchTimer);
        }
        tabSwitchTimer = setTimeout(function () {
            tabSwitchTimer = null;
            mobileBoardTab = targetTab;
            applyMobileBoardTabVisibility();
        }, TAB_SWITCH_DELAY_MS);
    }

    function updateMobileBoardTabs(state) {
        var useTabs = usesMobileBoardTabs(state);
        boardTabsEl.hidden = !useTabs;
        playerBoards.classList.toggle("bso-mobile-tabs", useTabs);

        if (!useTabs) {
            if (tabSwitchTimer) {
                clearTimeout(tabSwitchTimer);
                tabSwitchTimer = null;
            }
            ownPanel.classList.remove("bso-board-panel-hidden");
            targetPanel.classList.remove("bso-board-panel-hidden");
            lastTurnSeen = null;
            return;
        }

        if (state.status === "battle") {
            if (lastTurnSeen === null) {
                mobileBoardTab = state.turn === state.your_seat ? "enemy" : "own";
                lastTurnSeen = state.turn;
            } else if (state.turn !== lastTurnSeen) {
                lastTurnSeen = state.turn;
                scheduleTabSwitchForTurn(state);
            }
        }

        applyMobileBoardTabVisibility();
    }

    function setMobileBoardTab(tab) {
        if (tabSwitchTimer) {
            clearTimeout(tabSwitchTimer);
            tabSwitchTimer = null;
        }
        mobileBoardTab = tab;
        applyMobileBoardTabVisibility();
    }

    function updatePlayBar(state) {
        var isPlayer = !!state.your_seat;
        var showBar =
            state.status === "placement" ||
            state.status === "battle" ||
            state.status === "won" ||
            (!!state.spectator && state.status !== "waiting");

        playBarEl.hidden = !showBar;
        wrapperEl.classList.toggle("bso-play-active", showBar);
        turnBannerEl.className = "bso-turn-banner";
        turnBannerEl.innerHTML = "";

        if (!showBar) {
            return;
        }

        var mainText = "";
        var subText = "";
        var bannerClass = "bso-turn-banner";

        if (state.status === "placement") {
            if (!isPlayer) {
                mainText = "Ship placement";
                subText = "Players are arranging fleets";
            } else if (state.your_ready && !state.opponent_ready) {
                bannerClass += " bso-turn-waiting";
                mainText = "Waiting for opponent";
                subText = "They still need to ready up \u2014 tap Unready to adjust ships";
            } else if (!state.your_ready) {
                bannerClass += " bso-turn-yours";
                mainText = "Place your ships";
                subText = "Select a ship, move/rotate, then Ready";
            } else {
                bannerClass += " bso-turn-waiting";
                mainText = "Starting battle\u2026";
            }
        } else if (state.status === "battle") {
            var turnName = seatName(state, state.turn);
            if (!isPlayer) {
                bannerClass += " bso-turn-spectate";
                mainText = turnName + "'s turn";
                subText = "Spectating";
            } else if (state.turn === state.your_seat) {
                bannerClass += " bso-turn-yours";
                mainText = "Your turn";
                if (lastOpponentShot) {
                    subText =
                        "They fired at " +
                        shotCoord(lastOpponentShot.row, lastOpponentShot.col);
                } else {
                    subText = "Fire on enemy waters";
                }
            } else {
                bannerClass += " bso-turn-opponent";
                mainText = turnName + "'s turn";
                subText = "Waiting for their shot";
            }
        } else if (state.status === "won") {
            if (isPlayer && state.winner === state.your_seat) {
                bannerClass += " bso-turn-yours";
                mainText = "You win!";
                subText = "You sank their fleet";
            } else if (isPlayer) {
                bannerClass += " bso-turn-opponent";
                mainText = seatName(state, state.winner) + " wins";
                subText = "Missed ships revealed on enemy waters \u00b7 tap Rematch to play again";
            } else {
                mainText = seatName(state, state.winner) + " wins";
            }
        }

        turnBannerEl.className = bannerClass;
        turnBannerEl.innerHTML =
            '<div class="bso-turn-main">' + mainText + "</div>" +
            (subText ? '<div class="bso-turn-sub">' + subText + "</div>" : "");
    }

    function statusText(state) {
        if (state.status === "waiting") {
            return "Waiting for an opponent\u2026 share the link above.";
        }
        return "";
    }

    function cellClass(cellState) {
        return "bso-cell bso-" + cellState;
    }

    function shotCoord(row, col) {
        return COLUMN_LABELS[col] + String(row + 1);
    }

    function findNewOpponentShot(prevBoard, newBoard) {
        if (!prevBoard || !newBoard) {
            return null;
        }
        for (var row = 0; row < GRID_SIZE; row += 1) {
            for (var col = 0; col < GRID_SIZE; col += 1) {
                var prev = prevBoard[row][col];
                var curr = newBoard[row][col];
                var wasUntargeted = prev === "water" || prev.indexOf("ship") === 0;
                if (wasUntargeted && (curr === "miss" || curr === "hit")) {
                    return { row: row, col: col };
                }
            }
        }
        return null;
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

    function renderGrid(container, board, mode, onCellClick, recentOpponentShot) {
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

                if (
                    recentOpponentShot &&
                    recentOpponentShot.row === row &&
                    recentOpponentShot.col === col
                ) {
                    cell.classList.add("bso-recent-opponent-shot");
                }

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
        var canUnready = !!state.your_ready && !state.opponent_ready;
        var locked = !!state.your_ready || isPlacementAction;
        shuffleBtn.disabled = locked;
        readyBtn.hidden = canUnready;
        readyBtn.disabled = locked;
        unreadyBtn.hidden = !canUnready;
        unreadyBtn.disabled = isPlacementAction;
        rotateBtn.disabled = locked || selectedShipId === null;
        moveUpBtn.disabled = locked || selectedShipId === null;
        moveDownBtn.disabled = locked || selectedShipId === null;
        moveLeftBtn.disabled = locked || selectedShipId === null;
        moveRightBtn.disabled = locked || selectedShipId === null;
    }

    function render(state) {
        var prevYourBoard = lastState && lastState.your_board;
        lastState = state;
        var isPlayer = !!state.your_seat;

        if (state.status === "battle" && state.your_board) {
            var newShot = findNewOpponentShot(prevYourBoard, state.your_board);
            if (newShot) {
                lastOpponentShot = newShot;
            }
        } else if (state.status !== "battle") {
            lastOpponentShot = null;
        }
        var statusMessage = statusText(state);
        statusEl.textContent = statusMessage;
        statusEl.hidden = !statusMessage;
        statusEl.className = "bso-status-message bso-status-" + state.status;
        updatePlayBar(state);
        wrapperEl.classList.toggle("bso-in-battle", isPlayer && state.status === "battle");
        updateMobileBoardTabs(state);

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
            var battling = state.status === "battle";
            playerBoards.classList.toggle("bso-battle-active", battling);
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
                    if (isFinished && state.winner !== state.your_seat) {
                        targetTitle.textContent = "Enemy waters \u2014 ships you missed";
                        targetPanel.classList.remove("bso-panel-active-turn");
                    } else if (battling && state.turn === state.your_seat) {
                        targetTitle.textContent = "Enemy waters \u2014 your turn";
                        targetPanel.classList.add("bso-panel-active-turn");
                    } else {
                        targetTitle.textContent = "Enemy waters";
                        targetPanel.classList.remove("bso-panel-active-turn");
                    }
                    selectedShipId = null;
                    renderGrid(ownGrid, state.your_board, "view", null, lastOpponentShot);
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
            playerBoards.classList.remove("bso-battle-active");
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
    unreadyBtn.addEventListener("click", function () {
        placementRequest("/unready");
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

    tabEnemyBtn.addEventListener("click", function () {
        setMobileBoardTab("enemy");
    });
    tabOwnBtn.addEventListener("click", function () {
        setMobileBoardTab("own");
    });
    mobileLayout.addEventListener("change", function () {
        if (lastState) {
            render(lastState);
        }
    });

    joinThenStart();
})();
