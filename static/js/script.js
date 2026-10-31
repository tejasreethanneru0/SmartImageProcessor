document.addEventListener("DOMContentLoaded", () => {
    let originalFilename = null;
    let currentFilename = null;
    let originalUrl = null;
    let currentUrl = null;
    let busy = false;

    const $ = (id) => document.getElementById(id);
    const uploadForm = $("uploadForm");
    const imageInput = $("imageInput");
    const uploadButton = $("uploadButton");
    const uploadStatus = $("uploadStatus");
    const fileName = $("fileName");
    const originalPreview = $("originalPreview");
    const currentPreview = $("currentPreview");
    const originalPlaceholder = $("originalPlaceholder");
    const currentPlaceholder = $("currentPlaceholder");
    const imageMeta = $("imageMeta");
    const processStatus = $("processStatus");
    const resetButton = $("resetButton");
    const downloadButton = $("downloadButton");
    const historyList = $("historyList");

    function setStatus(element, message, isError = false) {
        element.textContent = message || "";
        element.classList.toggle("error", isError);
    }

    function setBusy(value) {
        busy = value;
        document.querySelectorAll(".process-button").forEach(button => {
            button.disabled = value || !currentFilename;
        });
        uploadButton.disabled = value;
    }

    function showImage(img, placeholder, url) {
        img.src = url + (url.includes("?") ? "&" : "?") + "t=" + Date.now();
        img.hidden = false;
        placeholder.hidden = true;
    }

    function updateCurrent(result) {
        currentFilename = result.filename;
        currentUrl = result.url;
        showImage(currentPreview, currentPlaceholder, currentUrl);
        downloadButton.href = currentUrl;
        downloadButton.download = currentFilename;
        downloadButton.classList.remove("disabled");
        downloadButton.setAttribute("aria-disabled", "false");
        resetButton.disabled = false;
        imageMeta.textContent = `${result.width} × ${result.height} · ${result.format} · ${(result.size / 1024).toFixed(1)} KB`;
    }

    async function readJson(response) {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || "Something went wrong.");
        return data;
    }

    async function refreshHistory() {
        try {
            const response = await fetch("/api/history");
            const items = await readJson(response);
            if (!items.length) {
                historyList.innerHTML = '<p class="empty-history">Your processed images will appear here.</p>';
                return;
            }
            historyList.innerHTML = items.map(item => `
                <div class="history-item">
                    <div>
                        <strong>${escapeHtml(item.message)}</strong>
                        <small>${escapeHtml(item.created)} · ${item.width} × ${item.height} · ${item.format} · ${(item.size / 1024).toFixed(1)} KB</small>
                    </div>
                    <a href="/media/processed/${encodeURIComponent(item.filename)}" download="${escapeHtml(item.filename)}">Download</a>
                </div>
            `).join("");
        } catch {
            historyList.innerHTML = '<p class="empty-history">Could not load history.</p>';
        }
    }

    function escapeHtml(value) {
        return String(value).replace(/[&<>"']/g, char => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
        })[char]);
    }

    imageInput.addEventListener("change", () => {
        fileName.textContent = imageInput.files[0]?.name || "No file selected";
    });

    uploadForm.addEventListener("submit", async event => {
        event.preventDefault();
        if (busy) return;
        const file = imageInput.files[0];
        if (!file) {
            setStatus(uploadStatus, "Choose an image first.", true);
            return;
        }

        const formData = new FormData();
        formData.append("image", file);
        setBusy(true);
        setStatus(uploadStatus, "Uploading image...");

        try {
            const response = await fetch("/api/upload", { method: "POST", body: formData });
            const result = await readJson(response);
            originalFilename = result.filename;
            currentFilename = result.filename;
            originalUrl = result.url;
            currentUrl = result.url;

            showImage(originalPreview, originalPlaceholder, originalUrl);
            showImage(currentPreview, currentPlaceholder, currentUrl);
            imageMeta.textContent = `${result.width} × ${result.height} · ${result.format} · ${(result.size / 1024).toFixed(1)} KB`;
            downloadButton.href = currentUrl;
            downloadButton.download = currentFilename;
            downloadButton.classList.remove("disabled");
            downloadButton.setAttribute("aria-disabled", "false");
            resetButton.disabled = false;
            setStatus(uploadStatus, result.message);
            setStatus(processStatus, "");
            document.querySelectorAll(".process-button").forEach(button => button.disabled = false);
            $("cropRight").value = result.width;
            $("cropBottom").value = result.height;
            $("resizeWidth").value = result.width;
            $("resizeHeight").value = result.height;
        } catch (error) {
            setStatus(uploadStatus, error.message, true);
        } finally {
            setBusy(false);
            document.querySelectorAll(".process-button").forEach(button => button.disabled = !currentFilename);
        }
    });

    $("keepRatio").addEventListener("change", event => {
        $("heightField").hidden = event.target.checked;
    });

    $("quality").addEventListener("input", event => {
        $("qualityValue").textContent = event.target.value;
    });

    $("brightness").addEventListener("input", event => {
        $("brightnessValue").textContent = Number(event.target.value).toFixed(1);
    });

    $("contrast").addEventListener("input", event => {
        $("contrastValue").textContent = Number(event.target.value).toFixed(1);
    });

    $("filterEffect").addEventListener("change", event => {
        $("blurField").hidden = event.target.value !== "blur";
    });

    function operationPayload(action) {
        const payload = { filename: currentFilename, operation: action };

        if (action === "resize") {
            payload.width = Number($("resizeWidth").value);
            payload.keep_ratio = $("keepRatio").checked;
            payload.height = Number($("resizeHeight").value);
        } else if (action === "compress") {
            payload.quality = Number($("quality").value);
        } else if (action === "crop") {
            payload.left = Number($("cropLeft").value);
            payload.top = Number($("cropTop").value);
            payload.right = Number($("cropRight").value);
            payload.bottom = Number($("cropBottom").value);
        } else if (action === "rotate") {
            payload.degrees = Number($("rotation").value);
        } else if (action === "flip") {
            payload.direction = $("flipDirection").value;
        } else if (action === "convert") {
            payload.format = $("outputFormat").value;
        } else if (action === "adjust") {
            payload.brightness = Number($("brightness").value);
            payload.contrast = Number($("contrast").value);
        } else if (action === "filter") {
            payload.effect = $("filterEffect").value;
            payload.radius = Number($("blurRadius").value);
        }
        return payload;
    }

    document.querySelectorAll(".process-button").forEach(button => {
        button.addEventListener("click", async () => {
            if (busy) return;
            if (!currentFilename) {
                setStatus(processStatus, "Upload an image first.", true);
                return;
            }

            const action = button.dataset.action;
            setBusy(true);
            setStatus(processStatus, "Processing image...");

            try {
                const response = await fetch("/api/process", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(operationPayload(action))
                });
                const result = await readJson(response);
                updateCurrent(result);
                setStatus(processStatus, result.message);
                await refreshHistory();
            } catch (error) {
                setStatus(processStatus, error.message, true);
            } finally {
                setBusy(false);
                document.querySelectorAll(".process-button").forEach(item => {
                    item.disabled = !currentFilename;
                });
            }
        });
    });

    resetButton.addEventListener("click", () => {
        if (!originalFilename || !originalUrl) return;
        currentFilename = originalFilename;
        currentUrl = originalUrl;
        showImage(currentPreview, currentPlaceholder, currentUrl);
        downloadButton.href = currentUrl;
        downloadButton.download = currentFilename;
        imageMeta.textContent = "Restored original image";
        setStatus(processStatus, "Preview reset to the original upload. Previous processed files remain in history.");
    });

    $("clearHistory").addEventListener("click", async () => {
        try {
            const response = await fetch("/api/history", { method: "DELETE" });
            const result = await readJson(response);
            setStatus(processStatus, result.message);
            await refreshHistory();
        } catch (error) {
            setStatus(processStatus, error.message, true);
        }
    });

    refreshHistory();
    document.querySelectorAll(".process-button").forEach(button => button.disabled = true);
});
