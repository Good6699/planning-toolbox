const bootText = document.getElementById("boot_text");
const progressBar = document.getElementById("progress_bar");
const _startTime = Date.now();

async function pollStatus() {
    try {
        const r = await fetch("/api/splash/status");
        const data = await r.json();
        bootText.innerText = data.text || "INITIALIZING...";
        progressBar.style.width = (data.progress || 0) + "%";
        if (data.phase >= 7) return;
    } catch (e) {
        bootText.innerText = "INITIALIZING...";
    }
    if (Date.now() - _startTime > 15000) return;
    setTimeout(pollStatus, 250);
}

setTimeout(pollStatus, 200);
