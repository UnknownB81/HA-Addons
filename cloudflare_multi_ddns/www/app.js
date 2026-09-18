const elements = {
  form: document.querySelector("#config-form"),
  token: document.querySelector("#api-token"),
  tokenHint: document.querySelector("#token-hint"),
  interval: document.querySelector("#interval"),
  dryRun: document.querySelector("#dry-run"),
  createMissing: document.querySelector("#create-missing"),
  ipv4Url: document.querySelector("#ipv4-url"),
  ipv6Url: document.querySelector("#ipv6-url"),
  records: document.querySelector("#records"),
  template: document.querySelector("#record-template"),
  recordCount: document.querySelector("#record-count"),
  zoneCount: document.querySelector("#zone-count"),
  testButton: document.querySelector("#test-button"),
  syncButton: document.querySelector("#sync-button"),
  saveButton: document.querySelector("#save-button"),
  saveState: document.querySelector("#save-state"),
  statusBadge: document.querySelector("#status-badge"),
  statusLabel: document.querySelector("#status-label"),
  lastSuccess: document.querySelector("#last-success"),
  changedCount: document.querySelector("#changed-count"),
  unchangedCount: document.querySelector("#unchanged-count"),
  toast: document.querySelector("#toast"),
};

let hasToken = false;
let toastTimer;
let availableZones = [];

