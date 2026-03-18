async function requestJSON(url, method, payload) {
  const response = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: payload ? JSON.stringify(payload) : undefined,
  });
  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || `Request failed: ${response.status}`);
  }
  return response.json();
}

document.getElementById("api-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  try {
    await requestJSON("/api/apis", "POST", {
      name: form.name.value,
      base_url: form.base_url.value,
      auth_token: form.auth_token.value,
      enabled: form.enabled.checked,
      readonly_mode: form.readonly_mode.checked,
    });
    location.reload();
  } catch (err) {
    alert(`Unable to create API: ${err.message}`);
  }
});

document.querySelectorAll(".perm-form").forEach((form) => {
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await requestJSON("/api/permissions", "POST", {
        api_id: form.dataset.apiId,
        name: form.name.value,
        method: form.method.value,
        path_pattern: form.path_pattern.value,
        risk: "low",
        enabled: true,
      });
      location.reload();
    } catch (err) {
      alert(`Unable to create permission: ${err.message}`);
    }
  });
});

document.getElementById("client-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  try {
    const data = await requestJSON("/api/clients", "POST", {
      name: form.name.value,
      auto_grant_readonly: form.auto_grant_readonly.checked,
    });
    alert(`Client created. API key:\n\n${data.api_key}\n\nThis key is also visible in the client card.`);
    location.reload();
  } catch (err) {
    alert(`Unable to create client: ${err.message}`);
  }
});

document.querySelectorAll(".grant-form").forEach((form) => {
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const selected = [...form.querySelectorAll("input[name='permission_ids']:checked")].map((el) => Number(el.value));
    try {
      await requestJSON(`/api/clients/${form.dataset.clientId}/permissions`, "POST", {
        permission_ids: selected,
      });
      alert("Grants updated.");
    } catch (err) {
      alert(`Unable to save grants: ${err.message}`);
    }
  });
});

async function toggleApi(id, field, value) {
  try {
    await requestJSON(`/api/apis/${id}`, "PATCH", { [field]: value });
    location.reload();
  } catch (err) {
    alert(`Unable to update API: ${err.message}`);
  }
}

async function togglePermission(id, enabled) {
  try {
    await requestJSON(`/api/permissions/${id}`, "PATCH", { enabled });
    location.reload();
  } catch (err) {
    alert(`Unable to update permission: ${err.message}`);
  }
}

async function deleteApi(id, name) {
  if (!confirm(`Delete external API "${name}" and all its rules/grants?`)) {
    return;
  }
  try {
    await requestJSON(`/api/apis/${id}`, "DELETE");
    location.reload();
  } catch (err) {
    alert(`Unable to delete API: ${err.message}`);
  }
}

async function deletePermission(id) {
  if (!confirm("Delete this permission rule?")) {
    return;
  }
  try {
    await requestJSON(`/api/permissions/${id}`, "DELETE");
    location.reload();
  } catch (err) {
    alert(`Unable to delete permission: ${err.message}`);
  }
}

async function updateApiToken(id) {
  const input = document.getElementById(`token-input-${id}`);
  if (!input) {
    return;
  }
  const authToken = input.value.trim();
  if (!authToken) {
    alert("Enter a token value first.");
    return;
  }

  try {
    await requestJSON(`/api/apis/${id}`, "PATCH", { auth_token: authToken });
    alert("Upstream token updated.");
    input.value = "";
    location.reload();
  } catch (err) {
    alert(`Unable to update token: ${err.message}`);
  }
}

async function deleteClient(id, name) {
  if (!confirm(`Delete internal client "${name}"?`)) {
    return;
  }
  try {
    await requestJSON(`/api/clients/${id}`, "DELETE");
    location.reload();
  } catch (err) {
    alert(`Unable to delete client: ${err.message}`);
  }
}

async function grantReadonlyNow(id) {
  try {
    const data = await requestJSON(`/api/clients/${id}/grant-readonly`, "POST");
    alert(`Granted ${data.granted_count} read-only rules.`);
    location.reload();
  } catch (err) {
    alert(`Unable to grant read-only rules: ${err.message}`);
  }
}

async function toggleClient(id, active) {
  try {
    await requestJSON(`/api/clients/${id}`, "PATCH", { active });
    location.reload();
  } catch (err) {
    alert(`Unable to update client: ${err.message}`);
  }
}

async function rotateClientKey(id) {
  if (!confirm("Rotate this key? Existing integrations using the old key will stop working.")) {
    return;
  }
  try {
    const data = await requestJSON(`/api/clients/${id}/rotate-key`, "POST");
    alert(`New key:\n\n${data.api_key}\n\nThe UI will refresh and keep this key visible.`);
    location.reload();
  } catch (err) {
    alert(`Unable to rotate key: ${err.message}`);
  }
}

async function copyClientKey(id) {
  const input = document.getElementById(`client-key-${id}`);
  if (!input) {
    return;
  }
  try {
    await navigator.clipboard.writeText(input.value);
    alert("API key copied to clipboard.");
  } catch {
    input.select();
    document.execCommand("copy");
    alert("API key copied.");
  }
}

function setGrantSelection(triggerButton, mode) {
  const form = triggerButton.closest("form");
  if (!form) {
    return;
  }
  const checkboxes = [...form.querySelectorAll("input[name='permission_ids']")];
  checkboxes.forEach((checkbox) => {
    if (mode === "all") {
      checkbox.checked = true;
    } else if (mode === "none") {
      checkbox.checked = false;
    } else {
      checkbox.checked = ["GET", "HEAD", "OPTIONS"].includes((checkbox.dataset.method || "").toUpperCase());
    }
  });
}

window.toggleApi = toggleApi;
window.togglePermission = togglePermission;
window.deleteApi = deleteApi;
window.deletePermission = deletePermission;
window.updateApiToken = updateApiToken;
window.toggleClient = toggleClient;
window.deleteClient = deleteClient;
window.grantReadonlyNow = grantReadonlyNow;
window.rotateClientKey = rotateClientKey;
window.copyClientKey = copyClientKey;
window.setGrantSelection = setGrantSelection;
