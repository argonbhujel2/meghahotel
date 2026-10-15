async function meghaUpload(fileInput, folder, urlInputId) {
  var file = fileInput.files && fileInput.files[0];
  if (!file) return;
  var status = fileInput.parentElement.querySelector(".upload-status");
  if (status) status.textContent = "Uploading…";
  var fd = new FormData();
  fd.append("file", file);
  fd.append("folder", folder || "misc");
  // CSRF from meta or hidden
  var csrf = document.querySelector('meta[name="csrf-token"]');
  var token = csrf ? csrf.content : (document.querySelector('input[name="csrf_token"]') || {}).value;
  try {
    var res = await fetch("/admin/upload", {
      method: "POST",
      headers: token ? { "X-CSRFToken": token } : {},
      body: fd,
    });
    var data = await res.json();
    if (!res.ok) throw new Error(data.error || "Upload failed");
    var input = document.getElementById(urlInputId);
    if (input) input.value = data.url;
    var preview = document.getElementById(urlInputId + "-preview");
    if (preview) {
      preview.src = data.url;
      preview.style.display = "block";
    }
    if (status) status.textContent = "Uploaded ✓";
  } catch (e) {
    if (status) status.textContent = e.message;
    alert(e.message);
  }
}