async function api(path, options = {}) {
  const response = await fetch(`./api/${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "Une erreur est survenue");
  return body;
}

function showToast(message, error = false) {
  clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.className = `toast visible${error ? " error" : ""}`;
  toastTimer = setTimeout(() => { elements.toast.className = "toast"; }, 4200);
}

function populateZoneSelect(select, selectedZone = "") {
  select.replaceChildren(new Option("Automatique", ""));
  availableZones.forEach((zone) => select.add(new Option(zone, zone)));
  if (selectedZone && !availableZones.includes(selectedZone)) {
    select.add(new Option(selectedZone, selectedZone));
  }
  select.value = selectedZone;
}

function setAvailableZones(zones) {
  availableZones = zones.map((zone) => zone.name);
  elements.records.querySelectorAll(".record-zone").forEach((select) => {
    populateZoneSelect(select, select.value);
  });
  elements.zoneCount.textContent = `${zones.length} zone${zones.length > 1 ? "s" : ""} accessible${zones.length > 1 ? "s" : ""}`;
}

function addRecord(record = {}) {
  const fragment = elements.template.content.cloneNode(true);
  const card = fragment.querySelector(".record-card");
  card.querySelector(".record-name").value = record.name || "";
  card.querySelector(".record-type").value = record.type || "A";
  populateZoneSelect(card.querySelector(".record-zone"), record.zone || "");
  card.querySelector(".record-proxied").value = record.proxied === true ? "true" : record.proxied === false ? "false" : "";
  card.querySelector(".record-ttl").value = record.ttl || "";
  card.querySelector(".delete-record").addEventListener("click", () => {
    card.remove();
    updateRecordNumbers();
  });
  elements.records.append(card);
  updateRecordNumbers();
}

function updateRecordNumbers() {
  const cards = [...elements.records.querySelectorAll(".record-card")];
  cards.forEach((card, index) => { card.querySelector(".record-index").textContent = index + 1; });
  elements.recordCount.textContent = cards.length;
  const empty = elements.records.querySelector(".empty-state");
  if (cards.length === 0 && !empty) {
    const message = document.createElement("div");
    message.className = "empty-state";
    message.textContent = "Ajoutez votre premier enregistrement DNS.";
    elements.records.append(message);
  } else if (cards.length > 0 && empty) {
    empty.remove();
  }
}

function collectConfig() {
  const records = [...elements.records.querySelectorAll(".record-card")].map((card) => {
    const record = {
      name: card.querySelector(".record-name").value.trim(),
      type: card.querySelector(".record-type").value,
    };
    const zone = card.querySelector(".record-zone").value.trim();
    const proxied = card.querySelector(".record-proxied").value;
    const ttl = card.querySelector(".record-ttl").value;
    if (zone) record.zone = zone;
    if (proxied) record.proxied = proxied === "true";
    if (ttl) record.ttl = Number(ttl);
    return record;
  });
  return {
    api_token: elements.token.value,
    interval: Number(elements.interval.value),
    create_missing: elements.createMissing.checked,
    dry_run: elements.dryRun.checked,
    ipv4_url: elements.ipv4Url.value.trim(),
    ipv6_url: elements.ipv6Url.value.trim(),
    records,
  };
}

function populateConfig(config) {
  hasToken = config.has_token;
  elements.tokenHint.textContent = hasToken ? "Un jeton est enregistré; laissez vide pour le conserver" : "Aucun jeton enregistré";
  elements.interval.value = config.interval;
  elements.dryRun.checked = config.dry_run;
  elements.createMissing.checked = config.create_missing;
  elements.ipv4Url.value = config.ipv4_url;
  elements.ipv6Url.value = config.ipv6_url;
  elements.records.replaceChildren();
  config.records.forEach(addRecord);
  updateRecordNumbers();
}

function renderStatus(status) {
  const labels = { waiting: "À configurer", idle: "Opérationnel", running: "Synchronisation", error: "Erreur" };
  elements.statusBadge.className = `status-badge ${status.state}`;
  elements.statusLabel.textContent = labels[status.state] || status.state;
  elements.lastSuccess.textContent = status.last_success ? new Date(status.last_success).toLocaleString("fr-CA") : "Jamais";
  elements.changedCount.textContent = status.changed;
  elements.unchangedCount.textContent = status.unchanged;
  elements.syncButton.disabled = status.state === "running";
  if (status.error && elements.statusBadge.dataset.error !== status.error) {
    elements.statusBadge.dataset.error = status.error;
    showToast(status.error, true);
  }
}

async function load() {
  try {
    const [config, status] = await Promise.all([api("config"), api("status")]);
    populateConfig(config);
    renderStatus(status);
    if (hasToken) {
      try {
        const result = await api("test", { method: "POST", body: JSON.stringify({ api_token: "" }) });
        setAvailableZones(result.zones);
      } catch (_) {
        elements.zoneCount.textContent = "Zones temporairement indisponibles";
      }
    }
  } catch (error) {
    showToast(error.message, true);
  }
}

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!elements.form.reportValidity()) return;
  elements.saveButton.disabled = true;
  elements.saveState.textContent = "Enregistrement…";
  try {
    const config = await api("config", { method: "PUT", body: JSON.stringify(collectConfig()) });
    populateConfig(config);
    elements.token.value = "";
    elements.saveState.textContent = "Configuration enregistrée";
    showToast("Configuration enregistrée");
  } catch (error) {
    elements.saveState.textContent = "";
    showToast(error.message, true);
  } finally {
    elements.saveButton.disabled = false;
  }
});

elements.testButton.addEventListener("click", async () => {
  if (!elements.token.value && !hasToken) {
    showToast("Saisissez d’abord un jeton Cloudflare", true);
    return;
  }
  elements.testButton.disabled = true;
  try {
    const result = await api("test", { method: "POST", body: JSON.stringify({ api_token: elements.token.value }) });
    setAvailableZones(result.zones);
    showToast("Connexion Cloudflare réussie");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    elements.testButton.disabled = false;
  }
});

elements.syncButton.addEventListener("click", async () => {
  elements.syncButton.disabled = true;
  try {
    await api("sync", { method: "POST", body: "{}" });
    showToast("Synchronisation démarrée");
  } catch (error) {
    showToast(error.message, true);
    elements.syncButton.disabled = false;
  }
});

document.querySelector("#add-record").addEventListener("click", () => addRecord());
load();
setInterval(async () => {
  try { renderStatus(await api("status")); } catch (_) { /* prochain essai automatique */ }
}, 3000);