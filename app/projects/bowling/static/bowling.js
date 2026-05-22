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
            }
        }

        function refreshGame() {
            if (pendingSave) {
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
                    } else if (data.status !== "setup") {
                        setVisibleView(data.status);
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
