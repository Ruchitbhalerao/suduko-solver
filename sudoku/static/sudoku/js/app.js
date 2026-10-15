/* AI-Based Sudoku Solver — frontend behaviour (Phase 7, part 2).
 *
 * Plain vanilla JavaScript (no framework, no build step). Responsibilities:
 *   - build the 9x9 editable grid,
 *   - track the grid, the original clues, and solver-filled cells,
 *   - call the existing JSON API (/api/validate/ and /api/solve/),
 *   - render status messages and solver metrics,
 *   - mark results stale when the puzzle or algorithm changes.
 *
 * The two endpoint URLs are read from data-* attributes rendered by Django
 * ({% url %}), so nothing here hard-codes a host or port.
 */
(function () {
    "use strict";

    /* A deterministic, valid, incomplete classic puzzle. The same grid is used
       by the project's tests and the benchmark dataset ("easy_classic"), and the
       validation endpoint accepts it. */
    var EXAMPLE_PUZZLE = [
        [5, 3, 0, 0, 7, 0, 0, 0, 0],
        [6, 0, 0, 1, 9, 5, 0, 0, 0],
        [0, 9, 8, 0, 0, 0, 0, 6, 0],
        [8, 0, 0, 0, 6, 0, 0, 0, 3],
        [4, 0, 0, 8, 0, 3, 0, 0, 1],
        [7, 0, 0, 0, 2, 0, 0, 0, 6],
        [0, 6, 0, 0, 0, 0, 2, 8, 0],
        [0, 0, 0, 4, 1, 9, 0, 0, 5],
        [0, 0, 0, 0, 8, 0, 0, 7, 9]
    ];

    var ALGORITHM_LABELS = {
        backtracking: "Backtracking (baseline)",
        mrv: "MRV",
        mrv_forward_checking: "MRV + Forward Checking"
    };

    function zeros() {
        return Array.from({ length: 9 }, function () {
            return new Array(9).fill(0);
        });
    }

    function falses() {
        return Array.from({ length: 9 }, function () {
            return new Array(9).fill(false);
        });
    }

    function cloneGrid(grid) {
        return grid.map(function (row) {
            return row.slice();
        });
    }

    function serialize(grid) {
        var out = "";
        for (var r = 0; r < 9; r += 1) {
            for (var c = 0; c < 9; c += 1) {
                out += String(grid[r][c]);
            }
        }
        return out;
    }

    function isAbort(error) {
        return Boolean(error) && error.name === "AbortError";
    }

    function formatInt(value) {
        return typeof value === "number" && isFinite(value) ? String(value) : "\u2014";
    }

    function formatMs(value) {
        if (typeof value !== "number" || !isFinite(value)) {
            return "\u2014";
        }
        return (value < 0.1 ? value.toFixed(4) : value.toFixed(2)) + " ms";
    }

    function init() {
        var gridEl = document.getElementById("sudoku-grid");
        if (!gridEl) {
            return;
        }

        var validateUrl = gridEl.dataset.validateUrl;
        var solveUrl = gridEl.dataset.solveUrl;

        var algorithmSelect = document.getElementById("algorithm");
        var solveButton = document.getElementById("solve-button");
        var validateButton = document.getElementById("validate-button");
        var loadExampleButton = document.getElementById("load-example-button");
        var clearButton = document.getElementById("clear-button");

        var statusEl = document.getElementById("status");
        var resultsEl = document.getElementById("results");
        var resultsEmptyEl = document.getElementById("results-empty");
        var staleNoteEl = document.getElementById("stale-note");

        var resultStatusEl = document.getElementById("result-status");
        var resultAlgorithmEl = document.getElementById("result-algorithm");
        var resultCallsEl = document.getElementById("result-recursive-calls");
        var resultAssignmentsEl = document.getElementById("result-attempted-assignments");
        var resultBacktracksEl = document.getElementById("result-backtracks");
        var resultTimeEl = document.getElementById("result-execution-time");

        var state = {
            grid: zeros(),
            clueMask: falses(),
            solvedMask: falses(),
            cells: [],
            solving: false,
            validating: false,
            solveToken: 0,
            validateToken: 0,
            activeSolveToken: 0,
            activeValidateToken: 0,
            solveController: null,
            validateController: null,
            hasResult: false,
            resultStale: false
        };

        /* ---------- rendering ---------- */

        function buildGrid() {
            gridEl.textContent = "";
            state.cells = [];
            var fragment = document.createDocumentFragment();

            for (var r = 0; r < 9; r += 1) {
                var rowEl = document.createElement("div");
                rowEl.className = "grid-row";
                rowEl.setAttribute("role", "row");
                var rowCells = [];

                for (var c = 0; c < 9; c += 1) {
                    var input = document.createElement("input");
                    input.type = "text";
                    input.inputMode = "numeric";
                    input.autocomplete = "off";
                    input.maxLength = 1;
                    input.className = "cell";
                    input.setAttribute("role", "gridcell");
                    input.setAttribute(
                        "aria-label",
                        "Row " + (r + 1) + " column " + (c + 1)
                    );
                    input.dataset.row = String(r);
                    input.dataset.col = String(c);
                    if (c % 3 === 2 && c !== 8) {
                        input.classList.add("box-right");
                    }
                    if (r % 3 === 2 && r !== 8) {
                        input.classList.add("box-bottom");
                    }
                    input.addEventListener("input", onCellInput);
                    input.addEventListener("keydown", onCellKeyDown);
                    rowEl.appendChild(input);
                    rowCells.push(input);
                }

                fragment.appendChild(rowEl);
                state.cells.push(rowCells);
            }

            gridEl.appendChild(fragment);
        }

        function applyCellState(r, c) {
            var input = state.cells[r][c];
            var value = state.grid[r][c];
            var isClue = state.clueMask[r][c];
            var isSolved = !isClue && state.solvedMask[r][c];
            var isEntered = !isClue && !isSolved && value !== 0;

            input.value = value === 0 ? "" : String(value);
            input.classList.toggle("clue", isClue);
            input.classList.toggle("solved", isSolved);
            input.classList.toggle("entered", isEntered);
            input.classList.toggle("empty", value === 0);
        }

        function renderAll() {
            for (var r = 0; r < 9; r += 1) {
                for (var c = 0; c < 9; c += 1) {
                    applyCellState(r, c);
                }
            }
        }

        function setStatus(message, kind) {
            if (!message) {
                statusEl.hidden = true;
                statusEl.textContent = "";
                statusEl.className = "status";
                return;
            }
            statusEl.hidden = false;
            statusEl.textContent = message;
            statusEl.className = "status" + (kind ? " is-" + kind : "");
        }

        function clearResult() {
            state.hasResult = false;
            state.resultStale = false;
            resultsEl.hidden = true;
            resultsEmptyEl.hidden = false;
            staleNoteEl.hidden = true;
        }

        function markStale() {
            if (!state.hasResult) {
                return;
            }
            state.resultStale = true;
            staleNoteEl.hidden = false;
        }

        function showResult(outcome) {
            state.hasResult = true;
            state.resultStale = false;
            resultsEmptyEl.hidden = true;
            resultsEl.hidden = false;
            staleNoteEl.hidden = true;

            var metrics = outcome.metrics || {};
            resultStatusEl.textContent = outcome.status;
            resultAlgorithmEl.textContent =
                ALGORITHM_LABELS[outcome.algorithm] || outcome.algorithm;
            resultCallsEl.textContent = formatInt(metrics.recursive_calls);
            resultAssignmentsEl.textContent = formatInt(metrics.attempted_assignments);
            resultBacktracksEl.textContent = formatInt(metrics.backtracks);
            resultTimeEl.textContent = formatMs(metrics.execution_time_ms);
        }

        function updateControls() {
            var busy = state.solving || state.validating;
            solveButton.disabled = busy;
            validateButton.disabled = busy;
            solveButton.textContent = state.solving ? "Solving\u2026" : "Solve";
            validateButton.textContent = state.validating ? "Validating\u2026" : "Validate";
        }

        /* ---------- grid interaction ---------- */

        function sanitize(raw) {
            var digits = String(raw).replace(/[^1-9]/g, "");
            return digits.slice(-1);
        }

        function onCellInput(event) {
            var input = event.target;
            var r = Number(input.dataset.row);
            var c = Number(input.dataset.col);

            var cleaned = sanitize(input.value);
            if (input.value !== cleaned) {
                input.value = cleaned;
            }

            state.grid[r][c] = cleaned === "" ? 0 : Number(cleaned);
            /* Any edit makes the cell the user's own value, never a clue. */
            state.clueMask[r][c] = false;
            state.solvedMask[r][c] = false;

            applyCellState(r, c);
            onGridEdited();
        }

        function onCellKeyDown(event) {
            var moves = {
                ArrowUp: [-1, 0],
                ArrowDown: [1, 0],
                ArrowLeft: [0, -1],
                ArrowRight: [0, 1]
            };
            var move = moves[event.key];
            if (!move) {
                return;
            }
            event.preventDefault();
            var r = Number(event.target.dataset.row) + move[0];
            var c = Number(event.target.dataset.col) + move[1];
            if (r < 0) {
                r = 8;
            } else if (r > 8) {
                r = 0;
            }
            if (c < 0) {
                c = 8;
            } else if (c > 8) {
                c = 0;
            }
            state.cells[r][c].focus();
            state.cells[r][c].select();
        }

        function onGridEdited() {
            abortRequest("solve");
            abortRequest("validate");
            state.solving = false;
            state.validating = false;
            updateControls();
            markStale();
        }

        function abortRequest(kind) {
            if (kind === "solve" && state.solveController) {
                state.solveController.abort();
                state.solveController = null;
            }
            if (kind === "validate" && state.validateController) {
                state.validateController.abort();
                state.validateController = null;
            }
        }

        /* ---------- API helpers ---------- */

        function readJson(response) {
            return response.text().then(function (text) {
                if (!text) {
                    return null;
                }
                try {
                    return JSON.parse(text);
                } catch (err) {
                    return null;
                }
            });
        }

        function errorMessage(data, response) {
            if (data && data.error && data.error.message) {
                return data.error.message;
            }
            if (response.status === 400) {
                return "The request was rejected (400 Bad Request).";
            }
            if (response.status === 415) {
                return "The request must be sent as JSON.";
            }
            if (response.status === 422) {
                return "The grid is not a valid Sudoku puzzle.";
            }
            if (response.status >= 500) {
                return "The server hit an internal error. Please try again.";
            }
            return "The request failed with status " + response.status + ".";
        }

        var NETWORK_MESSAGE =
            "Could not reach the server. Check that it is running and try again.";

        /* ---------- actions ---------- */

        function loadExample() {
            abortRequest("solve");
            abortRequest("validate");
            state.solving = false;
            state.validating = false;
            updateControls();

            state.grid = cloneGrid(EXAMPLE_PUZZLE);
            state.clueMask = EXAMPLE_PUZZLE.map(function (row) {
                return row.map(function (value) {
                    return value !== 0;
                });
            });
            state.solvedMask = falses();
            clearResult();
            renderAll();
            setStatus("Loaded an example puzzle. Press Solve or Validate.", "info");
        }

        function clearGrid() {
            abortRequest("solve");
            abortRequest("validate");
            state.solving = false;
            state.validating = false;
            updateControls();

            state.grid = zeros();
            state.clueMask = falses();
            state.solvedMask = falses();
            clearResult();
            renderAll();
            setStatus("Grid cleared. Enter a puzzle or load the example.", "info");
        }

        function validate() {
            if (state.solving || state.validating) {
                return;
            }
            abortRequest("validate");
            var token = state.validateToken + 1;
            state.validateToken = token;
            state.activeValidateToken = token;
            var controller = new AbortController();
            state.validateController = controller;
            state.validating = true;
            updateControls();
            setStatus("Validating\u2026", "info");

            var snapshot = serialize(state.grid);

            fetch(validateUrl, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ grid: state.grid }),
                signal: controller.signal
            })
                .then(function (response) {
                    return readJson(response).then(function (data) {
                        return { response: response, data: data };
                    });
                })
                .then(function (result) {
                    if (token !== state.activeValidateToken) {
                        return;
                    }
                    if (serialize(state.grid) !== snapshot) {
                        setStatus("The grid changed; validation was ignored.", "info");
                        return;
                    }
                    if (!result.data) {
                        setStatus("The server returned an unexpected response.", "error");
                        return;
                    }
                    if (result.response.ok && result.data.valid) {
                        setStatus(
                            result.data.message || "The grid is valid.",
                            "success"
                        );
                    } else {
                        setStatus(errorMessage(result.data, result.response), "error");
                    }
                })
                .catch(function (error) {
                    if (!isAbort(error)) {
                        setStatus(NETWORK_MESSAGE, "error");
                    }
                })
                .then(function () {
                    if (state.activeValidateToken === token) {
                        state.validateController = null;
                        state.validating = false;
                        updateControls();
                    }
                });
        }

        function solve() {
            if (state.solving || state.validating) {
                return;
            }
            abortRequest("solve");
            var token = state.solveToken + 1;
            state.solveToken = token;
            state.activeSolveToken = token;
            var controller = new AbortController();
            state.solveController = controller;
            state.solving = true;
            updateControls();

            var algorithm = algorithmSelect.value;
            var submittedGrid = cloneGrid(state.grid);
            var submittedClues = cloneGrid(state.clueMask).map(function (row) {
                return row.map(Boolean);
            });
            var snapshot = serialize(submittedGrid);

            setStatus(
                "Solving with " + (ALGORITHM_LABELS[algorithm] || algorithm) + "\u2026",
                "info"
            );

            fetch(solveUrl, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    grid: submittedGrid,
                    algorithm: algorithm
                }),
                signal: controller.signal
            })
                .then(function (response) {
                    return readJson(response).then(function (data) {
                        return { response: response, data: data };
                    });
                })
                .then(function (result) {
                    if (token !== state.activeSolveToken) {
                        return;
                    }
                    if (
                        algorithmSelect.value !== algorithm ||
                        serialize(state.grid) !== snapshot
                    ) {
                        setStatus(
                            "The grid or algorithm changed; the result was ignored.",
                            "info"
                        );
                        return;
                    }
                    if (!result.data) {
                        setStatus("The server returned an unexpected response.", "error");
                        return;
                    }

                    if (result.response.ok && result.data.solved) {
                        applySolution(result.data.solution, submittedClues);
                        showResult({
                            status: "Solved",
                            algorithm: result.data.algorithm || algorithm,
                            metrics: result.data.metrics
                        });
                        setStatus(
                            result.data.message || "Puzzle solved.",
                            "success"
                        );
                        return;
                    }

                    if (result.response.ok && result.data.status === "unsolvable") {
                        showResult({
                            status: "Unsolvable",
                            algorithm: result.data.algorithm || algorithm,
                            metrics: result.data.metrics
                        });
                        setStatus(
                            result.data.message ||
                                "The puzzle is valid but has no solution.",
                            "warning"
                        );
                        return;
                    }

                    setStatus(errorMessage(result.data, result.response), "error");
                })
                .catch(function (error) {
                    if (!isAbort(error)) {
                        setStatus(NETWORK_MESSAGE, "error");
                    }
                })
                .then(function () {
                    if (state.activeSolveToken === token) {
                        state.solveController = null;
                        state.solving = false;
                        updateControls();
                    }
                });
        }

        function applySolution(solution, submittedClues) {
            if (
                !Array.isArray(solution) ||
                solution.length !== 9 ||
                solution.some(function (row) {
                    return !Array.isArray(row) || row.length !== 9;
                })
            ) {
                setStatus("The server returned a malformed solution.", "error");
                return;
            }
            state.grid = cloneGrid(solution);
            state.clueMask = cloneGrid(submittedClues);
            state.solvedMask = state.grid.map(function (row, r) {
                return row.map(function (value, c) {
                    return value !== 0 && !submittedClues[r][c];
                });
            });
            renderAll();
        }

        /* ---------- wiring ---------- */

        if (algorithmSelect) {
            algorithmSelect.addEventListener("change", function () {
                abortRequest("solve");
                state.solving = false;
                updateControls();
                markStale();
            });
        }
        solveButton.addEventListener("click", solve);
        validateButton.addEventListener("click", validate);
        loadExampleButton.addEventListener("click", loadExample);
        clearButton.addEventListener("click", clearGrid);


        /* ---------- image upload ---------- */
        var extractUrl = gridEl.dataset.extractUrl;
        var dropzone = document.getElementById("upload-dropzone");
        var imageInput = document.getElementById("image-input");
        var chooseImageButton = document.getElementById("choose-image-button");
        var extractButton = document.getElementById("extract-button");
        var resetImageButton = document.getElementById("reset-image-button");
        var imagePreviewContainer = document.getElementById("image-preview-container");
        var imagePreview = document.getElementById("image-preview");
        var uploadStatus = document.getElementById("upload-status");
        var uploadWarnings = document.getElementById("upload-warnings");

        var selectedImageFile = null;
        var extracting = false;
        var extractToken = 0;
        var activeExtractToken = 0;
        var extractController = null;

        function setUploadStatus(message, kind) {
            if (!uploadStatus) return;
            if (!message) {
                uploadStatus.hidden = true;
                uploadStatus.textContent = "";
                uploadStatus.className = "upload-status";
                return;
            }
            uploadStatus.hidden = false;
            uploadStatus.textContent = message;
            uploadStatus.className = "upload-status" + (kind ? " is-" + kind : "");
        }

        function setUploadWarnings(messages) {
            if (!uploadWarnings) return;
            if (!messages || messages.length === 0) {
                uploadWarnings.hidden = true;
                uploadWarnings.textContent = "";
                return;
            }
            uploadWarnings.hidden = false;
            uploadWarnings.textContent = messages.join(" ");
        }

        function abortExtract() {
            if (extractController) {
                extractController.abort();
                extractController = null;
            }
        }

        function clearSelectedImage() {
            selectedImageFile = null;
            if (imageInput) imageInput.value = "";
            if (imagePreviewContainer) imagePreviewContainer.hidden = true;
            if (imagePreview) imagePreview.src = "";
            if (extractButton) extractButton.disabled = true;
            if (resetImageButton) resetImageButton.disabled = true;
            setUploadStatus("", null);
            setUploadWarnings([]);
        }

        function updateExtractControls() {
            if (extractButton) {
                extractButton.disabled = !selectedImageFile || extracting;
                extractButton.textContent = extracting ? "Extracting…" : "Extract Sudoku";
            }
            if (resetImageButton) resetImageButton.disabled = !selectedImageFile || extracting;
            if (chooseImageButton) chooseImageButton.disabled = extracting;
        }

        function loadImageFile(file) {
            if (!file) return;
            var t = (file.type || "").toLowerCase();
            var name = (file.name || "").toLowerCase();
            var ok = t.startsWith("image/png") || t.startsWith("image/jpeg") || t.startsWith("image/jpg") || t.startsWith("image/webp") ||
                     name.endsWith(".png") || name.endsWith(".jpg") || name.endsWith(".jpeg") || name.endsWith(".webp");
            if (!ok) {
                setUploadStatus("Unsupported image format. Use PNG, JPG, JPEG, or WEBP.", "error");
                return;
            }
            if (file.size > 8*1024*1024) {
                setUploadStatus("The image is too large (maximum 8 MB).", "error");
                return;
            }
            selectedImageFile = file;
            var reader = new FileReader();
            reader.onload = function (e) {
                if (imagePreview) imagePreview.src = e.target.result;
                if (imagePreviewContainer) imagePreviewContainer.hidden = false;
            };
            reader.readAsDataURL(file);
            setUploadStatus("Image selected. Click 'Extract Sudoku'.", "info");
            setUploadWarnings([]);
            updateExtractControls();
        }

        if (dropzone && imageInput && chooseImageButton) {
            chooseImageButton.addEventListener("click", function () { imageInput.click(); });
            imageInput.addEventListener("change", function (e) {
                if (e.target.files && e.target.files[0]) loadImageFile(e.target.files[0]);
            });
            dropzone.addEventListener("click", function (e) {
                if (e.target.closest(".btn")) return;
                imageInput.click();
            });
            dropzone.addEventListener("keydown", function (e) {
                if (e.key === "Enter" || e.key === " ") { e.preventDefault(); imageInput.click(); }
            });
            dropzone.addEventListener("dragover", function (e) {
                e.preventDefault(); dropzone.classList.add("is-dragover");
            });
            dropzone.addEventListener("dragleave", function (e) {
                e.preventDefault(); dropzone.classList.remove("is-dragover");
            });
            dropzone.addEventListener("drop", function (e) {
                e.preventDefault(); dropzone.classList.remove("is-dragover");
                if (e.dataTransfer.files && e.dataTransfer.files[0]) loadImageFile(e.dataTransfer.files[0]);
            });
        }

        if (resetImageButton) {
            resetImageButton.addEventListener("click", function () {
                abortExtract(); extracting = false; activeExtractToken = ++extractToken; updateExtractControls();
                clearSelectedImage();
            });
        }

        document.addEventListener("paste", function (e) {
            var items = e.clipboardData && e.clipboardData.items;
            if (!items || items.length === 0) return;
            for (var i=0; i<items.length; i++) {
                if (items[i].type.indexOf("image") !== -1) {
                    var file = items[i].getAsFile();
                    if (file) {
                        e.preventDefault();
                        loadImageFile(file);
                    }
                    break;
                }
            }
        });

        function applyExtractedGrid(grid) {
            abortRequest("solve"); abortRequest("validate");
            state.solving=false; state.validating=false; updateControls();
            state.grid = cloneGrid(grid);
            state.clueMask = grid.map(function (r){ return r.map(function(v){ return v!==0; }); });
            state.solvedMask = falses();
            clearResult();
            renderAll();
            markStale();
        }

        function extractImage() {
            if (!selectedImageFile || extracting) return;
            abortExtract();
            var token = extractToken + 1; extractToken = token; activeExtractToken = token;
            var controller = new AbortController(); extractController = controller;
            extracting = true; updateExtractControls();
            setUploadStatus("Extracting Sudoku from image…", "info"); setUploadWarnings([]);

            var formData = new FormData();
            formData.append("image", selectedImageFile);
            fetch(extractUrl, { method: "POST", body: formData, signal: controller.signal })
                .then(function (r) { return r.json().then(function(d){ return {response:r, data:d}; }); })
                .then(function (res) {
                    if (token !== activeExtractToken) return;
                    var d = res.data || {};
                    if (res.response.ok && d.status === "ok" && Array.isArray(d.grid)) {
                        applyExtractedGrid(d.grid);
                        setUploadStatus(d.message || "Sudoku grid extracted successfully.", "success");
                        setUploadWarnings(Array.isArray(d.warnings) ? d.warnings : []);
                        return;
                    }
                    var msg = (d.error && d.error.message) || d.message || "Failed to extract Sudoku from image.";
                    setUploadStatus(msg, "error");
                    setUploadWarnings(Array.isArray(d.warnings) ? d.warnings : []);
                })
                .catch(function (err) {
                    if (!isAbort(err)) setUploadStatus(NETWORK_MESSAGE, "error");
                })
                .then(function () {
                    if (token === activeExtractToken) {
                        extractController = null; extracting = false; updateExtractControls();
                    }
                });
        }
        if (extractButton) extractButton.addEventListener("click", extractImage);
        clearSelectedImage(); updateExtractControls();
        buildGrid();
        renderAll();
        updateControls();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
