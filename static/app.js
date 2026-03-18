async function postJSON(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || `Request failed: ${response.status}`);
  }
  return response.json();
}

async function patchJSON(url, payload) {
  const response = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
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
    await postJSON("/api/apis", {
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
      await postJSON("/api/permissions", {
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
    const data = await postJSON("/api/clients", { name: form.name.value });
    const keyBox = document.getElementById("new-key-box");
    keyBox.classList.remove("d-none");
    keyBox.innerHTML = `<strong>Copy this key now.</strong><br><code>${data.api_key}</code>`;
    form.reset();
    setTimeout(() => location.reload(), 800);
  } catch (err) {
    alert(`Unable to create client: ${err.message}`);
  }
});

document.querySelectorAll(".grant-form").forEach((form) => {
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const selected = [...form.querySelectorAll("input[name='permission_ids']:checked")].map((el) => Number(el.value));
    try {
      await postJSON(`/api/clients/${form.dataset.clientId}/permissions`, {
        permission_ids: selected,
      });
      location.reload();
    } catch (err) {
      alert(`Unable to save grants: ${err.message}`);
    }
  });
});

async function toggleApi(id, field, value) {
  try {
    await patchJSON(`/api/apis/${id}`, { [field]: value });
    location.reload();
  } catch (err) {
    alert(`Unable to update API: ${err.message}`);
  }
}

async function togglePermission(id, enabled) {
  try {
    await patchJSON(`/api/permissions/${id}`, { enabled });
    location.reload();
  } catch (err) {
    alert(`Unable to update permission: ${err.message}`);
  }
}

window.toggleApi = toggleApi;
window.togglePermission = togglePermission;
