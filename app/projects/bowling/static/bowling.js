/**
 * Bowling — home, setup, and shared game utilities.
 */
(function () {
    "use strict";

    var STORAGE_KEY = "bowling_last_code";
    var POLL_MS = 4000;
    var CODE_PATTERN = /^\d{6}$/;

    var toastTimer = null;
    var pollTimer = null;
    var gameState = null;
    var pendingSave = false;

    function getCsrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute("content") : "";
    }

    function apiRequest(method, url, body) {
        var headers = {
            Accept: "application/json",
        };
        var token = getCsrfToken();
        if (token) {
            headers["X-CSRFToken"] = token;
        }
        var options = {
            method: method,
            headers: headers,
            credentials: "same-origin",
        };
        if (body !== undefined) {
            headers["Content-Type"] = "application/json";
            options.body = JSON.stringify(body);
        }
        return fetch(url, options).then(function (response) {
            return response.json().catch(function () {
                return {};
            }).then(function (data) {
                if (!response.ok) {
                    var message = data.error || "Something went wrong.";
                    throw new Error(message);
                }
                return data;
            });
        });
    }

    function absoluteGameUrl(code) {
        return window.location.origin + "/bowling/" + code;
    }

    function saveLastCode(code) {
        try {
            localStorage.setItem(STORAGE_KEY, code);
        } catch (err) {
            /* ignore storage failures */
        }
    }

    function showToast(message, isError) {
        var toast = document.getElementById("bowling-toast");
        if (!toast) {
            return;
        }
        toast.textContent = message;
        toast.hidden = false;
        toast.classList.toggle("bowling-toast-error", !!isError);
        if (toastTimer) {
            clearTimeout(toastTimer);
        }
        toastTimer = setTimeout(function () {
            toast.hidden = true;
        }, 2800);
    }

    function shareGame(code) {
        var url = absoluteGameUrl(code);
        if (navigator.share) {
            return navigator.share({
                title: "Bowling game",
                text: "Join our bowling game",
                url: url,
            }).catch(function (err) {
                if (err && err.name === "AbortError") {
                    return;
                }
                return copyGameUrl(url);
            });
        }
        return copyGameUrl(url);
    }

    function copyGameUrl(url) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(url).then(function () {
                showToast("Link copied");
            });
        }
        showToast(url);
        return Promise.resolve();
    }

    function normalizeCode(value) {
        return String(value || "").replace(/\D/g, "").slice(0, 6);
    }

    function initHome() {
        var home = document.getElementById("bowling-home");
        if (!home) {
            return;
        }

        var createBtn = document.getElementById("bowling-create-btn");
        var joinForm = document.getElementById("bowling-join-form");
        var joinInput = document.getElementById("bowling-join-code");
        var joinError = document.getElementById("bowling-join-error");
        var rejoinSection = document.getElementById("bowling-rejoin-section");
        var rejoinLink = document.getElementById("bowling-rejoin-link");

        if (joinInput) {
            joinInput.addEventListener("input", function () {
                var normalized = normalizeCode(joinInput.value);
                if (joinInput.value !== normalized) {
                    joinInput.value = normalized;
                }
                if (joinError) {
                    joinError.hidden = true;
                }
            });
        }

        var lastCode = null;
        try {
            lastCode = localStorage.getItem(STORAGE_KEY);
        } catch (err) {
            lastCode = null;
        }
        if (lastCode && CODE_PATTERN.test(lastCode) && rejoinSection && rejoinLink) {
            rejoinLink.href = "/bowling/" + lastCode;
            rejoinLink.textContent = "Rejoin game " + lastCode;
            rejoinSection.hidden = false;
        }

        if (createBtn) {
            createBtn.addEventListener("click", function () {
                createBtn.disabled = true;
                apiRequest("POST", "/bowling/api/games")
                    .then(function (data) {
                        saveLastCode(data.code);
                        window.location.href = data.url;
                    })
                    .catch(function (err) {
                        createBtn.disabled = false;
                        showToast(err.message, true);
                    });
            });
        }

        if (joinForm) {
            joinForm.addEventListener("submit", function (event) {
                event.preventDefault();
                var code = normalizeCode(joinInput ? joinInput.value : "");
                if (!CODE_PATTERN.test(code)) {
                    if (joinError) {
                        joinError.textContent = "Enter a 6-digit game code.";
                        joinError.hidden = false;
                    }
                    return;
                }
                if (joinError) {
                    joinError.hidden = true;
                }
                apiRequest("GET", "/bowling/api/games/" + code)
                    .then(function () {
                        saveLastCode(code);
                        window.location.href = "/bowling/" + code;
                    })
                    .catch(function (err) {
                        if (joinError) {
                            joinError.textContent = err.message;
                            joinError.hidden = false;
                        }
                    });
            });
        }
    }

    function initGame() {
        var root = document.getElementById("bowling-game-root");
        if (!root) {
            return;
        }

        var code = root.getAttribute("data-code");
        if (!code || !CODE_PATTERN.test(code)) {
            return;
        }

        saveLastCode(code);

        var shareBtn = document.getElementById("bowling-share-btn");
        var addPlayerBtn = document.getElementById("bowling-add-player-btn");
        var startBtn = document.getElementById("bowling-start-btn");
        var startDialog = document.getElementById("bowling-start-dialog");
        var playerList = document.getElementById("bowling-player-list");
        var setupEmpty = document.getElementById("bowling-setup-empty");

        var activeSelection = null;
        var pinPanelOpen = false;
        var scoreActionPending = false;
        var saveIndicatorTimer = null;

        var scorecardEl = document.getElementById("bowling-scorecard");
        var completeScorecardEl = document.getElementById("bowling-complete-scorecard");
        var pinPanel = document.getElementById("bowling-pin-panel");
        var pinLabel = document.getElementById("bowling-pin-label");
        var pinGrid = document.getElementById("bowling-pin-grid");
        var pinDismissBtn = document.getElementById("bowling-pin-dismiss-btn");
        var clearFrameBtn = document.getElementById("bowling-clear-frame-btn");
        var saveIndicator = document.getElementById("bowling-save-indicator");
        var activeAddPlayerBtn = document.getElementById("bowling-active-add-player-btn");
        var newGameBtn = document.getElementById("bowling-new-game-btn");
        var completeNewGameBtn = document.getElementById("bowling-complete-new-game-btn");
        var markCompleteBtn = document.getElementById("bowling-mark-complete-btn");
        var markCompleteBanner = document.getElementById("bowling-mark-complete-banner");
        var completeDialog = document.getElementById("bowling-complete-dialog");
        var newGameDialog = document.getElementById("bowling-new-game-dialog");
        var addPlayerDialog = document.getElementById("bowling-add-player-dialog");
        var addPlayerNameInput = document.getElementById("bowling-add-player-name");
        var gameMenuBtn = document.getElementById("bowling-game-menu-btn");
        var gameMenu = document.getElementById("bowling-game-menu");

        if (shareBtn) {
            shareBtn.addEventListener("click", function () {
                shareGame(code).catch(function (err) {
                    showToast(err.message || "Could not share", true);
                });
            });
        }

        if (addPlayerBtn) {
            addPlayerBtn.addEventListener("click", function () {
                if (pendingSave) {
                    return;
                }
                pendingSave = true;
                addPlayerBtn.disabled = true;
                apiRequest("POST", "/bowling/api/games/" + code + "/players", { name: "" })
                    .then(function (data) {
                        gameState = data;
                        renderGame(data);
                    })
                    .catch(function (err) {
                        showToast(err.message, true);
                    })
                    .finally(function () {
                        pendingSave = false;
                        addPlayerBtn.disabled = false;
                        focusLatestEmptyPlayer();
                    });
            });
        }

        if (startBtn) {
            startBtn.addEventListener("click", function () {
                if (startBtn.disabled || pendingSave) {
                    return;
                }
                openStartDialog();
            });
        }

        if (startDialog) {
            startDialog.addEventListener("close", function () {
                if (startDialog.returnValue !== "confirm") {
                    return;
                }
                confirmStartGame();
            });
        }

        function openStartDialog() {
            if (!startDialog || !gameState) {
                return;
            }

            var roster = document.getElementById("bowling-start-dialog-roster");
            var playersList = document.getElementById("bowling-start-dialog-players");
            var warning = document.getElementById("bowling-start-dialog-warning");
            var namedPlayers = getNamedPlayersFromForm();
            var totalRows = playerList
                ? playerList.querySelectorAll(".bowling-player-row").length
                : 0;
            var unnamedCount = totalRows - namedPlayers.length;

            if (playersList) {
                playersList.innerHTML = "";
                namedPlayers.forEach(function (player) {
                    var item = document.createElement("li");
                    item.textContent = player.name.trim();
                    playersList.appendChild(item);
                });
            }

            if (roster) {
                roster.hidden = namedPlayers.length === 0;
            }

            if (warning) {
                if (unnamedCount > 0) {
                    warning.textContent =
                        unnamedCount === 1
                            ? "1 player has no name — add a name or remove them before starting."
                            : unnamedCount + " players have no names — add names or remove them before starting.";
                    warning.hidden = false;
                } else {
                    warning.hidden = true;
                    warning.textContent = "";
                }
            }

            startDialog.showModal();
        }

        function confirmStartGame() {
            if (pendingSave) {
                return;
            }
            saveUnsavedPlayerNames()
                .then(function () {
                    if (!hasAnyNamedPlayer()) {
                        showToast("Add at least one player name.", true);
                        return;
                    }
                    pendingSave = true;
                    startBtn.disabled = true;
                    return apiRequest("POST", "/bowling/api/games/" + code + "/start");
                })
                .then(function (data) {
                    if (!data) {
                        return;
                    }
                    gameState = data;
                    renderGame(data);
                    showToast("Game started");
                })
                .catch(function (err) {
                    if (err && err.message) {
                        showToast(err.message, true);
                    }
                })
                .finally(function () {
                    pendingSave = false;
                    updateStartButton(gameState);
                });
        }

        function focusLatestEmptyPlayer() {
            if (!playerList) {
                return;
            }
            var inputs = playerList.querySelectorAll(".bowling-player-name-input");
            for (var i = inputs.length - 1; i >= 0; i -= 1) {
                if (!inputs[i].value.trim()) {
                    inputs[i].focus();
                    return;
                }
            }
        }

        function hasAnyNamedPlayer() {
            if (playerList) {
                var inputs = playerList.querySelectorAll(".bowling-player-name-input");
                for (var i = 0; i < inputs.length; i += 1) {
                    if (inputs[i].value.trim()) {
                        return true;
                    }
                }
            }
            if (gameState && gameState.players) {
                return gameState.players.some(function (player) {
                    return player.name && player.name.trim();
                });
            }
            return false;
        }

        function getNamedPlayersFromForm() {
            var named = [];
            if (!playerList) {
                return named;
            }
            Array.prototype.slice.call(
                playerList.querySelectorAll(".bowling-player-row")
            ).forEach(function (row) {
                var input = row.querySelector(".bowling-player-name-input");
                if (input && input.value.trim()) {
                    named.push({ name: input.value.trim() });
                }
            });
            return named;
        }

        function savePlayerName(playerId, input) {
            var trimmed = input.value.trim();
            if (trimmed === (input.dataset.lastSaved || "")) {
                input.value = trimmed;
                return Promise.resolve();
            }
            pendingSave = true;
            return apiRequest("PUT", "/bowling/api/games/" + code + "/players/" + playerId, {
                name: trimmed,
            })
                .then(function (data) {
                    gameState = data;
                    input.dataset.lastSaved = trimmed;
                    input.value = trimmed;
                    updateStartButton(data);
                    return data;
                })
                .catch(function (err) {
                    showToast(err.message, true);
                    input.value = input.dataset.lastSaved || "";
                    throw err;
                })
                .finally(function () {
                    pendingSave = false;
                    updateStartButton(gameState);
                });
        }

        function saveUnsavedPlayerNames() {
            if (!playerList) {
                return Promise.resolve();
            }
            var inputs = playerList.querySelectorAll(".bowling-player-name-input");
            var saves = [];
            Array.prototype.forEach.call(inputs, function (input) {
                var trimmed = input.value.trim();
                if (trimmed !== (input.dataset.lastSaved || "")) {
                    saves.push(savePlayerName(input.dataset.playerId, input));
                }
            });
            return Promise.all(saves);
        }

        function setVisibleView(status) {
            var setupView = document.getElementById("bowling-view-setup");
            var activeView = document.getElementById("bowling-view-active");
            var completeView = document.getElementById("bowling-view-complete");
            if (setupView) {
                setupView.hidden = status !== "setup";
            }
            if (activeView) {
                activeView.hidden = status !== "active";
            }
            if (completeView) {
                completeView.hidden = status !== "complete";
            }
            if (root) {
                root.classList.toggle("bowling-game-root--active", status === "active");
                root.classList.toggle("bowling-game-root--complete", status === "complete");
                root.classList.toggle("bowling-game-root--pin-open", status === "active" && pinPanelOpen);
            }
            if (status !== "active") {
                closePinPanel();
            }
            if (root && status !== "active") {
                root.classList.remove("bowling-game-root--mark-complete");
            }
            updateGameMenuVisibility(status);
        }

        function closeGameMenu() {
            if (!gameMenu || !gameMenuBtn) {
                return;
            }
            gameMenu.hidden = true;
            gameMenuBtn.setAttribute("aria-expanded", "false");
        }

        function toggleGameMenu() {
            if (!gameMenu || !gameMenuBtn) {
                return;
            }
            var willOpen = gameMenu.hidden;
            gameMenu.hidden = !willOpen;
            gameMenuBtn.setAttribute("aria-expanded", willOpen ? "true" : "false");
        }

        function isGameFullyScored(state) {
            if (!state || state.status !== "active" || !state.mark_complete_eligible) {
                return false;
            }
            var players = state.players || [];
            for (var i = 0; i < players.length; i += 1) {
                if (players[i].actionable_frame) {
                    return false;
                }
                if (players[i].scorecard.total === null || players[i].scorecard.total === undefined) {
                    return false;
                }
            }
            return players.length > 0;
        }

        function updateGameMenuVisibility(status) {
            if (gameMenuBtn) {
                gameMenuBtn.hidden = status !== "active";
            }
            if (status !== "active") {
                closeGameMenu();
            }
        }

        function shouldStayOnSameFrame(player, rolledFrame) {
            if (!player || player.actionable_frame !== rolledFrame) {
                return false;
            }
            var frame = player.scorecard.frames[rolledFrame - 1];
            if (!frame || frame.complete) {
                return false;
            }
            return !!getNextRollForPlayer(player);
        }

        function advancePinPanelAfterRoll(data, playerId, rolledFrame) {
            var updated = getPlayerById(data, playerId);
            if (updated && shouldStayOnSameFrame(updated, rolledFrame)) {
                openPinPanelForPlayer(playerId);
                return;
            }
            if (data.current_turn_player_id !== null && data.current_turn_player_id !== undefined) {
                var turnPlayer = getPlayerById(data, data.current_turn_player_id);
                if (turnPlayer && turnPlayer.actionable_frame) {
                    openPinPanelForPlayer(data.current_turn_player_id);
                } else {
                    closePinPanel();
                }
                return;
            }
            closePinPanel();
        }

        function getPlayerById(state, playerId) {
            if (!state || !state.players) {
                return null;
            }
            var targetId = Number(playerId);
            for (var i = 0; i < state.players.length; i += 1) {
                if (Number(state.players[i].id) === targetId) {
                    return state.players[i];
                }
            }
            return null;
        }

        function getNextRollForPlayer(player) {
            var frameNum = player.actionable_frame;
            if (!frameNum) {
                return null;
            }
            var frame = player.scorecard.frames[frameNum - 1];
            if (!frame || frame.complete) {
                return null;
            }
            var rolls = frame.rolls || [];
            if (frameNum <= 9) {
                if (rolls.length === 0) {
                    return 1;
                }
                if (rolls[0].display === "X") {
                    return null;
                }
                if (rolls.length === 1) {
                    return 2;
                }
                return null;
            }
            if (rolls.length === 0) {
                return 1;
            }
            if (rolls.length === 1) {
                return 2;
            }
            if (rolls.length === 2 && !frame.third_roll_locked) {
                return 3;
            }
            return null;
        }

        function maxPinsForRoll(player, frameNum, rollNum) {
            var frame = player.scorecard.frames[frameNum - 1];
            var rolls = frame.rolls || [];
            if (frameNum <= 9) {
                if (rollNum === 1) {
                    return 10;
                }
                var r1 = rolls[0] ? rolls[0].pins : 0;
                return 10 - r1;
            }
            var r1 = rolls[0] ? rolls[0].pins : null;
            var r2 = rolls[1] ? rolls[1].pins : null;
            if (rollNum === 1) {
                return 10;
            }
            if (r1 === 10) {
                if (rollNum === 2) {
                    return 10;
                }
                if (rollNum === 3 && r2 !== null && r2 < 10) {
                    return 10 - r2;
                }
                return 10;
            }
            if (rollNum === 2) {
                return 10 - (r1 || 0);
            }
            if (r1 !== null && r1 < 10 && r2 !== null && r1 + r2 === 10) {
                return 10;
            }
            return 10;
        }

        function formatTotalValue(player) {
            if (player.scorecard.total === null || player.scorecard.total === undefined) {
                return "";
            }
            return String(player.scorecard.total);
        }

        function buildRollBoxes(frame, frameNum) {
            var rolls = frame.rolls || [];
            var boxes = [];
            if (frameNum < 10) {
                if (rolls.length > 0 && rolls[0].display === "X") {
                    boxes.push({ display: "X", className: "bowling-roll-box bowling-roll-box--strike-only" });
                    boxes.push({ display: "", className: "bowling-roll-box bowling-roll-box--hidden" });
                    return boxes;
                }
                boxes.push({
                    display: rolls[0] ? rolls[0].display : "",
                    className: "bowling-roll-box",
                });
                boxes.push({
                    display: rolls[1] ? rolls[1].display : "",
                    className: "bowling-roll-box",
                });
                return boxes;
            }
            boxes.push({
                display: rolls[0] ? rolls[0].display : "",
                className: "bowling-roll-box",
            });
            boxes.push({
                display: rolls[1] ? rolls[1].display : "",
                className: "bowling-roll-box",
            });
            if (frame.third_roll_locked && rolls.length < 3) {
                boxes.push({ display: "", className: "bowling-roll-box bowling-roll-box--locked" });
            } else {
                boxes.push({
                    display: rolls[2] ? rolls[2].display : "",
                    className: "bowling-roll-box",
                });
            }
            return boxes;
        }

        function renderScorecardInto(container, state, readOnly) {
            if (!container) {
                return;
            }
            container.innerHTML = "";
            var table = document.createElement("div");
            table.className = "bowling-scorecard-table";

            var head = document.createElement("div");
            head.className = "bowling-scorecard-head";
            var nameHead = document.createElement("div");
            nameHead.className = "bowling-sc-cell bowling-sc-name-head";
            nameHead.textContent = "Player";
            head.appendChild(nameHead);
            for (var f = 1; f <= 10; f += 1) {
                var frameHead = document.createElement("div");
                frameHead.className = "bowling-sc-cell bowling-sc-frame-head";
                frameHead.textContent = String(f);
                head.appendChild(frameHead);
            }
            var totalHead = document.createElement("div");
            totalHead.className = "bowling-sc-cell bowling-sc-total-head";
            totalHead.textContent = "Total";
            head.appendChild(totalHead);
            table.appendChild(head);

            (state.players || []).forEach(function (player) {
                var row = document.createElement("div");
                row.className = "bowling-scorecard-row bowling-player-row";
                row.dataset.playerId = String(player.id);
                if (player.id === state.current_turn_player_id) {
                    row.classList.add("bowling-scorecard-row--turn");
                }

                var nameCell = document.createElement("div");
                nameCell.className = "bowling-sc-cell bowling-sc-name";
                if (player.id === state.current_turn_player_id) {
                    var marker = document.createElement("span");
                    marker.className = "bowling-sc-turn-marker";
                    marker.textContent = "▶";
                    nameCell.appendChild(marker);
                }
                nameCell.appendChild(document.createTextNode(player.name || "Player"));
                row.appendChild(nameCell);

                player.scorecard.frames.forEach(function (frame) {
                    var frameCell = document.createElement("div");
                    frameCell.className = "bowling-sc-cell bowling-frame-cell";
                    frameCell.dataset.playerId = String(player.id);
                    frameCell.dataset.frame = String(frame.frame);

                    if (!readOnly && frame.frame === player.actionable_frame && player.actionable_frame) {
                        if (player.id === state.current_turn_player_id) {
                            frameCell.classList.add("bowling-frame-cell--actionable-turn");
                        } else {
                            frameCell.classList.add("bowling-frame-cell--actionable-other");
                        }
                    }
                    if (!readOnly && frame.frame === player.clearable_frame && player.clearable_frame) {
                        frameCell.classList.add("bowling-frame-cell--clearable");
                    }

                    var inner = document.createElement("div");
                    inner.className = "bowling-frame-cell-inner";

                    var rollsRow = document.createElement("div");
                    rollsRow.className = "bowling-frame-rolls";
                    buildRollBoxes(frame, frame.frame).forEach(function (box) {
                        var rollBox = document.createElement("span");
                        rollBox.className = box.className;
                        rollBox.textContent = box.display;
                        rollsRow.appendChild(rollBox);
                    });

                    var scoreEl = document.createElement("div");
                    scoreEl.className = "bowling-frame-score";
                    if (frame.pending) {
                        scoreEl.classList.add("bowling-frame-score--pending");
                        scoreEl.textContent = "…";
                    } else if (
                        frame.complete &&
                        frame.cumulative !== null &&
                        frame.cumulative !== undefined
                    ) {
                        scoreEl.textContent = String(frame.cumulative);
                    } else {
                        scoreEl.textContent = "";
                    }

                    var rollsWrap = document.createElement("div");
                    rollsWrap.className = "bowling-frame-rolls-wrap";
                    rollsWrap.appendChild(rollsRow);

                    if (!readOnly && frame.frame === player.clearable_frame && player.clearable_frame) {
                        var clearBtn = document.createElement("button");
                        clearBtn.type = "button";
                        clearBtn.className = "bowling-frame-clear-btn";
                        clearBtn.setAttribute("aria-label", "Clear frame " + frame.frame);
                        clearBtn.textContent = "Clear";
                        clearBtn.addEventListener("click", function (event) {
                            event.stopPropagation();
                            requestClearFrame(player.id, frame.frame);
                        });
                        rollsWrap.appendChild(clearBtn);
                    }

                    inner.appendChild(rollsWrap);
                    inner.appendChild(scoreEl);
                    frameCell.appendChild(inner);

                    row.appendChild(frameCell);
                });

                var totalCell = document.createElement("div");
                totalCell.className = "bowling-sc-cell bowling-sc-total";
                totalCell.textContent = formatTotalValue(player);
                row.appendChild(totalCell);

                table.appendChild(row);
            });

            container.appendChild(table);
        }

        function showSaveIndicator() {
            if (!saveIndicator) {
                return;
            }
            saveIndicator.hidden = false;
            if (saveIndicatorTimer) {
                clearTimeout(saveIndicatorTimer);
            }
            saveIndicatorTimer = setTimeout(function () {
                saveIndicator.hidden = true;
            }, 1500);
        }

        function closePinPanel() {
            pinPanelOpen = false;
            activeSelection = null;
            if (pinPanel) {
                pinPanel.hidden = true;
            }
            if (root) {
                root.classList.remove("bowling-game-root--pin-open");
            }
        }

        function openPinPanelForPlayer(playerId) {
            if (!gameState || gameState.status !== "active") {
                return;
            }
            var player = getPlayerById(gameState, playerId);
            if (!player || !player.actionable_frame) {
                return;
            }
            activeSelection = {
                playerId: player.id,
                frame: player.actionable_frame,
            };
            pinPanelOpen = true;
            if (pinPanel) {
                pinPanel.hidden = false;
            }
            if (root) {
                root.classList.add("bowling-game-root--pin-open");
            }
            renderPinPanel(gameState);
        }

        function renderPinPanel(state) {
            if (!pinPanelOpen || !activeSelection || !pinGrid || !pinLabel) {
                return;
            }
            var player = getPlayerById(state, activeSelection.playerId);
            if (!player || !player.actionable_frame) {
                closePinPanel();
                return;
            }
            activeSelection.frame = player.actionable_frame;
            var frameNum = player.actionable_frame;
            var rollNum = getNextRollForPlayer(player);
            if (!rollNum) {
                closePinPanel();
                return;
            }

            pinLabel.textContent =
                (player.name || "Player") +
                " — Frame " +
                frameNum +
                ", Roll " +
                rollNum;

            var maxPins = maxPinsForRoll(player, frameNum, rollNum);
            pinGrid.innerHTML = "";
            for (var pins = 0; pins <= 10; pins += 1) {
                var btn = document.createElement("button");
                btn.type = "button";
                var disabled = pins > maxPins;
                btn.className = "bowling-pin-btn";
                if (disabled) {
                    btn.classList.add("bowling-pin-btn--disabled");
                    btn.disabled = true;
                }
                var label = String(pins);
                if (rollNum === 1 && pins === 10) {
                    label = "10 / Strike";
                    btn.classList.add("bowling-pin-btn--wide");
                } else if (rollNum === 2 && pins === maxPins && maxPins < 10 && pins > 0) {
                    label = "/ (" + pins + ")";
                    btn.classList.add("bowling-pin-btn--spare");
                } else if (rollNum === 1 && pins === 10 && frameNum === 10) {
                    btn.classList.add("bowling-pin-btn--wide");
                }
                btn.textContent = label;
                if (!disabled) {
                    (function (pinCount) {
                        btn.addEventListener("click", function () {
                            submitRoll(pinCount);
                        });
                    })(pins);
                }
                pinGrid.appendChild(btn);
            }

            if (clearFrameBtn) {
                var canClear = player.clearable_frame === frameNum;
                clearFrameBtn.hidden = !canClear;
            }
        }

        function submitRoll(pins) {
            if (!activeSelection || scoreActionPending) {
                return;
            }
            var player = getPlayerById(gameState, activeSelection.playerId);
            if (!player) {
                return;
            }
            var frameNum = player.actionable_frame;
            var rollNum = getNextRollForPlayer(player);
            if (!frameNum || !rollNum) {
                return;
            }
            var rolledFrame = frameNum;

            scoreActionPending = true;
            apiRequest("POST", "/bowling/api/games/" + code + "/rolls", {
                player_id: player.id,
                frame: frameNum,
                roll: rollNum,
                pins: pins,
            })
                .then(function (data) {
                    gameState = data;
                    advancePinPanelAfterRoll(data, player.id, rolledFrame);
                    renderActiveGame(data);
                    showSaveIndicator();
                    return refreshGame();
                })
                .catch(function (err) {
                    showToast(err.message, true);
                })
                .finally(function () {
                    scoreActionPending = false;
                });
        }

        function requestClearFrame(playerId, frameNum) {
            if (scoreActionPending) {
                return;
            }
            var player = getPlayerById(gameState, playerId);
            if (!player) {
                return;
            }
            var frame = player.scorecard.frames[frameNum - 1];
            if (frame && frame.complete) {
                var playerName = player.name || "Player";
                var confirmed = window.confirm(
                    "Clear frame " +
                        frameNum +
                        " for " +
                        playerName +
                        "? All rolls for this frame will be removed and earlier scores may change."
                );
                if (!confirmed) {
                    return;
                }
            }
            clearFrameForPlayer(playerId, frameNum);
        }

        function clearFrameForPlayer(playerId, frameNum) {
            if (scoreActionPending) {
                return;
            }
            scoreActionPending = true;
            apiRequest("POST", "/bowling/api/games/" + code + "/clear", {
                player_id: playerId,
                frame: frameNum,
            })
                .then(function (data) {
                    gameState = data;
                    renderActiveGame(data);
                    showSaveIndicator();
                    var updated = getPlayerById(data, playerId);
                    if (updated && updated.actionable_frame) {
                        openPinPanelForPlayer(playerId);
                    } else {
                        closePinPanel();
                    }
                    return refreshGame();
                })
                .catch(function (err) {
                    showToast(err.message, true);
                })
                .finally(function () {
                    scoreActionPending = false;
                });
        }

        function handleScorecardClick(event) {
            if (!gameState || gameState.status !== "active" || scoreActionPending) {
                return;
            }
            var clearBtn = event.target.closest(".bowling-frame-clear-btn");
            if (clearBtn) {
                return;
            }
            var frameCell = event.target.closest(".bowling-frame-cell");
            var row = event.target.closest(".bowling-scorecard-row");
            if (!row) {
                return;
            }
            var playerId = parseInt(row.dataset.playerId, 10);
            var player = getPlayerById(gameState, playerId);
            if (!player) {
                return;
            }

            if (frameCell) {
                var frameNum = parseInt(frameCell.dataset.frame, 10);
                if (frameNum === player.actionable_frame) {
                    openPinPanelForPlayer(playerId);
                }
                return;
            }

            if (playerId === gameState.current_turn_player_id && player.actionable_frame) {
                openPinPanelForPlayer(playerId);
            }
        }

        function renderActiveGame(state) {
            updateGameMenuVisibility(state.status);
            if (activeAddPlayerBtn) {
                activeAddPlayerBtn.hidden = !state.can_add_player;
            }
            var showMarkComplete = isGameFullyScored(state);
            if (markCompleteBanner) {
                markCompleteBanner.hidden = !showMarkComplete;
            }
            if (root) {
                root.classList.toggle("bowling-game-root--mark-complete", showMarkComplete);
            }
            renderScorecardInto(scorecardEl, state, false);
            if (pinPanelOpen && activeSelection) {
                renderPinPanel(state);
            }
        }

        function renderCompleteGame(state) {
            renderScorecardInto(completeScorecardEl, state, true);
        }

        if (scorecardEl) {
            scorecardEl.addEventListener("click", handleScorecardClick);
        }
        if (gameMenuBtn && gameMenu) {
            gameMenuBtn.addEventListener("click", function (event) {
                event.stopPropagation();
                toggleGameMenu();
            });
            document.addEventListener("click", function (event) {
                if (gameMenu.hidden) {
                    return;
                }
                if (!gameMenu.contains(event.target) && event.target !== gameMenuBtn) {
                    closeGameMenu();
                }
            });
        }
        if (pinDismissBtn) {
            pinDismissBtn.addEventListener("click", closePinPanel);
        }
        if (clearFrameBtn) {
            clearFrameBtn.addEventListener("click", function () {
                if (!activeSelection) {
                    return;
                }
                requestClearFrame(activeSelection.playerId, activeSelection.frame);
            });
        }
        if (activeAddPlayerBtn) {
            activeAddPlayerBtn.addEventListener("click", function () {
                closeGameMenu();
                if (addPlayerNameInput) {
                    addPlayerNameInput.value = "";
                }
                if (addPlayerDialog) {
                    addPlayerDialog.showModal();
                    if (addPlayerNameInput) {
                        addPlayerNameInput.focus();
                    }
                }
            });
        }
        if (addPlayerDialog) {
            addPlayerDialog.addEventListener("close", function () {
                if (addPlayerDialog.returnValue !== "confirm") {
                    return;
                }
                var name = addPlayerNameInput ? addPlayerNameInput.value.trim() : "";
                if (!name) {
                    showToast("Player name is required.", true);
                    return;
                }
                scoreActionPending = true;
                apiRequest("POST", "/bowling/api/games/" + code + "/players", { name: name })
                    .then(function (data) {
                        gameState = data;
                        renderActiveGame(data);
                        showToast("Player added");
                    })
                    .catch(function (err) {
                        showToast(err.message, true);
                    })
                    .finally(function () {
                        scoreActionPending = false;
                    });
            });
        }
        function openNewGameDialog() {
            if (newGameDialog) {
                newGameDialog.showModal();
            }
        }

        if (newGameBtn && newGameDialog) {
            newGameBtn.addEventListener("click", function () {
                closeGameMenu();
                openNewGameDialog();
            });
            newGameDialog.addEventListener("close", function () {
                if (newGameDialog.returnValue === "confirm") {
                    window.location.href = "/bowling/";
                }
            });
        }
        if (completeNewGameBtn && newGameDialog) {
            completeNewGameBtn.addEventListener("click", openNewGameDialog);
        }
        if (markCompleteBtn && completeDialog) {
            markCompleteBtn.addEventListener("click", function () {
                completeDialog.showModal();
            });
            completeDialog.addEventListener("close", function () {
                if (completeDialog.returnValue !== "confirm") {
                    return;
                }
                scoreActionPending = true;
                apiRequest("POST", "/bowling/api/games/" + code + "/complete")
                    .then(function (data) {
                        gameState = data;
                        closePinPanel();
                        renderGame(data);
                        showToast("Game complete");
                    })
                    .catch(function (err) {
                        showToast(err.message, true);
                    })
                    .finally(function () {
                        scoreActionPending = false;
                    });
            });
        }

        function createPlayerRow(player, index, total) {
            var row = document.createElement("div");
            row.className = "bowling-player-row";
            row.setAttribute("role", "listitem");
            row.dataset.playerId = String(player.id);

            var order = document.createElement("div");
            order.className = "bowling-player-order";

            var upBtn = document.createElement("button");
            upBtn.type = "button";
            upBtn.className = "bowling-btn bowling-btn-icon";
            upBtn.setAttribute("aria-label", "Move player up");
            upBtn.textContent = "↑";
            upBtn.disabled = index === 0;
            upBtn.addEventListener("click", function () {
                movePlayer(player.id, -1);
            });

            var downBtn = document.createElement("button");
            downBtn.type = "button";
            downBtn.className = "bowling-btn bowling-btn-icon";
            downBtn.setAttribute("aria-label", "Move player down");
            downBtn.textContent = "↓";
            downBtn.disabled = index >= total - 1;
            downBtn.addEventListener("click", function () {
                movePlayer(player.id, 1);
            });

            order.appendChild(upBtn);
            order.appendChild(downBtn);

            var input = document.createElement("input");
            input.type = "text";
            input.className = "bowling-input bowling-player-name-input";
            input.value = player.name || "";
            input.placeholder = "Player name";
            input.autocomplete = "off";
            input.maxLength = 100;
            input.dataset.playerId = String(player.id);
            input.dataset.lastSaved = player.name || "";

            input.addEventListener("blur", function () {
                savePlayerName(player.id, input);
            });
            input.addEventListener("input", function () {
                updateStartButton(gameState);
            });
            input.addEventListener("keydown", function (event) {
                if (event.key === "Enter") {
                    event.preventDefault();
                    input.blur();
                }
            });

            var removeBtn = document.createElement("button");
            removeBtn.type = "button";
            removeBtn.className = "bowling-player-remove";
            removeBtn.textContent = "Remove";
            removeBtn.disabled = total <= 1;
            removeBtn.addEventListener("click", function () {
                removePlayer(player.id);
            });

            row.appendChild(order);
            row.appendChild(input);
            row.appendChild(removeBtn);
            return row;
        }

        function updatePlayerRow(row, player, index, total) {
            var input = row.querySelector(".bowling-player-name-input");
            var upBtn = row.querySelector(".bowling-player-order button:first-child");
            var downBtn = row.querySelector(".bowling-player-order button:last-child");
            var removeBtn = row.querySelector(".bowling-player-remove");

            if (upBtn) {
                upBtn.disabled = index === 0;
            }
            if (downBtn) {
                downBtn.disabled = index >= total - 1;
            }
            if (removeBtn) {
                removeBtn.disabled = total <= 1;
            }
            if (input && document.activeElement !== input) {
                input.value = player.name || "";
                input.dataset.lastSaved = player.name || "";
            }
        }

        function renderSetupPlayers(state) {
            if (!playerList) {
                return;
            }

            var players = state.players || [];
            if (setupEmpty) {
                setupEmpty.hidden = players.length > 0;
            }

            var focusedId = document.activeElement && document.activeElement.dataset
                ? document.activeElement.dataset.playerId
                : null;

            players.forEach(function (player, index) {
                var row = playerList.querySelector('[data-player-id="' + player.id + '"]');
                if (!row) {
                    row = createPlayerRow(player, index, players.length);
                } else {
                    updatePlayerRow(row, player, index, players.length);
                }
                // appendChild moves existing nodes — keeps DOM order in sync with server order
                playerList.appendChild(row);
            });

            Array.prototype.slice.call(
                playerList.querySelectorAll("[data-player-id]")
            ).forEach(function (row) {
                var rowId = row.dataset.playerId;
                var exists = players.some(function (player) {
                    return String(player.id) === rowId;
                });
                if (!exists && rowId !== focusedId) {
                    row.remove();
                }
            });

            updateStartButton(state);
        }

        function updateStartButton(state) {
            if (!startBtn || !state || state.status !== "setup") {
                return;
            }
            startBtn.disabled = !hasAnyNamedPlayer() || pendingSave;
        }

        function movePlayer(playerId, direction) {
            if (!gameState || pendingSave) {
                return;
            }
            var players = gameState.players.slice();
            var index = players.findIndex(function (player) {
                return player.id === playerId;
            });
            if (index < 0) {
                return;
            }
            var target = index + direction;
            if (target < 0 || target >= players.length) {
                return;
            }
            var tmp = players[index];
            players[index] = players[target];
            players[target] = tmp;
            var ids = players.map(function (player) {
                return player.id;
            });

            pendingSave = true;
            apiRequest("PUT", "/bowling/api/games/" + code + "/players/order", {
                player_ids: ids,
            })
                .then(function (data) {
                    gameState = data;
                    renderSetupPlayers(data);
                })
                .catch(function (err) {
                    showToast(err.message, true);
                })
                .finally(function () {
                    pendingSave = false;
                });
        }

        function removePlayer(playerId) {
            if (!gameState || pendingSave) {
                return;
            }
            if (gameState.players.length <= 1) {
                return;
            }
            pendingSave = true;
            apiRequest("DELETE", "/bowling/api/games/" + code + "/players/" + playerId)
                .then(function (data) {
                    gameState = data;
                    renderSetupPlayers(data);
                })
                .catch(function (err) {
                    showToast(err.message, true);
                })
                .finally(function () {
                    pendingSave = false;
                });
        }

        function renderGame(state) {
            if (!state) {
                return;
            }
            setVisibleView(state.status);
            if (state.status === "setup") {
                renderSetupPlayers(state);
            } else if (state.status === "active") {
                renderActiveGame(state);
            } else if (state.status === "complete") {
                renderCompleteGame(state);
            }
        }

        function refreshGame() {
            if (pendingSave || scoreActionPending) {
                return Promise.resolve();
            }
            var skipPlayerMerge =
                document.activeElement &&
                document.activeElement.classList &&
                document.activeElement.classList.contains("bowling-player-name-input");
            var previousStatus = gameState ? gameState.status : null;

            return apiRequest("GET", "/bowling/api/games/" + code)
                .then(function (data) {
                    gameState = data;
                    if (data.status !== previousStatus) {
                        renderGame(data);
                        return;
                    }
                    if (data.status === "setup" && !skipPlayerMerge) {
                        renderSetupPlayers(data);
                    } else if (data.status === "active") {
                        renderActiveGame(data);
                    } else if (data.status === "complete") {
                        renderCompleteGame(data);
                    }
                })
                .catch(function (err) {
                    showToast(err.message, true);
                });
        }

        refreshGame().then(function () {
            pollTimer = setInterval(refreshGame, POLL_MS);
        });

        window.addEventListener("beforeunload", function () {
            if (pollTimer) {
                clearInterval(pollTimer);
            }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            initHome();
            initGame();
        });
    } else {
        initHome();
        initGame();
    }
})();
