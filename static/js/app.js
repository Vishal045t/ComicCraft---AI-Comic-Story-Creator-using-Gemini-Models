(function () {
  var form = document.getElementById("comic-form");
  if (!form) return;

  var overlay = document.getElementById("progress");
  var fill = document.getElementById("bar-fill");
  var msg = document.getElementById("progress-msg");
  var bar = overlay.querySelector(".bar");
  var errorBox = document.getElementById("form-error");
  var button = document.getElementById("submit-btn");
  var prompt = document.getElementById("prompt");

  document.querySelectorAll(".chip").forEach(function (chip) {
    chip.addEventListener("click", function () {
      prompt.value = chip.dataset.idea;
      prompt.focus();
    });
  });

  function showError(text) {
    errorBox.textContent = text;
    errorBox.hidden = false;
    overlay.hidden = true;
    button.disabled = false;
  }

  function setProgress(pct, text) {
    fill.style.width = pct + "%";
    bar.setAttribute("aria-valuenow", pct);
    if (text) msg.textContent = text;
  }

  function poll(jobId, failures) {
    fetch("/api/jobs/" + jobId)
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
      .then(function (res) {
        if (!res.ok) { showError(res.data.detail || "The job was lost. Please try again."); return; }
        var job = res.data;
        setProgress(job.progress, job.message);
        if (job.status === "done") { window.location.href = "/comic/" + job.comic_id; return; }
        if (job.status === "error") { showError(job.error || "Generation failed. Please try again."); return; }
        setTimeout(function () { poll(jobId, 0); }, 1500);
      })
      .catch(function () {
        if (failures >= 5) { showError("Lost connection to the server. Is it still running?"); return; }
        setTimeout(function () { poll(jobId, failures + 1); }, 2000);
      });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    errorBox.hidden = true;
    var promptText = prompt.value.trim();
    var name = document.getElementById("character_name").value.trim();
    if (promptText.length < 5) { showError("Describe your story in at least a few words."); prompt.focus(); return; }
    if (!name) { showError("Give your main character a name."); document.getElementById("character_name").focus(); return; }

    button.disabled = true;
    setProgress(2, "Starting…");
    overlay.hidden = false;

    fetch("/api/jobs", { method: "POST", body: new FormData(form) })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
      .then(function (res) {
        if (!res.ok) { showError(res.data.detail || "Please check your input."); return; }
        poll(res.data.job_id, 0);
      })
      .catch(function () { showError("Could not reach the server. Is it running?"); });
  });
})();
