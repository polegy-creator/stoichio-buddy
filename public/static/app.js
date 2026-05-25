const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

const api = {
  async get(path) {
    const response = await fetch(path);
    if (!response.ok) throw new Error(await errorMessage(response));
    return response.json();
  },
  async send(path, method, body = undefined) {
    const headers = {};
    const pin = localStorage.getItem("stoichioAdminPin") || "";
    if (pin) headers["X-Stoichio-Pin"] = pin;
    let payload;
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }
    const response = await fetch(path, { method, headers, body: payload });
    if (!response.ok) throw new Error(await errorMessage(response));
    return response.json();
  },
  async upload(path, formData) {
    const headers = {};
    const pin = localStorage.getItem("stoichioAdminPin") || "";
    if (pin) headers["X-Stoichio-Pin"] = pin;
    const response = await fetch(path, { method: "POST", headers, body: formData });
    if (!response.ok) throw new Error(await errorMessage(response));
    return response.json();
  },
};

const state = {
  powders: {},
  inventory: {},
  inventoryLog: [],
  densities: {},
  msdsInventory: [],
  closets: { 1: "Powders", 2: "Acids", 3: "Flammables", 4: "Fridge" },
  history: [],
  linkedRecipes: [],
  powderSets: {},
  selectedPowders: new Set(["Fe2O3", "TiO2"]),
  favoritePowders: new Set(),
  recentPowdersByTarget: {},
  savedDensityChoices: {},
  lastRecipe: null,
  lastRecipeMass: null,
  lastDensityResult: null,
  densityTargetAutoSynced: true,
  selectedDensityReviewKey: "",
  densityPickerExpanded: {
    heightDensityChoice: false,
    relativeDensityChoice: false,
  },
};

const pageMeta = {
  "powder-mass": ["Powder Mass Calculation", ""],
  "target-density": ["Target Density %", ""],
  "powders-inventory": ["Powder & Inventory", ""],
  "inventory-msds": ["Inventory & MSDS", ""],
  "material-density": ["Theoretical Density", ""],
  "data-health": ["Data Health", ""],
  history: ["History", ""],
};

const els = {
  serviceStatus: $("#serviceStatus"),
  adminPin: $("#adminPin"),
  savePin: $("#savePin"),
  themeToggle: $("#themeToggle"),
  quickMode: $("#quickMode"),
  globalMessage: $("#globalMessage"),
  pageTitle: $("#pageTitle"),
  pageSubtitle: $("#pageSubtitle"),
  powderCount: $("#powderCount"),
  densityCount: $("#densityCount"),
  historyCount: $("#historyCount"),

  targetFormula: $("#targetFormula"),
  recipeTargetFor: $("#recipeTargetFor"),
  recipeTargetPreview: $("#recipeTargetPreview"),
  targetMassLabel: $("#targetMassLabel"),
  targetMass: $("#targetMass"),
  targetHeight: $("#targetHeight"),
  targetDiameter: $("#targetDiameter"),
  targetPorosity: $("#targetPorosity"),
  heightDensityChoice: $("#heightDensityChoice"),
  manualHeightDensityWrap: $("#manualHeightDensityWrap"),
  heightDensity: $("#heightDensity"),
  heightMassPreview: $("#heightMassPreview"),
  showAllPowders: $("#showAllPowders"),
  reloadPowders: $("#reloadPowders"),
  powderFilterHint: $("#powderFilterHint"),
  powderSetBox: $("#powderSetBox"),
  powderList: $("#powderList"),
  recipeForm: $("#recipeForm"),
  recipeMessage: $("#recipeMessage"),
  recipeQuickSummary: $("#recipeQuickSummary"),
  recipeMetrics: $("#recipeMetrics"),
  recipeTableBody: $("#recipeTable tbody"),
  recipeDetails: $("#recipeDetails"),
  recipeNotes: $("#recipeNotes"),
  saveRecipe: $("#saveRecipe"),
  saveAndDeductRecipe: $("#saveAndDeductRecipe"),
  deductInventory: $("#deductInventory"),
  copyRecipeNotebook: $("#copyRecipeNotebook"),
  printRecipeLabel: $("#printRecipeLabel"),
  recipeSummary: $("#recipeSummary"),

  linkedRecipe: $("#linkedRecipe"),
  linkedRecipeInfo: $("#linkedRecipeInfo"),
  densityTargetFormula: $("#densityTargetFormula"),
  densityTargetFor: $("#densityTargetFor"),
  densityTargetPreview: $("#densityTargetPreview"),
  finalDiameter: $("#finalDiameter"),
  finalHeight: $("#finalHeight"),
  finalMass: $("#finalMass"),
  relativeDensityChoice: $("#relativeDensityChoice"),
  manualRelativeDensityWrap: $("#manualRelativeDensityWrap"),
  relativeTheoreticalDensity: $("#relativeTheoreticalDensity"),
  densityForm: $("#densityForm"),
  densityResult: $("#densityResult"),
  densityMetrics: $("#densityMetrics"),
  densityNotes: $("#densityNotes"),
  saveDensityHistory: $("#saveDensityHistory"),
  densitySummary: $("#densitySummary"),

  addPowderForm: $("#addPowderForm"),
  newPowderFormula: $("#newPowderFormula"),
  newPowderPurity: $("#newPowderPurity"),
  newPowderCompany: $("#newPowderCompany"),
  newPowderGrams: $("#newPowderGrams"),
  inventoryForm: $("#inventoryForm"),
  inventoryPowder: $("#inventoryPowder"),
  inventoryCurrent: $("#inventoryCurrent"),
  inventoryGrams: $("#inventoryGrams"),
  inventoryAdd: $("#inventoryAdd"),
  inventoryRemove: $("#inventoryRemove"),
  deletePowderForm: $("#deletePowderForm"),
  deletePowder: $("#deletePowder"),
  removeDeletedStock: $("#removeDeletedStock"),
  powderDatabaseTableBody: $("#powderDatabaseTable tbody"),
  dataHealthGrid: $("#dataHealthGrid"),
  msdsPdfHealthList: $("#msdsPdfHealthList"),
  lowStockDashboard: $("#lowStockDashboard"),
  inventoryTableBody: $("#inventoryTable tbody"),
  ledgerTableBody: $("#ledgerTable tbody"),

  msdsForm: $("#msdsForm"),
  newMsdsMaterial: $("#newMsdsMaterial"),
  msdsItemId: $("#msdsItemId"),
  msdsFormMode: $("#msdsFormMode"),
  msdsCasNumber: $("#msdsCasNumber"),
  msdsNameFormula: $("#msdsNameFormula"),
  msdsLookupStatus: $("#msdsLookupStatus"),
  msdsPurity: $("#msdsPurity"),
  msdsCompany: $("#msdsCompany"),
  msdsClosetNumber: $("#msdsClosetNumber"),
  msdsExternalUrl: $("#msdsExternalUrl"),
  msdsPdfFile: $("#msdsPdfFile"),
  saveMsdsMaterial: $("#saveMsdsMaterial"),
  uploadMsdsFile: $("#uploadMsdsFile"),
  msdsBinderDownload: $("#msdsBinderDownload"),
  msdsSearch: $("#msdsSearch"),
  msdsClosetFilter: $("#msdsClosetFilter"),
  msdsTableBody: $("#msdsTable tbody"),

  materialDensityForm: $("#materialDensityForm"),
  materialFormula: $("#materialFormula"),
  materialPhase: $("#materialPhase"),
  densityEntryMode: $("#densityEntryMode"),
  latticeFields: $("#latticeFields"),
  unitCellFields: $("#unitCellFields"),
  manualDensityFields: $("#manualDensityFields"),
  crystalSystem: $("#crystalSystem"),
  latticeAWrap: $("#latticeAWrap"),
  latticeBWrap: $("#latticeBWrap"),
  latticeCWrap: $("#latticeCWrap"),
  latticeAlphaWrap: $("#latticeAlphaWrap"),
  latticeBetaWrap: $("#latticeBetaWrap"),
  latticeGammaWrap: $("#latticeGammaWrap"),
  latticeA: $("#latticeA"),
  latticeB: $("#latticeB"),
  latticeC: $("#latticeC"),
  latticeAlpha: $("#latticeAlpha"),
  latticeBeta: $("#latticeBeta"),
  latticeGamma: $("#latticeGamma"),
  latticeSystemHint: $("#latticeSystemHint"),
  unitCellVolume: $("#unitCellVolume"),
  zField: $("#zField"),
  zValue: $("#zValue"),
  manualMaterialDensity: $("#manualMaterialDensity"),
  materialDensityPreview: $("#materialDensityPreview"),
  densitySourceUrl: $("#densitySourceUrl"),
  densityRecordNotes: $("#densityRecordNotes"),
  densityVerifiedBy: $("#densityVerifiedBy"),
  densityVerifiedCheck: $("#densityVerifiedCheck"),
  densitySearch: $("#densitySearch"),
  densityReviewScope: $("#densityReviewScope"),
  densityReviewRecord: $("#densityReviewRecord"),
  densityReviewDetails: $("#densityReviewDetails"),
  densityReviewBy: $("#densityReviewBy"),
  densityReviewDate: $("#densityReviewDate"),
  densityMarkChecked: $("#densityMarkChecked"),
  densityMakePreferred: $("#densityMakePreferred"),
  densityDoNotUse: $("#densityDoNotUse"),
  materialDensityTableBody: $("#materialDensityTable tbody"),

  historySearch: $("#historySearch"),
  historyOwnerFilter: $("#historyOwnerFilter"),
  historyStatusFilter: $("#historyStatusFilter"),
  historyLog: $("#historyLog"),

  confirmModal: $("#confirmModal"),
  confirmTitle: $("#confirmTitle"),
  confirmMessage: $("#confirmMessage"),
  confirmCancel: $("#confirmCancel"),
  confirmAccept: $("#confirmAccept"),
};

async function errorMessage(response) {
  try {
    const data = await response.json();
    return data.detail || data.error || JSON.stringify(data);
  } catch {
    return response.statusText;
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatNumber(value, digits = 4) {
  if (value === null || value === undefined || value === "") return "";
  const number = Number(value);
  if (!Number.isFinite(number)) return "";
  return number.toFixed(digits).replace(/\.?0+$/, "");
}

function closetLabel(closetNumber) {
  const number = Number(closetNumber);
  const name = state.closets[number] || "";
  return name ? `${number} \u2014 ${name}` : "";
}

function closetOptionsHtml(includeAll = false) {
  const options = includeAll ? [`<option value="">All closets</option>`] : [];
  for (const number of [1, 2, 3, 4]) {
    options.push(`<option value="${number}">${escapeHtml(closetLabel(number))}</option>`);
  }
  return options.join("");
}

function msdsStatus(item) {
  if (item.msdsFileName || item.msdsStatus === "uploaded") return "PDF uploaded";
  if (item.msdsExternalUrl || item.msdsStatus === "link only") return "source only";
  return "missing PDF";
}

function powderLabel(powder) {
  return state.powders[powder]?.display_name || powder;
}

function powderFormula(powder) {
  return state.powders[powder]?.formula || powder.split(" | ")[0];
}

function statusPill(status) {
  const kind = status === "PDF uploaded" ? "good" : status === "source only" ? "warning" : "missing";
  return `<span class="status-pill ${kind}">${escapeHtml(status)}</span>`;
}

function setMessage(element, text, kind = "") {
  element.hidden = false;
  element.className = `message ${kind}`.trim();
  element.textContent = text;
}

function flash(text, kind = "good") {
  setMessage(els.globalMessage, text, kind);
  window.setTimeout(() => {
    els.globalMessage.hidden = true;
  }, 5000);
}

function setBusy(button, busyText = "Working...") {
  const previous = button.textContent;
  button.disabled = true;
  button.textContent = busyText;
  return () => {
    button.disabled = false;
    button.textContent = previous;
  };
}

function confirmDanger(title, message, confirmText = "Confirm") {
  return new Promise((resolve) => {
    els.confirmTitle.textContent = title;
    els.confirmMessage.textContent = message;
    els.confirmAccept.textContent = confirmText;
    els.confirmModal.hidden = false;
    document.body.classList.add("modal-open");

    const finish = (accepted) => {
      els.confirmModal.hidden = true;
      document.body.classList.remove("modal-open");
      els.confirmCancel.removeEventListener("click", onCancel);
      els.confirmAccept.removeEventListener("click", onAccept);
      els.confirmModal.removeEventListener("click", onBackdrop);
      document.removeEventListener("keydown", onKey);
      resolve(accepted);
    };
    const onCancel = () => finish(false);
    const onAccept = () => finish(true);
    const onBackdrop = (event) => {
      if (event.target === els.confirmModal) finish(false);
    };
    const onKey = (event) => {
      if (event.key === "Escape") finish(false);
    };

    els.confirmCancel.addEventListener("click", onCancel);
    els.confirmAccept.addEventListener("click", onAccept);
    els.confirmModal.addEventListener("click", onBackdrop);
    document.addEventListener("keydown", onKey);
    els.confirmCancel.focus();
  });
}

function selectedAmountMode() {
  return $("input[name='amountMode']:checked").value;
}

function selectedRecipeMassBasis() {
  return "total_precursor_powder";
}

function recipeInputMassLabel() {
  return "target formula mass";
}

function densityRecordLabel(record, prefix = "") {
  const phase = record.phase ? `, ${record.phase}` : "";
  const status = record.verification_status ? ` - ${record.verification_status}` : "";
  return `${prefix}${record.display_name || record.formula}${phase}: ${formatNumber(record.theoretical_density_g_cm3, 5)} g/cm³${status}`;
}

function densityStatus(record) {
  return String(record.verification_status || "").toLowerCase();
}

function isPreferredDensity(record) {
  return densityStatus(record).includes("preferred");
}

function isTrustedDensity(record) {
  const status = densityStatus(record);
  return status.includes("preferred") || status.includes("checked") || status.includes("verified");
}

function displayDensityStatus(record) {
  const status = densityStatus(record);
  if (status.includes("preferred")) return "Preferred";
  if (status.includes("checked") || status.includes("verified")) return "Verified";
  if (status.includes("do not use")) return "Do not use";
  if (status.includes("codex") || status.includes("unverified")) return "Needs review";
  return record.verification_status || "";
}

function densityNeedsReview(record) {
  const status = densityStatus(record);
  return !status.includes("checked") && !status.includes("preferred") && !status.includes("do not use");
}

function densityRecordId(record) {
  return record.record_key || record.record_id || record.formula || "";
}

function densityChoiceValue(select) {
  const key = select.value;
  if (!key || key === "__manual__" || key === "__show_more__") return null;
  return state.densities[key] || null;
}

function theoreticalDensityFromSelect(select, manualInput) {
  const record = densityChoiceValue(select);
  if (record) return Number(record.theoretical_density_g_cm3);
  return Number(manualInput.value);
}

function densitySourceFromSelect(select) {
  const record = densityChoiceValue(select);
  if (!record) return "Manual theoretical density";
  return densityRecordLabel(record);
}

function linkedRecipeById(entryId) {
  return state.linkedRecipes.find((entry) => entry.entry_id === entryId) || null;
}

function normalizeOwner(value) {
  return String(value || "").trim();
}

function loadJsonSetting(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function saveJsonSetting(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function currentTargetKey() {
  return els.targetFormula.value.trim().toLowerCase() || "__blank__";
}

function recentPowdersForCurrentTarget() {
  return Array.isArray(state.recentPowdersByTarget[currentTargetKey()])
    ? state.recentPowdersByTarget[currentTargetKey()]
    : [];
}

function persistPowderComfortSettings() {
  saveJsonSetting("stoichioFavoritePowders", Array.from(state.favoritePowders));
  saveJsonSetting("stoichioRecentPowdersByTarget", state.recentPowdersByTarget);
}

function rememberRecentPowders(powders) {
  const key = currentTargetKey();
  const previous = Array.isArray(state.recentPowdersByTarget[key]) ? state.recentPowdersByTarget[key] : [];
  const next = [...powders, ...previous]
    .filter((powder, index, list) => powder && list.indexOf(powder) === index)
    .slice(0, 8);
  state.recentPowdersByTarget[key] = next;
  persistPowderComfortSettings();
}

function sortPowderOptions(options) {
  const recent = recentPowdersForCurrentTarget();
  return [...options].sort((a, b) => {
    const favoriteRank = Number(!state.favoritePowders.has(a)) - Number(!state.favoritePowders.has(b));
    if (favoriteRank !== 0) return favoriteRank;
    const recentA = recent.includes(a) ? recent.indexOf(a) : 999;
    const recentB = recent.includes(b) ? recent.indexOf(b) : 999;
    if (recentA !== recentB) return recentA - recentB;
    const selectedRank = Number(!state.selectedPowders.has(a)) - Number(!state.selectedPowders.has(b));
    if (selectedRank !== 0) return selectedRank;
    return a.localeCompare(b);
  });
}

function persistRecipeSettings() {
  const checkedAmountMode = $("input[name='amountMode']:checked");
  saveJsonSetting("stoichioRecipeSettings", {
    targetFormula: els.targetFormula.value,
    recipeTargetFor: els.recipeTargetFor.value,
    targetMass: els.targetMass.value,
    targetHeight: els.targetHeight.value,
    targetDiameter: els.targetDiameter.value,
    targetPorosity: els.targetPorosity.value,
    heightDensity: els.heightDensity.value,
    recipeNotes: els.recipeNotes.value,
    showAllPowders: els.showAllPowders.checked,
    amountMode: checkedAmountMode ? checkedAmountMode.value : "mass",
    selectedPowders: Array.from(state.selectedPowders),
    densityChoices: {
      heightDensityChoice: els.heightDensityChoice.value,
      relativeDensityChoice: els.relativeDensityChoice.value,
    },
  });
}

function restoreRecipeSettings() {
  state.favoritePowders = new Set(loadJsonSetting("stoichioFavoritePowders", []));
  state.recentPowdersByTarget = loadJsonSetting("stoichioRecentPowdersByTarget", {});
  const settings = loadJsonSetting("stoichioRecipeSettings", null);
  if (!settings) return;

  if (settings.targetFormula) els.targetFormula.value = settings.targetFormula;
  if (settings.recipeTargetFor) els.recipeTargetFor.value = settings.recipeTargetFor;
  if (settings.targetMass) els.targetMass.value = settings.targetMass;
  if (settings.targetHeight) els.targetHeight.value = settings.targetHeight;
  if (settings.targetDiameter) els.targetDiameter.value = settings.targetDiameter;
  if (settings.targetPorosity) els.targetPorosity.value = settings.targetPorosity;
  if (settings.heightDensity) els.heightDensity.value = settings.heightDensity;
  if (settings.recipeNotes) els.recipeNotes.value = settings.recipeNotes;
  els.showAllPowders.checked = Boolean(settings.showAllPowders);
  if (Array.isArray(settings.selectedPowders) && settings.selectedPowders.length) {
    state.selectedPowders = new Set(settings.selectedPowders);
  }
  if (settings.amountMode) {
    const restoredAmountMode = settings.amountMode === "height" ? "height" : "mass";
    const amountMode = $(`input[name='amountMode'][value="${restoredAmountMode}"]`);
    if (amountMode) amountMode.checked = true;
  }
  state.savedDensityChoices = settings.densityChoices || {};
}

async function loadAll() {
  const data = await api.get("/api/bootstrap");
  applyData(data);
  await loadPowderOptions();
}

function applyData(data) {
  if (data.health) {
    els.serviceStatus.textContent = data.health.storage_mode;
    if (data.health.storage_error) {
      els.serviceStatus.textContent += ` (${data.health.storage_error})`;
    }
  }
  state.powders = data.powders || state.powders;
  state.inventory = data.inventory || state.inventory;
  state.inventoryLog = data.inventory_log || state.inventoryLog;
  state.msdsInventory = data.msds_inventory || data.items || state.msdsInventory;
  state.closets = data.closets || state.closets;
  state.densities = data.densities || state.densities;
  state.history = data.history || state.history;
  state.linkedRecipes = data.linked_recipes || state.linkedRecipes;
  state.powderSets = data.powder_sets || state.powderSets;
  renderEverything();
}

function renderEverything() {
  els.powderCount.textContent = Object.keys(state.powders).length;
  els.densityCount.textContent = Object.keys(state.densities).length;
  els.historyCount.textContent = state.history.length;
  renderInventorySelectors();
  renderPowderDatabase();
  renderInventoryTables();
  renderMsdsInventory();
  renderDataHealth();
  renderDensityChoices();
  renderLinkedRecipes();
  renderMaterialDensityTable();
  renderHistory();
}

async function loadPowderOptions() {
  const params = new URLSearchParams({
    target: els.targetFormula.value.trim(),
    show_all: String(els.showAllPowders.checked),
  });
  const data = await api.get(`/api/powders?${params.toString()}`);
  state.powders = data.powders || state.powders;
  const options = data.options || Object.keys(state.powders);

  state.selectedPowders = new Set(
    Array.from(state.selectedPowders).filter((powder) => options.includes(powder)),
  );
  for (const powder of ["Fe2O3", "TiO2"]) {
    if (options.includes(powder)) state.selectedPowders.add(powder);
  }

  renderPowderList(options, data);
  renderPowderSets(data.matching_powder_sets || []);
  renderPowderDatabase();
}

function renderPowderList(options, data) {
  els.powderList.innerHTML = "";
  const orderedOptions = sortPowderOptions(options);
  if (data.filter_error) {
    els.powderFilterHint.textContent = `Filter error: ${data.filter_error}`;
  } else if (els.showAllPowders.checked) {
    els.powderFilterHint.textContent = `${Object.keys(state.powders).length} powders`;
  } else {
    const elements = (data.target_elements || []).join(", ");
    els.powderFilterHint.textContent = elements
      ? `${orderedOptions.length} relevant · ${elements} · ${(data.hidden || []).length} hidden`
      : `${orderedOptions.length} powders`;
  }

  if (!orderedOptions.length) {
    els.powderList.innerHTML = `<div class="empty-state">No matching powders.</div>`;
    return;
  }

  const recent = recentPowdersForCurrentTarget();
  for (const powder of orderedOptions) {
    const record = state.powders[powder] || {};
    const favorite = state.favoritePowders.has(powder);
    const isRecent = recent.includes(powder);
    const row = document.createElement("div");
    row.className = "selector-row";
    row.innerHTML = `
      <button type="button" class="icon favorite-toggle ${favorite ? "active" : ""}" data-favorite-powder="${escapeHtml(powder)}" title="${favorite ? "Remove favorite powder" : "Favorite this powder"}">${favorite ? "&#9733;" : "&#9734;"}</button>
      <label>
        <input type="checkbox" value="${escapeHtml(powder)}">
        <span>${escapeHtml(powderLabel(powder))}</span>
      </label>
      <span class="pill">${formatNumber(record.molar_mass_g_mol, 3)} g/mol</span>
      ${record.purity ? `<span class="pill">${escapeHtml(record.purity)}</span>` : ""}
      <span class="pill">${record.available_g === null || record.available_g === undefined ? "no stock" : `${formatNumber(record.available_g, 3)} g`}</span>
      ${favorite ? `<span class="pill comfort">favorite</span>` : isRecent ? `<span class="pill comfort">recent</span>` : ""}
    `;
    const checkbox = row.querySelector("input");
    checkbox.checked = state.selectedPowders.has(powder);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) state.selectedPowders.add(powder);
      else state.selectedPowders.delete(powder);
      persistRecipeSettings();
    });
    row.querySelector("[data-favorite-powder]").addEventListener("click", () => {
      if (state.favoritePowders.has(powder)) state.favoritePowders.delete(powder);
      else state.favoritePowders.add(powder);
      persistPowderComfortSettings();
      renderPowderList(options, data);
    });
    els.powderList.appendChild(row);
  }
}

function renderPowderSets(matchingSets) {
  if (!matchingSets.length) {
    els.powderSetBox.hidden = true;
    els.powderSetBox.innerHTML = "";
    return;
  }
  els.powderSetBox.hidden = false;
  els.powderSetBox.innerHTML = `
    <strong>Saved powder sets</strong>
    ${matchingSets.map((record) => `
      <div class="inline-actions">
        <span>${escapeHtml(record.name || record.record_id)} (${escapeHtml((record.powders || []).map(powderLabel).join(", "))})</span>
        <button type="button" class="secondary" data-apply-set="${escapeHtml(record.record_id)}">Apply</button>
        <button type="button" class="icon" data-delete-set="${escapeHtml(record.record_id)}" title="Delete powder set">&#128465;</button>
      </div>
    `).join("")}
  `;
  els.powderSetBox.querySelectorAll("[data-apply-set]").forEach((button) => {
    button.addEventListener("click", () => {
      const record = matchingSets.find((item) => item.record_id === button.dataset.applySet);
      state.selectedPowders = new Set((record?.powders || []).filter((powder) => state.powders[powder]));
      loadPowderOptions().catch((error) => flash(error.message, "error"));
    });
  });
  els.powderSetBox.querySelectorAll("[data-delete-set]").forEach((button) => {
    button.addEventListener("click", async () => {
      const accepted = await confirmDanger(
        "Delete powder set?",
        "This removes the saved powder combination. Powder database and inventory stay unchanged.",
        "Delete Set",
      );
      if (!accepted) return;
      await api.send(`/api/powder-sets/${encodeURIComponent(button.dataset.deleteSet)}`, "DELETE");
      flash("Powder set deleted.");
      await loadAll();
    });
  });
}

function densityOptionHtml(record, prefix) {
  return `<option value="${escapeHtml(record.record_key)}">${escapeHtml(densityRecordLabel(record, prefix))}</option>`;
}

async function updateDensityChoicesForTarget(target, select, manualWrap) {
  const data = await api.get(`/api/densities?target=${encodeURIComponent(target || "")}`);
  state.densities = data.records || state.densities;
  const targetKey = String(target || "").trim().toLowerCase();
  const sameTargetAsLastRender = select.dataset.lastTarget === targetKey;
  const previous = select.value || state.savedDensityChoices[select.id] || "";
  const expanded = state.densityPickerExpanded[select.id] === true;
  const exact = (data.exact || []).slice().sort((a, b) => Number(isPreferredDensity(b)) - Number(isPreferredDensity(a)));
  const related = data.related || [];
  const visibleRelated = expanded ? related : related.slice(0, 6);
  const hiddenRelated = Math.max(0, related.length - visibleRelated.length);

  select.innerHTML = `<option value="__manual__">Manual theoretical density</option>`;
  for (const record of exact) {
    select.insertAdjacentHTML("beforeend", densityOptionHtml(record, isPreferredDensity(record) ? "Preferred exact - " : "Exact - "));
  }
  for (const record of visibleRelated) {
    if (!isTrustedDensity(record)) {
      select.insertAdjacentHTML("beforeend", densityOptionHtml(record, "Related - "));
      continue;
    }
    select.insertAdjacentHTML("beforeend", densityOptionHtml(record, isPreferredDensity(record) ? "Preferred related - " : "Checked related - "));
  }
  if (hiddenRelated > 0) {
    select.insertAdjacentHTML("beforeend", `<option value="__show_more__">Show ${hiddenRelated} more related density record(s)</option>`);
  }
  const previousIsSpecificRecord = previous && previous !== "__manual__" && previous !== "__show_more__";
  if (sameTargetAsLastRender && previousIsSpecificRecord && [...select.options].some((option) => option.value === previous)) {
    select.value = previous;
  } else if (sameTargetAsLastRender && previous === "__manual__") {
    select.value = "__manual__";
  } else if (select.options.length > 1) {
    select.selectedIndex = 1;
  }
  select.dataset.lastTarget = targetKey;
  state.savedDensityChoices[select.id] = select.value;
  manualWrap.hidden = select.value !== "__manual__";
}

function targetDensityFormulaForChoices() {
  return els.densityTargetFormula.value.trim() || els.targetFormula.value.trim();
}

function syncTargetDensityFormulaFromRecipeTarget({ force = false } = {}) {
  const recipeTarget = els.targetFormula.value.trim();
  if (recipeTarget && (force || state.densityTargetAutoSynced || !els.densityTargetFormula.value.trim())) {
    els.densityTargetFormula.value = recipeTarget;
    state.densityTargetAutoSynced = true;
  }
  return targetDensityFormulaForChoices();
}

function renderDensityChoices() {
  updateDensityChoicesForTarget(els.targetFormula.value, els.heightDensityChoice, els.manualHeightDensityWrap)
    .then(previewHeightMass)
    .catch(() => {});
  updateDensityChoicesForTarget(syncTargetDensityFormulaFromRecipeTarget(), els.relativeDensityChoice, els.manualRelativeDensityWrap)
    .catch(() => {});
}

async function previewHeightMass() {
  if (selectedAmountMode() !== "height") {
    els.heightMassPreview.textContent = "";
    return;
  }
  const density = theoreticalDensityFromSelect(els.heightDensityChoice, els.heightDensity);
  const height = Number(els.targetHeight.value);
  const diameter = Number(els.targetDiameter.value);
  const porosity = Number(els.targetPorosity.value || 0);
  if (!(density > 0 && height > 0 && diameter > 0)) {
    els.heightMassPreview.textContent = "Enter height and density to calculate target formula mass.";
    return;
  }
  try {
    const data = await api.send("/api/target-mass-from-height", "POST", {
      theoretical_density_g_cm3: density,
      height_mm: height,
      diameter_mm: diameter,
      target_porosity_percent: porosity,
    });
    els.heightMassPreview.textContent = `Target formula mass = ${formatNumber(data.target_mass_g, 6)} g · solid volume = ${formatNumber(data.solid_volume_cm3, 6)} cm³`;
  } catch (error) {
    els.heightMassPreview.textContent = error.message;
  }
}

async function currentTargetMass() {
  if (selectedAmountMode() !== "height") {
    return Number(els.targetMass.value);
  }
  const density = theoreticalDensityFromSelect(els.heightDensityChoice, els.heightDensity);
  const data = await api.send("/api/target-mass-from-height", "POST", {
    theoretical_density_g_cm3: density,
    height_mm: Number(els.targetHeight.value),
    diameter_mm: Number(els.targetDiameter.value),
    target_porosity_percent: Number(els.targetPorosity.value || 0),
  });
  return Number(data.target_mass_g);
}

async function calculateRecipe(event) {
  event.preventDefault();
  setMessage(els.recipeMessage, "Calculating...");
  renderRecipeEmptyState("Calculating...");
  els.recipeMetrics.innerHTML = "";
  els.recipeSummary.textContent = "";
  els.recipeQuickSummary.textContent = "Calculating...";
  els.recipeQuickSummary.className = "recipe-summary-card empty";

  try {
    const mass = await currentTargetMass();
    const payload = {
      target: els.targetFormula.value.trim(),
      mass_g: mass,
      selected_powders: Array.from(state.selectedPowders),
      mass_basis: selectedRecipeMassBasis(),
    };
    const data = await api.send("/api/recipe", "POST", payload);
    state.lastRecipe = { payload, result: data.result, stock_ok: data.stock_ok, stock_messages: data.stock_messages };
    state.lastRecipeMass = mass;
    rememberRecentPowders(payload.selected_powders);
    persistRecipeSettings();
    renderRecipeResult(data, mass);
  } catch (error) {
    setMessage(els.recipeMessage, error.message, "error");
    renderRecipeEmptyState("No recipe.");
    els.recipeQuickSummary.textContent = "Recipe calculation failed.";
    els.recipeQuickSummary.className = "recipe-summary-card empty";
  }
}

function renderRecipeEmptyState(text = "No powder masses yet.") {
  els.recipeTableBody.innerHTML = `
    <tr>
      <td colspan="4" class="empty-table">${escapeHtml(text)}</td>
    </tr>
  `;
}

function renderRecipeResult(data, mass) {
  const result = data.result || {};
  if (!result.recipe) {
    setMessage(els.recipeMessage, result.warning || "No recipe generated", "error");
    renderRecipeEmptyState("No powder recipe could be generated.");
    els.recipeQuickSummary.textContent = result.warning || "No recipe.";
    els.recipeQuickSummary.className = "recipe-summary-card empty";
    return;
  }

  setMessage(
    els.recipeMessage,
    result.warning || (data.stock_ok ? "Recipe calculated." : data.stock_messages.join("; ")),
    data.stock_ok && !result.warning ? "good" : "warning",
  );

  const inputMass = result.input_mass ?? mass;
  els.recipeDetails.textContent =
    `Target formula mass: ${formatNumber(inputMass, 6)} g; stoichiometry: ${result.exact ? "exact" : "approx"}; residual: ${formatNumber(result.residual, 10)}.`;
  els.recipeMetrics.innerHTML = `
    <div class="metric-card"><strong>${formatNumber(inputMass, 6)}</strong><small>target formula mass g</small></div>
    <div class="metric-card"><strong>${Object.keys(result.recipe || {}).length}</strong><small>powders</small></div>
    <div class="metric-card"><strong>${result.exact ? "Exact" : "Approx"}</strong><small>stoichiometry</small></div>
  `;
  els.recipeQuickSummary.className = `recipe-summary-card ${data.stock_ok ? "" : "warning"}`.trim();
  els.recipeQuickSummary.innerHTML = recipeOneLineSummaryHtml(result, mass, data.stock_ok);

  els.recipeTableBody.innerHTML = "";
  for (const [powder, grams] of Object.entries(result.recipe)) {
    const available = data.inventory[powder];
    const after = available === undefined ? null : Number(available) - Number(grams);
    const tr = document.createElement("tr");
    tr.className = after !== null && after < 0 ? "short" : after !== null && after < 10 ? "low" : "";
    tr.innerHTML = `
      <td>${escapeHtml(powderLabel(powder))}</td>
      <td>${formatNumber(grams, 6)}</td>
      <td>${available === undefined ? "Not in inventory" : formatNumber(available, 3)}</td>
      <td>${after === null ? "" : formatNumber(after, 3)}</td>
    `;
    els.recipeTableBody.appendChild(tr);
  }

  els.recipeSummary.textContent = recipeSummaryText(result, mass);
}

function recipeOneLineSummaryHtml(result, mass, stockOk) {
  const powders = Object.entries(result.recipe || {})
    .map(([powder, grams]) => `${powderLabel(powder)} ${formatNumber(grams, 6)} g`)
    .join(" | ");
  const inputMass = result.input_mass ?? mass;
  const badges = [
    `<span class="summary-badge ${result.exact ? "good" : "warning"}">${result.exact ? "Exact" : "Approx"}</span>`,
    stockOk ? `<span class="summary-badge good">Stock OK</span>` : `<span class="summary-badge warning">Stock warning</span>`,
  ].join("");
  return `
    <div><strong>${escapeHtml(result.normalized_target || els.targetFormula.value.trim())}</strong> | ${formatNumber(inputMass, 6)} g ${escapeHtml(recipeInputMassLabel())} | ${escapeHtml(powders)}</div>
    <div class="summary-badges">${badges}</div>
  `;
}

function recipeSummaryText(result, mass) {
  const inputMass = result.input_mass ?? mass;
  const lines = [
    `Target: ${result.normalized_target || els.targetFormula.value.trim()}`,
    `Target for: ${normalizeOwner(els.recipeTargetFor.value) || "quick calculation"}`,
    `${recipeInputMassLabel()}: ${formatNumber(inputMass, 6)} g`,
    "Powders:",
  ];
  for (const [powder, grams] of Object.entries(result.recipe || {})) {
    lines.push(`- ${powderLabel(powder)}: ${formatNumber(grams, 6)} g`);
  }
  if (els.recipeNotes.value.trim()) lines.push(`Notes: ${els.recipeNotes.value.trim()}`);
  return lines.join("\n");
}

function recipeNotebookText(result, mass) {
  const inputMass = result.input_mass ?? mass;
  const lines = [
    `Stoichio Buddy recipe`,
    `Date: ${niceTime(new Date().toISOString())}`,
    `Target: ${result.normalized_target || els.targetFormula.value.trim()}`,
    `Target for: ${normalizeOwner(els.recipeTargetFor.value) || "quick calculation"}`,
    `${recipeInputMassLabel()}: ${formatNumber(inputMass, 6)} g`,
    `Stoichiometry: ${result.exact ? "Exact" : "Approx"}`,
    `Residual: ${formatNumber(result.residual, 10)}`,
    `Powders:`,
  ];
  for (const [powder, grams] of Object.entries(result.recipe || {})) {
    const available = state.inventory[powder];
    const after = available === undefined ? "" : `, after recipe ${formatNumber(Number(available) - Number(grams), 3)} g`;
    lines.push(`- ${powderLabel(powder)}: ${formatNumber(grams, 6)} g${available === undefined ? " (not tracked in inventory)" : `, available ${formatNumber(available, 3)} g${after}`}`);
  }
  if (state.lastRecipe?.stock_messages?.length) {
    lines.push(`Inventory warning: ${state.lastRecipe.stock_messages.join("; ")}`);
  }
  if (els.recipeNotes.value.trim()) lines.push(`Notes: ${els.recipeNotes.value.trim()}`);
  return lines.join("\n");
}

async function copyTextToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      // Fall through to the textarea copy path, which is more forgiving in some browsers.
    }
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) throw new Error("Browser clipboard permission was not available.");
}

async function copyRecipeToNotebook() {
  if (!state.lastRecipe?.result?.recipe) {
    flash("Calculate a recipe before copying.", "warning");
    return;
  }
  const text = recipeNotebookText(state.lastRecipe.result, state.lastRecipeMass);
  try {
    await copyTextToClipboard(text);
    flash("Recipe copied for the lab notebook.");
  } catch (error) {
    els.recipeSummary.textContent = text;
    flash("Clipboard was blocked, so the lab-notebook text is ready in the summary box below.", "warning");
  }
}

async function saveRecipe() {
  if (!state.lastRecipe?.result?.recipe) {
    flash("Calculate a recipe before saving.", "warning");
    return;
  }
  const done = setBusy(els.saveRecipe, "Saving...");
  try {
    const data = await api.send("/api/history/recipe", "POST", {
      ...state.lastRecipe.payload,
      mass_g: state.lastRecipeMass,
      result: state.lastRecipe.result,
      notes: els.recipeNotes.value,
      target_for: els.recipeTargetFor.value,
      inventory_deducted: false,
    });
    state.history = data.history || state.history;
    state.linkedRecipes = data.linked_recipes || state.linkedRecipes;
    renderEverything();
    flash(`Saved recipe ${data.saved_entry?.recipe_id || ""}`.trim());
  } catch (error) {
    flash(error.message, "error");
  } finally {
    done();
  }
}

async function saveRecipeAndDeductInventory() {
  if (!state.lastRecipe?.result?.recipe) {
    flash("Calculate a recipe before saving and deducting inventory.", "warning");
    return;
  }
  const shortage = (state.lastRecipe.stock_messages || []).join(" ");
  const message = shortage
    ? `This will save the recipe and deduct inventory. Stock warning: ${shortage}`
    : "This will save the recipe and immediately deduct the powder masses from inventory.";
  const accepted = await confirmDanger("Save recipe and deduct inventory?", message, "Save + Deduct");
  if (!accepted) return;

  const done = setBusy(els.saveAndDeductRecipe, "Saving...");
  try {
    const data = await api.send("/api/history/recipe-and-deduct", "POST", {
      ...state.lastRecipe.payload,
      mass_g: state.lastRecipeMass,
      result: state.lastRecipe.result,
      notes: els.recipeNotes.value,
      target_for: els.recipeTargetFor.value,
      inventory_deducted: true,
    });
    state.history = data.history || state.history;
    state.linkedRecipes = data.linked_recipes || state.linkedRecipes;
    state.inventory = data.inventory || state.inventory;
    state.inventoryLog = data.inventory_log || state.inventoryLog;
    renderEverything();
    flash(`Saved recipe and deducted inventory ${data.saved_entry?.recipe_id || ""}`.trim());
  } catch (error) {
    flash(error.message, "error");
  } finally {
    done();
  }
}

async function deductInventory() {
  if (!state.lastRecipe?.result?.recipe) {
    flash("Calculate a recipe before deducting inventory.", "warning");
    return;
  }
  const accepted = await confirmDanger(
    "Deduct inventory?",
    "This will subtract the current recipe powder masses from inventory without saving a new recipe record.",
    "Deduct Inventory",
  );
  if (!accepted) return;
  const done = setBusy(els.deductInventory, "Deducting...");
  try {
    const data = await api.send("/api/inventory/deduct", "POST", {
      recipe: state.lastRecipe.result.recipe,
      reason: "Confirmed recipe deduction from Vercel lab website",
      recipe_id: state.lastRecipe.result.normalized_target || "",
    });
    state.inventory = data.inventory || state.inventory;
    state.inventoryLog = data.inventory_log || state.inventoryLog;
    renderEverything();
    flash("Inventory deducted.");
  } catch (error) {
    flash(error.message, "error");
  } finally {
    done();
  }
}

function printRecipeLabel() {
  if (!state.lastRecipe?.result?.recipe) {
    flash("Calculate a recipe before printing.", "warning");
    return;
  }
  const result = state.lastRecipe.result;
  const owner = normalizeOwner(els.recipeTargetFor.value) || "Quick calculation";
  const date = niceTime(new Date().toISOString());
  const rows = Object.entries(result.recipe || {})
    .map(([powder, grams]) => {
      const available = state.inventory[powder];
      const after = available === undefined ? "" : formatNumber(Number(available) - Number(grams), 3);
      const warn = available !== undefined && Number(available) < Number(grams) ? "short" : "";
      return `<tr class="${warn}"><td>${escapeHtml(powder)}</td><td>${formatNumber(grams, 6)} g</td><td>${available === undefined ? "not tracked" : `${formatNumber(available, 3)} g`}</td><td>${after ? `${after} g` : ""}</td></tr>`;
    })
    .join("");
  const notes = els.recipeNotes.value.trim();
  const popup = window.open("", "_blank", "width=780,height=900");
  if (!popup) {
    flash("The browser blocked the print window.", "warning");
    return;
  }
  popup.document.write(`
    <!doctype html>
    <html>
    <head>
      <title>Stoichio recipe label</title>
      <style>
        body { color: #111; font-family: Arial, sans-serif; margin: 24px; }
        h1 { font-size: 24px; margin: 0 0 8px; }
        .meta { color: #444; margin-bottom: 18px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #bbb; padding: 8px; text-align: left; }
        th { background: #eef3f5; }
        tr.short td { background: #ffe2df; }
        .box { border: 1px solid #bbb; margin-top: 14px; padding: 10px; white-space: pre-wrap; }
        @media print { button { display: none; } body { margin: 10mm; } }
      </style>
    </head>
    <body>
      <button onclick="window.print()">Print</button>
      <h1>${escapeHtml(result.normalized_target || els.targetFormula.value.trim())}</h1>
      <div class="meta">${escapeHtml(owner)} | ${escapeHtml(date)} | ${escapeHtml(recipeInputMassLabel())} ${formatNumber(result.input_mass ?? state.lastRecipeMass, 6)} g</div>
      <table>
        <thead><tr><th>Powder</th><th>Mass</th><th>Available before</th><th>After recipe</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <div class="box">Target formula mass: ${formatNumber(result.input_mass ?? state.lastRecipeMass, 6)} g
Stoichiometry: ${result.exact ? "Exact" : "Approx"}
Residual: ${formatNumber(result.residual, 10)}</div>
      ${notes ? `<div class="box"><strong>Notes</strong><br>${escapeHtml(notes)}</div>` : ""}
    </body>
    </html>
  `);
  popup.document.close();
  popup.focus();
}

function renderLinkedRecipes() {
  els.linkedRecipe.innerHTML = `<option value="">New target not linked to a recipe</option>`;
  for (const entry of state.linkedRecipes) {
    const label = `${entry.target_id || entry.recipe_id || entry.entry_id} - ${entry.target}${entry.target_for ? ` for ${entry.target_for}` : ""}`;
    els.linkedRecipe.insertAdjacentHTML("beforeend", `<option value="${escapeHtml(entry.entry_id)}">${escapeHtml(label)}</option>`);
  }
}

function onLinkedRecipeChange() {
  const linked = linkedRecipeById(els.linkedRecipe.value);
  if (!linked) {
    els.linkedRecipeInfo.textContent = "";
    state.densityPickerExpanded.relativeDensityChoice = false;
    updateDensityChoicesForTarget(
      syncTargetDensityFormulaFromRecipeTarget(),
      els.relativeDensityChoice,
      els.manualRelativeDensityWrap,
    ).catch(() => {});
    return;
  }
  els.densityTargetFormula.value = linked.target || "";
  state.densityTargetAutoSynced = false;
  els.densityTargetFor.value = linked.target_for || "";
  els.linkedRecipeInfo.textContent = `After-sintering density will be linked to ${linked.target_id || linked.recipe_id}.`;
  state.densityPickerExpanded.relativeDensityChoice = false;
  updateDensityChoicesForTarget(els.densityTargetFormula.value, els.relativeDensityChoice, els.manualRelativeDensityWrap).catch(() => {});
}

async function calculateDensity(event) {
  event.preventDefault();
  syncTargetDensityFormulaFromRecipeTarget();
  try {
    const theoretical = theoreticalDensityFromSelect(els.relativeDensityChoice, els.relativeTheoreticalDensity);
    const payload = {
      final_mass_g: Number(els.finalMass.value),
      final_diameter_mm: Number(els.finalDiameter.value),
      final_height_mm: Number(els.finalHeight.value),
      theoretical_density_g_cm3: theoretical,
    };
    const data = await api.send("/api/relative-density", "POST", payload);
    state.lastDensityResult = { payload, result: data };
    renderDensityResult(data, theoretical);
  } catch (error) {
    setMessage(els.densityResult, error.message, "error");
  }
}

function renderDensityResult(data, theoretical) {
  const relative = Number(data.relative_density_percent);
  setMessage(
    els.densityResult,
    relative > 100
      ? "Relative density is above 100%. Check dimensions, mass, or theoretical density."
      : "Target density calculated.",
    relative > 100 ? "warning" : "good",
  );
  els.densityMetrics.innerHTML = `
    <div class="metric-card"><strong>${formatNumber(data.measured_density_g_cm3, 5)}</strong><small>measured density g/cm³</small></div>
    <div class="metric-card"><strong>${formatNumber(theoretical, 5)}</strong><small>theoretical density g/cm³</small></div>
    <div class="metric-card"><strong>${formatNumber(relative, 2)}%</strong><small>relative density</small></div>
  `;
  els.densitySummary.textContent = [
    `Target: ${targetDensityFormulaForChoices()}`,
    `Target for: ${normalizeOwner(els.densityTargetFor.value) || "quick calculation"}`,
    `Measured density: ${formatNumber(data.measured_density_g_cm3, 5)} g/cm³`,
    `Theoretical density: ${formatNumber(theoretical, 5)} g/cm³`,
    `Relative density: ${formatNumber(relative, 2)}%`,
    `Final volume: ${formatNumber(data.final_volume_cm3, 6)} cm³`,
    `Density source: ${densitySourceFromSelect(els.relativeDensityChoice)}`,
    els.densityNotes.value.trim() ? `Notes: ${els.densityNotes.value.trim()}` : "",
  ].filter(Boolean).join("\n");
}

async function saveDensityHistory() {
  if (!state.lastDensityResult) {
    flash("Calculate target density before saving.", "warning");
    return;
  }
  const done = setBusy(els.saveDensityHistory, "Saving...");
  try {
    const payload = {
      ...state.lastDensityResult.payload,
      target: targetDensityFormulaForChoices(),
      target_for: els.densityTargetFor.value.trim(),
      density_source: densitySourceFromSelect(els.relativeDensityChoice),
      notes: els.densityNotes.value,
      linked_recipe_entry_id: els.linkedRecipe.value,
    };
    const data = await api.send("/api/history/target-density", "POST", payload);
    state.history = data.history || state.history;
    state.linkedRecipes = data.linked_recipes || state.linkedRecipes;
    renderEverything();
    flash(`Saved target density ${data.saved_entry?.target_id || ""}`.trim());
  } catch (error) {
    flash(error.message, "error");
  } finally {
    done();
  }
}

function renderInventorySelectors() {
  const powderNames = Object.keys(state.powders).sort();
  for (const select of [els.inventoryPowder, els.deletePowder]) {
    const previous = select.value;
    select.innerHTML = `<option value="">Choose powder</option>`;
    for (const powder of powderNames) {
      select.insertAdjacentHTML("beforeend", `<option value="${escapeHtml(powder)}">${escapeHtml(powderLabel(powder))}</option>`);
    }
    if (powderNames.includes(previous)) select.value = previous;
  }
  renderInventoryAdjustment();
}

function renderInventoryAdjustment() {
  const powder = els.inventoryPowder.value;
  if (!powder) {
    setMessage(els.inventoryCurrent, "Choose a powder to see current stock.");
    return;
  }
  const current = Number(state.inventory[powder] || 0);
  setMessage(
    els.inventoryCurrent,
    `${powderLabel(powder)} current stock: ${formatNumber(current, 4)} g`,
    current < 10 ? "warning" : "good",
  );
}

function renderPowderDatabase() {
  const rows = Object.entries(state.powders).sort(([a], [b]) => a.localeCompare(b));
  els.powderDatabaseTableBody.innerHTML = "";
  for (const [powder, record] of rows) {
    const tr = document.createElement("tr");
    const elements = Object.entries(record.elements || {})
      .map(([element, amount]) => `${element}:${formatNumber(amount, 3)}`)
      .join(", ");
    const available = state.inventory[powder] ?? record.available_g;
    tr.innerHTML = `
      <td>${escapeHtml(powderLabel(powder))}</td>
      <td>${escapeHtml(record.formula || powderFormula(powder))}</td>
      <td>${escapeHtml(record.purity || "")}</td>
      <td>${escapeHtml(record.company || "")}</td>
      <td>${formatNumber(record.molar_mass_g_mol, 5)}</td>
      <td class="wrap">${escapeHtml(elements)}</td>
      <td>${available === undefined || available === null ? "" : formatNumber(available, 3)}</td>
    `;
    els.powderDatabaseTableBody.appendChild(tr);
  }
}

function renderInventoryTables() {
  const recipe = state.lastRecipe?.result?.recipe || {};
  const rows = Object.entries(state.inventory)
    .sort(([a, av], [b, bv]) => {
      const lowA = Number(av) < 10 ? 0 : 1;
      const lowB = Number(bv) < 10 ? 0 : 1;
      return lowA - lowB || a.localeCompare(b);
    });
  const low = rows.filter(([, grams]) => Number(grams) < 10).map(([powder]) => powderLabel(powder));
  els.lowStockDashboard.textContent = low.length ? `Low inventory below 10 g: ${low.join(", ")}` : "No powder below 10 g.";
  els.lowStockDashboard.className = `message ${low.length ? "warning" : "good"}`;

  els.inventoryTableBody.innerHTML = "";
  if (!rows.length) {
    els.inventoryTableBody.innerHTML = `<tr><td colspan="4" class="empty-table">No inventory rows yet. Add stock from the form above.</td></tr>`;
  }
  for (const [powder, grams] of rows) {
    const need = recipe[powder];
    const after = need === undefined ? null : Number(grams) - Number(need);
    const tr = document.createElement("tr");
    tr.className = after !== null && after < 0 ? "short" : Number(grams) < 10 || (after !== null && after < 10) ? "low" : "";
    tr.innerHTML = `
      <td>${escapeHtml(powderLabel(powder))}</td>
      <td>${formatNumber(grams, 3)}</td>
      <td>${need === undefined ? "" : formatNumber(need, 6)}</td>
      <td>${after === null ? "" : formatNumber(after, 3)}</td>
    `;
    els.inventoryTableBody.appendChild(tr);
  }

  els.ledgerTableBody.innerHTML = "";
  const ledgerRows = [...state.inventoryLog].reverse().slice(0, 200);
  if (!ledgerRows.length) {
    els.ledgerTableBody.innerHTML = `<tr><td colspan="7" class="empty-table">No inventory changes logged yet.</td></tr>`;
  }
  for (const entry of ledgerRows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${niceTime(entry.time)}</td>
      <td>${escapeHtml(powderLabel(entry.powder))}</td>
      <td>${formatNumber(entry.change_g, 6)}</td>
      <td>${formatNumber(entry.before_g, 6)}</td>
      <td>${formatNumber(entry.after_g, 6)}</td>
      <td>${escapeHtml(entry.action)}</td>
      <td class="wrap">${escapeHtml(entry.reason || entry.notes || "")}</td>
    `;
    els.ledgerTableBody.appendChild(tr);
  }
}

function renderMsdsInventory() {
  if (!els.msdsTableBody) return;
  renderMsdsClosetControls();
  const rows = filteredMsdsItems();
  els.msdsTableBody.innerHTML = "";
  if (!rows.length) {
    els.msdsTableBody.innerHTML = `<tr><td colspan="7" class="empty-table">No material records match this view.</td></tr>`;
    return;
  }

  for (const item of rows) {
    const status = msdsStatus(item);
    const tr = document.createElement("tr");
    tr.className = status === "PDF uploaded" ? "" : "low";
    tr.innerHTML = `
      <td>${item.casNumber ? escapeHtml(item.casNumber) : `<span class="needs-verification">needs verification</span>`}</td>
      <td>${item.nameOrFormula ? escapeHtml(item.nameOrFormula) : `<span class="needs-verification">needs verification</span>`}</td>
      <td>${escapeHtml(item.purity || "")}</td>
      <td>${escapeHtml(item.company || "")}</td>
      <td>${escapeHtml(closetLabel(item.closetNumber))}</td>
      <td>${statusPill(status)}${item.msdsExternalUrl ? ` <a href="${escapeHtml(item.msdsExternalUrl)}" target="_blank" rel="noopener">link</a>` : ""}</td>
      <td class="row-actions">
        ${item.msdsFileUrl ? `<a class="icon-link" title="Open uploaded MSDS" href="${escapeHtml(item.msdsFileUrl)}" target="_blank" rel="noopener">&#128196;</a>` : ""}
        <button class="icon" title="Edit material" data-edit-msds="${escapeHtml(item.id)}">&#9998;</button>
        <button class="icon" title="Upload MSDS PDF" data-upload-msds="${escapeHtml(item.id)}">&#11014;</button>
        <button class="icon" title="Delete material" data-delete-msds="${escapeHtml(item.id)}">&#128465;</button>
      </td>
    `;
    els.msdsTableBody.appendChild(tr);
  }

  els.msdsTableBody.querySelectorAll("[data-edit-msds]").forEach((button) => {
    button.addEventListener("click", () => editMsdsItem(button.dataset.editMsds));
  });
  els.msdsTableBody.querySelectorAll("[data-upload-msds]").forEach((button) => {
    button.addEventListener("click", () => {
      editMsdsItem(button.dataset.uploadMsds);
      els.msdsPdfFile.focus();
    });
  });
  els.msdsTableBody.querySelectorAll("[data-delete-msds]").forEach((button) => {
    button.addEventListener("click", () => deleteMsdsItem(button.dataset.deleteMsds));
  });
}

function renderMsdsClosetControls() {
  if (!els.msdsClosetNumber || !els.msdsClosetFilter) return;
  const previousFormCloset = els.msdsClosetNumber.value || "1";
  const previousFilter = els.msdsClosetFilter.value;
  els.msdsClosetNumber.innerHTML = closetOptionsHtml(false);
  els.msdsClosetFilter.innerHTML = closetOptionsHtml(true);
  els.msdsClosetNumber.value = ["1", "2", "3", "4"].includes(previousFormCloset) ? previousFormCloset : "1";
  els.msdsClosetFilter.value = ["", "1", "2", "3", "4"].includes(previousFilter) ? previousFilter : "";
}

function filteredMsdsItems() {
  const search = els.msdsSearch.value.trim().toLowerCase();
  const closet = els.msdsClosetFilter.value;
  return [...state.msdsInventory]
    .filter((item) => {
      if (closet && String(item.closetNumber) !== closet) return false;
      if (!search) return true;
      return [
        item.casNumber,
        item.nameOrFormula,
        item.purity,
        closetLabel(item.closetNumber),
        item.msdsStatus,
        item.msdsExternalUrl,
        item.company,
      ].join(" ").toLowerCase().includes(search);
    })
    .sort((a, b) => (
      Number(a.closetNumber) - Number(b.closetNumber) ||
      String(a.nameOrFormula || "").localeCompare(String(b.nameOrFormula || "")) ||
      String(a.casNumber || "").localeCompare(String(b.casNumber || ""))
    ));
}

function resetMsdsForm() {
  els.msdsItemId.value = "";
  els.msdsCasNumber.value = "";
  els.msdsNameFormula.value = "";
  els.msdsPurity.value = "";
  els.msdsCompany.value = "";
  els.msdsClosetNumber.value = "1";
  els.msdsExternalUrl.value = "";
  els.msdsPdfFile.value = "";
  els.msdsLookupStatus.textContent = "";
  setMessage(els.msdsFormMode, "New material.");
  els.saveMsdsMaterial.textContent = "Save Material";
}

function editMsdsItem(itemId) {
  const item = state.msdsInventory.find((record) => record.id === itemId);
  if (!item) return;
  els.msdsItemId.value = item.id;
  els.msdsCasNumber.value = item.casNumber || "";
  els.msdsNameFormula.value = item.nameOrFormula || "";
  els.msdsPurity.value = item.purity || "";
  els.msdsCompany.value = item.company || "";
  els.msdsClosetNumber.value = String(item.closetNumber || 1);
  els.msdsExternalUrl.value = item.msdsExternalUrl || "";
  els.msdsPdfFile.value = "";
  els.msdsLookupStatus.textContent = "";
  setMessage(els.msdsFormMode, `Editing ${item.nameOrFormula || item.casNumber || "material"}.`, "good");
  els.saveMsdsMaterial.textContent = "Save Changes";
  els.msdsCasNumber.focus();
}

function msdsPayload() {
  return {
    casNumber: els.msdsCasNumber.value.trim(),
    nameOrFormula: els.msdsNameFormula.value.trim(),
    purity: els.msdsPurity.value.trim(),
    company: els.msdsCompany.value.trim(),
    closetNumber: Number(els.msdsClosetNumber.value || 1),
    msdsExternalUrl: els.msdsExternalUrl.value.trim(),
    identityStatus: "needs verification",
  };
}

async function saveMsdsMaterial(event, { keepForm = true } = {}) {
  if (event) event.preventDefault();
  const itemId = els.msdsItemId.value.trim();
  const done = setBusy(els.saveMsdsMaterial, itemId ? "Saving..." : "Adding...");
  try {
    const data = await api.send(
      itemId ? `/api/msds-inventory/${encodeURIComponent(itemId)}` : "/api/msds-inventory",
      itemId ? "PATCH" : "POST",
      msdsPayload(),
    );
    state.msdsInventory = data.items || state.msdsInventory;
    let savedItem = data.item;
    if (els.msdsPdfFile.files.length) {
      savedItem = await uploadMsdsPdf(savedItem.id);
    }
    renderEverything();
    if (keepForm) editMsdsItem(savedItem.id);
    else resetMsdsForm();
    flash("Material inventory saved.");
    return savedItem;
  } catch (error) {
    flash(error.message, "error");
    return null;
  } finally {
    done();
  }
}

async function uploadMsdsPdf(itemId = els.msdsItemId.value.trim()) {
  if (!els.msdsPdfFile.files.length) {
    flash("Choose an MSDS/SDS PDF first.", "warning");
    return null;
  }
  if (!itemId) {
    const saved = await saveMsdsMaterial(null);
    return saved;
  }
  const formData = new FormData();
  formData.append("file", els.msdsPdfFile.files[0]);
  const data = await api.upload(`/api/msds-inventory/${encodeURIComponent(itemId)}/msds-file`, formData);
  state.msdsInventory = data.items || state.msdsInventory;
  els.msdsPdfFile.value = "";
  renderEverything();
  flash("MSDS PDF uploaded.");
  return data.item;
}

async function deleteMsdsItem(itemId) {
  const item = state.msdsInventory.find((record) => record.id === itemId);
  const label = item?.nameOrFormula || item?.casNumber || "material";
  const accepted = await confirmDanger(
    `Delete ${label}?`,
    "This removes the material from the Inventory & MSDS tab. Powder recipes and powder inventory stay unchanged.",
    "Delete Material",
  );
  if (!accepted) return;
  try {
    const data = await api.send(`/api/msds-inventory/${encodeURIComponent(itemId)}`, "DELETE");
    state.msdsInventory = data.items || state.msdsInventory;
    if (els.msdsItemId.value === itemId) resetMsdsForm();
    renderEverything();
    flash("Material deleted.");
  } catch (error) {
    flash(error.message, "error");
  }
}

async function lookupMsdsIdentity(source) {
  const cas = els.msdsCasNumber.value.trim();
  const name = els.msdsNameFormula.value.trim();
  if (!cas && !name) {
    els.msdsLookupStatus.textContent = "";
    return;
  }
  try {
    const params = new URLSearchParams({ cas_number: cas, name_or_formula: name });
    const data = await api.get(`/api/msds-inventory/lookup?${params.toString()}`);
    const match = data.match;
    if (!match) {
      els.msdsLookupStatus.textContent = "No verified match in the lab database yet.";
      return;
    }
    if (source === "cas" && !els.msdsNameFormula.value.trim()) {
      els.msdsNameFormula.value = match.nameOrFormula || "";
    }
    if (source === "name" && !els.msdsCasNumber.value.trim()) {
      els.msdsCasNumber.value = match.casNumber || "";
    }
    if (!els.msdsPurity.value.trim()) els.msdsPurity.value = match.purity || "";
    if (!els.msdsCompany.value.trim()) els.msdsCompany.value = match.company || "";
    if (!els.msdsExternalUrl.value.trim()) els.msdsExternalUrl.value = match.msdsExternalUrl || "";
    els.msdsLookupStatus.textContent = `Matched existing record: ${match.nameOrFormula || match.casNumber}.`;
  } catch (error) {
    els.msdsLookupStatus.textContent = error.message;
  }
}

function renderDataHealth() {
  if (!els.dataHealthGrid) return;
  const powderNames = Object.keys(state.powders);
  const inventoryNames = Object.keys(state.inventory);
  const lowStock = inventoryNames
    .filter((powder) => Number(state.inventory[powder]) < 10)
    .sort((a, b) => Number(state.inventory[a]) - Number(state.inventory[b]));
  const missingStock = powderNames.filter((powder) => state.inventory[powder] === undefined).sort();
  const unknownStock = inventoryNames.filter((powder) => !state.powders[powder]).sort();
  const densityNeedsReview = Object.values(state.densities)
    .filter((record) => {
      const status = densityStatus(record);
      return !status.includes("checked") && !status.includes("preferred") && !status.includes("do not use");
    });
  const groups = targetLifecycleGroups();
  const needsDensity = groups.filter((group) => (
    group.entries.some((entry) => (entry.entry_type || "synthesis") === "synthesis") &&
    !group.entries.some((entry) => entry.entry_type === "target_density")
  ));
  const needsRecipe = groups.filter((group) => (
    group.entries.some((entry) => entry.entry_type === "target_density") &&
    !group.entries.some((entry) => (entry.entry_type || "synthesis") === "synthesis")
  ));
  const missingMsdsPdf = state.msdsInventory
    .filter((item) => msdsStatus(item) !== "PDF uploaded")
    .sort((a, b) => closetLabel(a.closetNumber).localeCompare(closetLabel(b.closetNumber))
      || String(a.nameOrFormula || a.casNumber || "").localeCompare(String(b.nameOrFormula || b.casNumber || "")));
  const missingIdentity = state.msdsInventory.filter((item) => !item.casNumber || !item.nameOrFormula);

  const card = (title, value, note, kind = "") => `
    <div class="health-card ${kind}">
      <strong>${escapeHtml(value)}</strong>
      <span>${escapeHtml(title)}</span>
      <small>${escapeHtml(note)}</small>
    </div>
  `;
  els.dataHealthGrid.innerHTML = [
    card("Materials without MSDS PDF", missingMsdsPdf.length, `${Math.max(0, state.msdsInventory.length - missingMsdsPdf.length)} / ${state.msdsInventory.length} complete`, missingMsdsPdf.length ? "warning" : "good"),
    card("Low stock below 10 g", lowStock.length, lowStock.slice(0, 6).join(", ") || "All stocked powders are above threshold.", lowStock.length ? "warning" : "good"),
    card("Powders with no stock row", missingStock.length, missingStock.slice(0, 6).join(", ") || "Every powder has an inventory row.", missingStock.length ? "warning" : "good"),
    card("Unknown inventory rows", unknownStock.length, unknownStock.slice(0, 6).join(", ") || "Inventory matches the powder database.", unknownStock.length ? "warning" : "good"),
    card("Density records needing review", densityNeedsReview.length, densityNeedsReview.slice(0, 5).map((r) => r.formula).join(", ") || "All density rows are reviewed or intentionally blocked.", densityNeedsReview.length ? "warning" : "good"),
    card("Materials needing identity check", missingIdentity.length, missingIdentity.slice(0, 5).map((item) => item.nameOrFormula || item.casNumber || "unnamed").join(", ") || "CAS and name/formula are filled where known.", missingIdentity.length ? "warning" : "good"),
    card("Saved targets needing density", needsDensity.length, needsDensity.slice(0, 5).map((g) => g.targetId).join(", ") || "Saved recipes are linked to density results.", needsDensity.length ? "warning" : "good"),
    card("Density rows needing recipe link", needsRecipe.length, needsRecipe.slice(0, 5).map((g) => g.targetId).join(", ") || "Density records have matching recipes.", needsRecipe.length ? "warning" : "good"),
  ].join("");

  if (els.msdsPdfHealthList) {
    if (!missingMsdsPdf.length) {
      els.msdsPdfHealthList.innerHTML = `<div class="message good">0 materials without MSDS PDF.</div>`;
    } else {
      els.msdsPdfHealthList.innerHTML = `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>CAS</th>
                <th>Name / Formula</th>
                <th>Purity</th>
                <th>Vendor</th>
                <th>Closet</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              ${missingMsdsPdf.map((item) => `
                <tr class="low">
                  <td>${escapeHtml(item.casNumber || "")}</td>
                  <td>${escapeHtml(item.nameOrFormula || "")}</td>
                  <td>${escapeHtml(item.purity || "")}</td>
                  <td>${escapeHtml(item.company || "")}</td>
                  <td>${escapeHtml(closetLabel(item.closetNumber))}</td>
                  <td>${item.msdsExternalUrl ? `<a href="${escapeHtml(item.msdsExternalUrl)}" target="_blank" rel="noopener">source</a>` : ""}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      `;
    }
  }
}

async function addPowder(event) {
  event.preventDefault();
  const done = setBusy(event.submitter, "Adding...");
  try {
    const data = await api.send("/api/powders", "POST", {
      formula: els.newPowderFormula.value,
      purity: els.newPowderPurity.value,
      company: els.newPowderCompany.value,
      initial_grams: Number(els.newPowderGrams.value),
    });
    state.powders = data.powders || state.powders;
    state.inventory = data.inventory || state.inventory;
    state.msdsInventory = data.msds_inventory || state.msdsInventory;
    renderEverything();
    await loadPowderOptions();
    flash(`Added ${powderLabel(data.powder)}.`);
  } catch (error) {
    flash(error.message, "error");
  } finally {
    done();
  }
}

async function adjustInventory(direction, button) {
  const powder = els.inventoryPowder.value;
  if (!powder) {
    flash("Choose a powder.", "warning");
    return;
  }
  const amount = Number(els.inventoryGrams.value);
  if (!(amount > 0)) {
    flash("Enter grams greater than 0.", "warning");
    return;
  }

  const current = Number(state.inventory[powder] || 0);
  if (direction === "remove" && amount >= current && current > 0) {
    const accepted = await confirmDanger(
      `Remove all ${powder} stock?`,
      `This will clamp ${powderLabel(powder)} inventory from ${formatNumber(current, 4)} g to 0 g.`,
      "Remove Stock",
    );
    if (!accepted) return;
  }
  const next = direction === "add"
    ? current + amount
    : Math.max(0, current - amount);
  const verb = direction === "add" ? "Added" : "Removed";
  const done = setBusy(button, direction === "add" ? "Adding..." : "Removing...");
  try {
    const data = await api.send(`/api/inventory/${encodeURIComponent(powder)}`, "PATCH", {
      grams: next,
      reason: `${verb} ${formatNumber(amount, 4)} g from Vercel lab website`,
    });
    state.inventory = data.inventory || state.inventory;
    state.inventoryLog = data.inventory_log || state.inventoryLog;
    renderEverything();
    flash(`${verb} ${formatNumber(amount, 4)} g for ${powderLabel(powder)}. New stock: ${formatNumber(next, 4)} g.`);
  } catch (error) {
    flash(error.message, "error");
  } finally {
    done();
  }
}

async function removePowder(event) {
  event.preventDefault();
  const powder = els.deletePowder.value;
  if (!powder) {
    flash("Choose a powder.", "warning");
    return;
  }
  const accepted = await confirmDanger(
    `Delete ${powderLabel(powder)}?`,
    els.removeDeletedStock.checked
      ? "This removes the powder from the database and removes its inventory row. History records stay unchanged."
      : "This removes the powder from the database but keeps the inventory row.",
    "Delete Powder",
  );
  if (!accepted) return;
  const done = setBusy(event.submitter, "Deleting...");
  try {
    const params = new URLSearchParams({ remove_inventory: String(els.removeDeletedStock.checked) });
    const data = await api.send(`/api/powders/${encodeURIComponent(powder)}?${params.toString()}`, "DELETE");
    state.powders = data.powders || state.powders;
    state.inventory = data.inventory || state.inventory;
    renderEverything();
    await loadPowderOptions();
    flash(`Deleted ${powderLabel(powder)}.`);
  } catch (error) {
    flash(error.message, "error");
  } finally {
    done();
  }
}

function toggleDensityEntryMode() {
  const mode = els.densityEntryMode.value;
  els.latticeFields.hidden = mode !== "From lattice parameters";
  els.unitCellFields.hidden = mode !== "From unit cell volume";
  els.manualDensityFields.hidden = mode !== "Manual theoretical density";
  els.zField.hidden = mode === "Manual theoretical density";
  syncLatticeFields();
  previewMaterialDensity().catch(() => {});
}

function latticeRules(system) {
  const key = String(system || "").toLowerCase();
  const rules = {
    cubic: {
      show: ["a"],
      hint: "b = c = a; α = β = γ = 90°",
      resolve: ({ a }) => ({ a, b: a, c: a, alpha: 90, beta: 90, gamma: 90 }),
    },
    tetragonal: {
      show: ["a", "c"],
      hint: "b = a; α = β = γ = 90°",
      resolve: ({ a, c }) => ({ a, b: a, c, alpha: 90, beta: 90, gamma: 90 }),
    },
    orthorhombic: {
      show: ["a", "b", "c"],
      hint: "α = β = γ = 90°",
      resolve: ({ a, b, c }) => ({ a, b, c, alpha: 90, beta: 90, gamma: 90 }),
    },
    hexagonal: {
      show: ["a", "c"],
      hint: "b = a; α = β = 90°; γ = 120°",
      resolve: ({ a, c }) => ({ a, b: a, c, alpha: 90, beta: 90, gamma: 120 }),
    },
    rhombohedral: {
      show: ["a", "alpha"],
      hint: "b = c = a; β = γ = α",
      resolve: ({ a, alpha }) => ({ a, b: a, c: a, alpha, beta: alpha, gamma: alpha }),
    },
    monoclinic: {
      show: ["a", "b", "c", "beta"],
      hint: "α = γ = 90°",
      resolve: ({ a, b, c, beta }) => ({ a, b, c, alpha: 90, beta, gamma: 90 }),
    },
    triclinic: {
      show: ["a", "b", "c", "alpha", "beta", "gamma"],
      hint: "a, b, c; α, β, γ",
      resolve: ({ a, b, c, alpha, beta, gamma }) => ({ a, b, c, alpha, beta, gamma }),
    },
  };
  return rules[key] || rules.triclinic;
}

function syncLatticeFields() {
  if (els.densityEntryMode.value !== "From lattice parameters") return;
  const rules = latticeRules(els.crystalSystem.value);
  const shown = new Set(rules.show);
  const fieldMap = {
    a: els.latticeAWrap,
    b: els.latticeBWrap,
    c: els.latticeCWrap,
    alpha: els.latticeAlphaWrap,
    beta: els.latticeBetaWrap,
    gamma: els.latticeGammaWrap,
  };
  Object.entries(fieldMap).forEach(([name, wrap]) => {
    wrap.hidden = !shown.has(name);
  });
  els.latticeSystemHint.innerHTML = `
    <span>Symmetry constraint</span>
    <strong>${escapeHtml(rules.hint)}</strong>
  `;
}

function latticeInputValues() {
  return {
    a: numberOrNull(els.latticeA.value),
    b: numberOrNull(els.latticeB.value),
    c: numberOrNull(els.latticeC.value),
    alpha: numberOrNull(els.latticeAlpha.value),
    beta: numberOrNull(els.latticeBeta.value),
    gamma: numberOrNull(els.latticeGamma.value),
  };
}

function resolvedLatticeValues() {
  return latticeRules(els.crystalSystem.value).resolve(latticeInputValues());
}

function densityCellPayload(mode = els.densityEntryMode.value) {
  const lattice = mode === "From lattice parameters"
    ? resolvedLatticeValues()
    : { a: null, b: null, c: null, alpha: null, beta: null, gamma: null };
  return {
    formula: els.materialFormula.value.trim(),
    crystal_system: els.crystalSystem.value,
    a_A: lattice.a,
    b_A: lattice.b,
    c_A: lattice.c,
    alpha_deg: lattice.alpha,
    beta_deg: lattice.beta,
    gamma_deg: lattice.gamma,
    unit_cell_volume_A3: mode === "From unit cell volume" ? numberOrNull(els.unitCellVolume.value) : null,
    z: Number(els.zValue.value || 1),
  };
}

function numberOrNull(value) {
  const number = Number(value);
  return Number.isFinite(number) && value !== "" ? number : null;
}

async function previewMaterialDensity() {
  const mode = els.densityEntryMode.value;
  if (!els.materialFormula.value.trim()) {
    els.materialDensityPreview.textContent = "";
    return;
  }
  if (mode === "Manual theoretical density") {
    els.materialDensityPreview.textContent = `ρ = ${formatNumber(els.manualMaterialDensity.value, 5)} g/cm³`;
    return;
  }
  try {
    const payload = densityCellPayload(mode);
    if (mode === "From lattice parameters") payload.unit_cell_volume_A3 = null;
    const data = await api.send("/api/density-from-cell", "POST", payload);
    els.materialDensityPreview.textContent = `V = ${formatNumber(data.unit_cell_volume_A3, 5)} Å³; ρ = ${formatNumber(data.theoretical_density_g_cm3, 5)} g/cm³`;
  } catch (error) {
    els.materialDensityPreview.textContent = error.message;
  }
}

async function saveMaterialDensity(event) {
  event.preventDefault();
  const done = setBusy(event.submitter, "Saving...");
  try {
    const mode = els.densityEntryMode.value;
    const verified = els.densityVerifiedCheck.checked;
    const payload = {
      ...densityCellPayload(mode),
      phase: els.materialPhase.value,
      theoretical_density_g_cm3: mode === "Manual theoretical density" ? Number(els.manualMaterialDensity.value) : null,
      density_source: mode === "Manual theoretical density" ? "manual" : mode === "From unit cell volume" ? "unit cell" : "lattice parameters",
      source: els.densitySourceUrl.value || "Lab density entry",
      source_url: els.densitySourceUrl.value,
      doi: "",
      cod_id: "",
      paper_title: "",
      notes: els.densityRecordNotes.value,
      verification_status: verified ? "Lab checked" : "Lab entry - unverified",
      verified_by: els.densityVerifiedBy.value,
      verified_date: verified ? new Date().toISOString().slice(0, 10) : "",
    };
    if (mode === "From lattice parameters") payload.unit_cell_volume_A3 = null;
    const data = await api.send("/api/densities", "POST", payload);
    state.densities = data.records || state.densities;
    renderEverything();
    flash(`Saved density ${data.record_id}.`);
  } catch (error) {
    flash(error.message, "error");
  } finally {
    done();
  }
}

function densitySourceHtml(record) {
  if (record.source_url) {
    return `<a href="${escapeHtml(record.source_url)}" target="_blank" rel="noopener">${escapeHtml(record.source_url)}</a>`;
  }
  return escapeHtml(record.doi || record.source || record.paper_title || "");
}

function filteredDensityRecords() {
  const search = els.densitySearch.value.trim().toLowerCase();
  const scope = els.densityReviewScope.value;
  return Object.values(state.densities)
    .filter((record) => {
      const text = JSON.stringify(record).toLowerCase();
      if (search && !text.includes(search)) return false;
      if (scope === "Needs review") return densityNeedsReview(record);
      if (scope === "Verified/preferred") return isTrustedDensity(record);
      return true;
    })
    .sort((a, b) => (
      Number(densityNeedsReview(b)) - Number(densityNeedsReview(a)) ||
      String(a.formula).localeCompare(String(b.formula)) ||
      String(a.phase).localeCompare(String(b.phase))
    ));
}

function renderDensityReviewPanel(rows) {
  const reviewCandidates = rows.filter(densityNeedsReview);
  const choices = reviewCandidates.length ? reviewCandidates : rows;
  const previous = state.selectedDensityReviewKey || els.densityReviewRecord.value;
  const selectedRecord = choices.find((record) => densityRecordId(record) === previous) || choices[0] || null;
  const selectedKey = selectedRecord ? densityRecordId(selectedRecord) : "";
  state.selectedDensityReviewKey = selectedKey;

  els.densityReviewRecord.innerHTML = "";
  if (!choices.length) {
    els.densityReviewRecord.insertAdjacentHTML("beforeend", `<option value="">No density records to review</option>`);
    els.densityReviewDetails.innerHTML = "No matching density records.";
  } else {
    for (const record of choices.slice(0, 300)) {
      const reviewLabel = densityNeedsReview(record) ? "Needs review" : displayDensityStatus(record);
      els.densityReviewRecord.insertAdjacentHTML(
        "beforeend",
        `<option value="${escapeHtml(densityRecordId(record))}">${escapeHtml(record.display_name || record.formula)} - ${escapeHtml(reviewLabel)}</option>`,
      );
    }
    els.densityReviewRecord.value = selectedKey;
  }

  [els.densityMarkChecked, els.densityMakePreferred, els.densityDoNotUse].forEach((button) => {
    button.disabled = !selectedRecord;
  });

  if (!selectedRecord) return;

  const source = densitySourceHtml(selectedRecord) || "No source recorded.";
  els.densityReviewDetails.innerHTML = `
    <div><strong>${escapeHtml(selectedRecord.display_name || selectedRecord.formula)}</strong></div>
    <div>Formula: ${escapeHtml(selectedRecord.formula)}${selectedRecord.phase ? ` | Phase: ${escapeHtml(selectedRecord.phase)}` : ""}</div>
    <div>Density: ${formatNumber(selectedRecord.theoretical_density_g_cm3, 5)} g/cm³ | V: ${formatNumber(selectedRecord.unit_cell_volume_A3, 5)} Å³ | Z: ${formatNumber(selectedRecord.z, 4)}</div>
    <div>Status: ${escapeHtml(displayDensityStatus(selectedRecord) || "Unreviewed")}</div>
    <div>Source: ${source}</div>
    ${selectedRecord.doi ? `<div>DOI: ${escapeHtml(selectedRecord.doi)}</div>` : ""}
    ${selectedRecord.notes ? `<div>Notes: ${escapeHtml(selectedRecord.notes)}</div>` : ""}
  `;
}

function renderMaterialDensityTable() {
  const rows = filteredDensityRecords();
  renderDensityReviewPanel(rows);

  els.materialDensityTableBody.innerHTML = "";
  if (!rows.length) {
    els.materialDensityTableBody.innerHTML = `<tr><td colspan="8" class="empty-table">No density records match this search.</td></tr>`;
    return;
  }
  for (const record of rows.slice(0, 600)) {
    const tr = document.createElement("tr");
    const status = String(record.verification_status || "").toLowerCase();
    tr.className = [
      String(record.origin || "").toLowerCase().startsWith("codex") ? "codex" : "",
      status.includes("do not use") ? "blocked" : "",
      status.includes("preferred") ? "preferred" : "",
    ].join(" ").trim();
    const sourceLink = densitySourceHtml(record);
    const recordKey = escapeHtml(densityRecordId(record));
    tr.innerHTML = `
      <td>${escapeHtml(record.formula)}</td>
      <td>${escapeHtml(record.phase || "")}</td>
      <td>${formatNumber(record.theoretical_density_g_cm3, 5)}</td>
      <td>${formatNumber(record.unit_cell_volume_A3, 5)}</td>
      <td>${formatNumber(record.z, 4)}</td>
      <td class="wrap">${escapeHtml(displayDensityStatus(record))}</td>
      <td class="wrap">${sourceLink}</td>
      <td class="row-actions">
        <button class="icon" title="Select for review" data-review-density="${recordKey}">&#128269;</button>
        <button class="icon" title="Mark as checked" data-check-density="${recordKey}">&#10003;</button>
        <button class="icon" title="Mark as preferred for this formula" data-prefer-density="${recordKey}">&#9733;</button>
        <button class="icon" title="Do not use this density" data-block-density="${recordKey}">&#10005;</button>
        <button class="icon" title="Delete density record" data-delete-density="${recordKey}">&#128465;</button>
      </td>
    `;
    els.materialDensityTableBody.appendChild(tr);
  }
  els.materialDensityTableBody.querySelectorAll("[data-review-density]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedDensityReviewKey = button.dataset.reviewDensity;
      renderMaterialDensityTable();
      els.densityReviewRecord.focus();
    });
  });
  els.materialDensityTableBody.querySelectorAll("[data-check-density]").forEach((button) => {
    button.addEventListener("click", () => updateDensityReviewStatus(button.dataset.checkDensity, "Lab checked", button));
  });
  els.materialDensityTableBody.querySelectorAll("[data-prefer-density]").forEach((button) => {
    button.addEventListener("click", () => updateDensityReviewStatus(button.dataset.preferDensity, "Preferred for formula", button));
  });
  els.materialDensityTableBody.querySelectorAll("[data-block-density]").forEach((button) => {
    button.addEventListener("click", () => updateDensityReviewStatus(button.dataset.blockDensity, "Do not use", button));
  });
  els.materialDensityTableBody.querySelectorAll("[data-delete-density]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        const accepted = await confirmDanger(
          "Delete density record?",
          "This removes the selected theoretical density source from the lab database.",
          "Delete Density",
        );
        if (!accepted) return;
        const data = await api.send(`/api/densities/${encodeURIComponent(button.dataset.deleteDensity)}`, "DELETE");
        state.densities = data.records || state.densities;
        renderEverything();
        flash("Density record deleted.");
      } catch (error) {
        flash(error.message, "error");
      }
    });
  });
}

async function markPreferredDensity(identifier) {
  return updateDensityReviewStatus(identifier, "Preferred for formula");
}

async function updateDensityReviewStatus(identifier, verificationStatus, button = null) {
  if (!identifier) return;
  const status = String(verificationStatus || "").trim();
  if (!status) return;
  if (status === "Do not use") {
    const accepted = await confirmDanger(
      "Mark density as Do Not Use?",
      "This keeps the record in the database but blocks it from trusted use until someone reviews it again.",
      "Do Not Use",
    );
    if (!accepted) return;
  }
  const reviewer = els.densityReviewBy.value.trim() || els.densityVerifiedBy.value.trim() || "Lab";
  const reviewDate = els.densityReviewDate.value || new Date().toISOString().slice(0, 10);
  const done = button ? setBusy(button, "Saving...") : () => {};
  try {
    const data = await api.send(`/api/densities/${encodeURIComponent(identifier)}/status`, "PATCH", {
      verification_status: status,
      verified_by: reviewer,
      verified_date: reviewDate,
    });
    state.densities = data.records || state.densities;
    state.selectedDensityReviewKey = "";
    renderEverything();
    flash(`Density marked ${status}.`);
  } catch (error) {
    flash(error.message, "error");
  } finally {
    done();
  }
}

function targetLifecycleGroups() {
  const map = new Map();
  for (const entry of state.history) {
    const owner = normalizeOwner(entry.target_for) || "Unassigned";
    const targetId = entry.target_id || `${owner}-${entry.target || "Target"}`;
    const key = `${owner}||${targetId}||${entry.target || ""}`;
    if (!map.has(key)) {
      map.set(key, { owner, targetId, target: entry.target || "", entries: [] });
    }
    map.get(key).entries.push(entry);
  }
  return Array.from(map.values()).sort((a, b) => a.owner.localeCompare(b.owner) || a.targetId.localeCompare(b.targetId));
}

function renderHistory() {
  const groups = targetLifecycleGroups();
  const owners = ["All", ...new Set(groups.map((group) => group.owner))].sort((a, b) => a === "All" ? -1 : b === "All" ? 1 : a.localeCompare(b));
  const previousOwner = els.historyOwnerFilter.value || "All";
  els.historyOwnerFilter.innerHTML = owners.map((owner) => `<option>${escapeHtml(owner)}</option>`).join("");
  if (owners.includes(previousOwner)) els.historyOwnerFilter.value = previousOwner;

  const search = els.historySearch.value.trim().toLowerCase();
  const ownerFilter = els.historyOwnerFilter.value;
  const statusFilter = els.historyStatusFilter.value;

  els.historyLog.innerHTML = "";
  let renderedGroups = 0;
  for (const group of groups) {
    const recipes = group.entries.filter((entry) => (entry.entry_type || "synthesis") === "synthesis");
    const densities = group.entries.filter((entry) => entry.entry_type === "target_density");
    const status = recipes.length && densities.length ? "Complete" : recipes.length ? "Needs density" : "Needs recipe";
    const text = JSON.stringify(group).toLowerCase();
    if (search && !text.includes(search)) continue;
    if (ownerFilter !== "All" && group.owner !== ownerFilter) continue;
    if (statusFilter !== "All" && status !== statusFilter) continue;

    const node = document.createElement("article");
    node.className = "history-group";
    node.innerHTML = `
      <div class="history-group-head">
        <div>
          <div class="history-group-title">${escapeHtml(group.targetId)} - ${escapeHtml(group.target)}</div>
          <div class="history-meta">${escapeHtml(group.owner)} | ${status} | ${recipes.length} recipe(s), ${densities.length} density record(s)</div>
        </div>
        <button class="icon" title="Clear this target group" data-clear-target="${escapeHtml(group.targetId)}">&#128465;</button>
      </div>
      ${group.entries.slice().reverse().map((entry) => historyItemHtml(entry)).join("")}
    `;
    els.historyLog.appendChild(node);
    renderedGroups += 1;
  }

  if (!renderedGroups) {
    els.historyLog.innerHTML = `<div class="empty-state">No history records match this view yet.</div>`;
  }

  els.historyLog.querySelectorAll("[data-delete-history]").forEach((button) => {
    button.addEventListener("click", () => deleteHistoryItem(button.dataset.deleteHistory));
  });
  els.historyLog.querySelectorAll("[data-clear-target]").forEach((button) => {
    button.addEventListener("click", () => clearTargetGroup(button.dataset.clearTarget));
  });
}

function historyItemHtml(entry) {
  const type = (entry.entry_type || "synthesis") === "target_density" ? "After sintering" : "Before sintering";
  const title = type === "Before sintering"
    ? `${entry.recipe_id || "Recipe"} - ${formatNumber(entry.mass, 6)} g target formula mass`
    : `Density ${formatNumber(entry.relative_density_percent, 2)}%`;
  const meta = type === "Before sintering"
    ? `${niceTime(entry.time)} | powders: ${Object.entries(entry.recipe || {}).map(([p, g]) => `${p} ${formatNumber(g, 6)} g`).join(", ")}`
    : `${niceTime(entry.time)} | measured ${formatNumber(entry.measured_density_g_cm3, 5)} g/cm³, theoretical ${formatNumber(entry.theoretical_density_g_cm3, 5)} g/cm³`;
  return `
    <div class="history-item">
      <div>
        <div class="history-item-title">${escapeHtml(type)} | ${escapeHtml(title)}</div>
        <div class="history-meta">${escapeHtml(meta)}</div>
        ${entry.notes ? `<div class="history-meta">${escapeHtml(entry.notes)}</div>` : ""}
      </div>
      <button class="icon" title="Delete this history item" data-delete-history="${escapeHtml(entry.entry_id)}">&#128465;</button>
    </div>
  `;
}

async function deleteHistoryItem(entryId) {
  try {
    const accepted = await confirmDanger(
      "Delete history item?",
      "This removes one saved recipe or target-density record from the lab log.",
      "Delete Item",
    );
    if (!accepted) return;
    const data = await api.send(`/api/history/${encodeURIComponent(entryId)}`, "DELETE");
    state.history = data.history || state.history;
    state.linkedRecipes = data.linked_recipes || state.linkedRecipes;
    renderEverything();
    flash("History item deleted.");
  } catch (error) {
    flash(error.message, "error");
  }
}

async function clearTargetGroup(targetId) {
  try {
    const accepted = await confirmDanger(
      `Clear ${targetId}?`,
      "This removes every history record in this target group.",
      "Clear Group",
    );
    if (!accepted) return;
    const data = await api.send(`/api/history/groups/target-id/${encodeURIComponent(targetId)}`, "DELETE");
    state.history = data.history || state.history;
    state.linkedRecipes = data.linked_recipes || state.linkedRecipes;
    renderEverything();
    flash(`Removed ${data.removed} history item(s).`);
  } catch (error) {
    flash(error.message, "error");
  }
}

function niceTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).replace(/\.\d+/, "");
  const pad = (number) => String(number).padStart(2, "0");
  return `D-${pad(date.getDate())}.${pad(date.getMonth() + 1)}.${String(date.getFullYear()).slice(-2)} T-${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

let targetPreviewTimer = null;
async function updateTargetPreview(input, output) {
  clearTimeout(targetPreviewTimer);
  targetPreviewTimer = setTimeout(async () => {
    const owner = normalizeOwner(input.value);
    if (!owner) {
      output.textContent = "";
      return;
    }
    try {
      const data = await api.get(`/api/target-id-preview?target_for=${encodeURIComponent(owner)}`);
      output.textContent = `Next saved target for ${owner}: ${data.target_id}.`;
    } catch {
      output.textContent = "";
    }
  }, 220);
}

function toggleAmountMode() {
  const heightMode = selectedAmountMode() === "height";
  $("#massModeFields").hidden = heightMode;
  $("#heightModeFields").hidden = !heightMode;
  els.targetMassLabel.textContent = "Target formula mass (g)";
  previewHeightMass().catch(() => {});
}

function setupNavigation() {
  $$(".nav-item").forEach((button) => {
    button.addEventListener("click", () => {
      $$(".nav-item").forEach((item) => item.classList.remove("active"));
      $$(".page").forEach((page) => page.classList.remove("active"));
      button.classList.add("active");
      $(`#page-${button.dataset.page}`).classList.add("active");
      const [title, subtitle] = pageMeta[button.dataset.page];
      els.pageTitle.textContent = title;
      els.pageSubtitle.textContent = subtitle;
      els.pageSubtitle.hidden = !subtitle;
      if (button.dataset.page === "target-density") {
        state.densityPickerExpanded.relativeDensityChoice = false;
        updateDensityChoicesForTarget(
          syncTargetDensityFormulaFromRecipeTarget(),
          els.relativeDensityChoice,
          els.manualRelativeDensityWrap,
        ).catch(() => {});
      }
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  });
}

function setupTheme() {
  const savedTheme = localStorage.getItem("stoichioTheme") || "dark";
  document.body.classList.toggle("light", savedTheme === "light");
  els.themeToggle.textContent = savedTheme === "light" ? "Dark mode" : "Light mode";
  els.themeToggle.addEventListener("click", () => {
    const light = !document.body.classList.contains("light");
    document.body.classList.toggle("light", light);
    localStorage.setItem("stoichioTheme", light ? "light" : "dark");
    els.themeToggle.textContent = light ? "Dark mode" : "Light mode";
  });
}

function setupQuickMode() {
  const savedQuick = localStorage.getItem("stoichioQuickMode") === "1";
  els.quickMode.checked = savedQuick;
  document.body.classList.toggle("quick", savedQuick);
  els.quickMode.addEventListener("change", () => {
    document.body.classList.toggle("quick", els.quickMode.checked);
    localStorage.setItem("stoichioQuickMode", els.quickMode.checked ? "1" : "0");
    flash(els.quickMode.checked ? "Quick calculation mode on." : "Full lab mode on.");
  });
}

function setupEvents() {
  restoreRecipeSettings();
  els.adminPin.value = localStorage.getItem("stoichioAdminPin") || "";
  els.savePin.addEventListener("click", () => {
    localStorage.setItem("stoichioAdminPin", els.adminPin.value.trim());
    flash("Admin PIN saved in this browser.");
  });
  $$("input[name='amountMode']").forEach((input) => input.addEventListener("change", () => {
    toggleAmountMode();
    persistRecipeSettings();
  }));
  els.targetFormula.addEventListener("input", debounce(async () => {
    state.densityPickerExpanded.heightDensityChoice = false;
    await loadPowderOptions();
    await updateDensityChoicesForTarget(els.targetFormula.value, els.heightDensityChoice, els.manualHeightDensityWrap);
    if (state.densityTargetAutoSynced || !els.densityTargetFormula.value.trim()) {
      state.densityPickerExpanded.relativeDensityChoice = false;
      await updateDensityChoicesForTarget(
        syncTargetDensityFormulaFromRecipeTarget(),
        els.relativeDensityChoice,
        els.manualRelativeDensityWrap,
      );
    }
    previewHeightMass().catch(() => {});
    persistRecipeSettings();
  }, 220));
  els.recipeTargetFor.addEventListener("input", () => {
    updateTargetPreview(els.recipeTargetFor, els.recipeTargetPreview);
    persistRecipeSettings();
  });
  els.densityTargetFor.addEventListener("input", () => updateTargetPreview(els.densityTargetFor, els.densityTargetPreview));
  els.showAllPowders.addEventListener("change", () => {
    persistRecipeSettings();
    loadPowderOptions().catch((error) => flash(error.message, "error"));
  });
  els.reloadPowders.addEventListener("click", () => loadPowderOptions().catch((error) => flash(error.message, "error")));
  [els.targetMass, els.targetHeight, els.targetDiameter, els.targetPorosity, els.heightDensity, els.recipeNotes].forEach((input) => {
    input.addEventListener("input", debounce(persistRecipeSettings, 200));
  });
  [els.targetHeight, els.targetDiameter, els.targetPorosity, els.heightDensity, els.heightDensityChoice].forEach((input) => {
    input.addEventListener("input", () => previewHeightMass().catch(() => {}));
    input.addEventListener("change", async () => {
      if (input === els.heightDensityChoice && input.value === "__show_more__") {
        state.densityPickerExpanded.heightDensityChoice = true;
        await updateDensityChoicesForTarget(els.targetFormula.value, els.heightDensityChoice, els.manualHeightDensityWrap);
      }
      els.manualHeightDensityWrap.hidden = els.heightDensityChoice.value !== "__manual__";
      state.savedDensityChoices.heightDensityChoice = els.heightDensityChoice.value;
      persistRecipeSettings();
      previewHeightMass().catch(() => {});
    });
  });
  els.recipeForm.addEventListener("submit", calculateRecipe);
  els.saveRecipe.addEventListener("click", saveRecipe);
  els.saveAndDeductRecipe.addEventListener("click", saveRecipeAndDeductInventory);
  els.deductInventory.addEventListener("click", deductInventory);
  els.copyRecipeNotebook.addEventListener("click", copyRecipeToNotebook);
  els.printRecipeLabel.addEventListener("click", printRecipeLabel);

  els.linkedRecipe.addEventListener("change", onLinkedRecipeChange);
  els.densityTargetFormula.addEventListener("input", debounce(() => {
    state.densityTargetAutoSynced = !els.densityTargetFormula.value.trim();
    state.densityPickerExpanded.relativeDensityChoice = false;
    updateDensityChoicesForTarget(targetDensityFormulaForChoices(), els.relativeDensityChoice, els.manualRelativeDensityWrap);
  }, 220));
  els.relativeDensityChoice.addEventListener("change", async () => {
    if (els.relativeDensityChoice.value === "__show_more__") {
      state.densityPickerExpanded.relativeDensityChoice = true;
      await updateDensityChoicesForTarget(targetDensityFormulaForChoices(), els.relativeDensityChoice, els.manualRelativeDensityWrap);
    }
    els.manualRelativeDensityWrap.hidden = els.relativeDensityChoice.value !== "__manual__";
    state.savedDensityChoices.relativeDensityChoice = els.relativeDensityChoice.value;
    persistRecipeSettings();
  });
  els.densityForm.addEventListener("submit", calculateDensity);
  els.saveDensityHistory.addEventListener("click", saveDensityHistory);

  els.addPowderForm.addEventListener("submit", addPowder);
  els.inventoryForm.addEventListener("submit", (event) => event.preventDefault());
  els.inventoryPowder.addEventListener("change", renderInventoryAdjustment);
  els.inventoryAdd.addEventListener("click", () => adjustInventory("add", els.inventoryAdd));
  els.inventoryRemove.addEventListener("click", () => adjustInventory("remove", els.inventoryRemove));
  els.deletePowderForm.addEventListener("submit", removePowder);

  els.msdsForm.addEventListener("submit", (event) => saveMsdsMaterial(event));
  els.newMsdsMaterial.addEventListener("click", resetMsdsForm);
  els.uploadMsdsFile.addEventListener("click", async () => {
    const done = setBusy(els.uploadMsdsFile, "Uploading...");
    try {
      await uploadMsdsPdf();
    } catch (error) {
      flash(error.message, "error");
    } finally {
      done();
    }
  });
  els.msdsSearch.addEventListener("input", renderMsdsInventory);
  els.msdsClosetFilter.addEventListener("change", renderMsdsInventory);
  els.msdsCasNumber.addEventListener("input", debounce(() => lookupMsdsIdentity("cas"), 260));
  els.msdsNameFormula.addEventListener("input", debounce(() => lookupMsdsIdentity("name"), 260));

  els.densityEntryMode.addEventListener("change", toggleDensityEntryMode);
  els.crystalSystem.addEventListener("change", () => {
    syncLatticeFields();
    previewMaterialDensity().catch(() => {});
  });
  [
    els.materialFormula, els.latticeA, els.latticeB, els.latticeC,
    els.latticeAlpha, els.latticeBeta, els.latticeGamma, els.unitCellVolume,
    els.zValue, els.manualMaterialDensity,
  ].forEach((input) => input.addEventListener("input", debounce(() => previewMaterialDensity(), 260)));
  els.materialDensityForm.addEventListener("submit", saveMaterialDensity);
  els.densitySearch.addEventListener("input", renderMaterialDensityTable);
  els.densityReviewDate.value = new Date().toISOString().slice(0, 10);
  els.densityReviewScope.addEventListener("change", () => {
    state.selectedDensityReviewKey = "";
    renderMaterialDensityTable();
  });
  els.densityReviewRecord.addEventListener("change", () => {
    state.selectedDensityReviewKey = els.densityReviewRecord.value;
    renderMaterialDensityTable();
  });
  els.densityMarkChecked.addEventListener("click", () => (
    updateDensityReviewStatus(els.densityReviewRecord.value, "Lab checked", els.densityMarkChecked)
  ));
  els.densityMakePreferred.addEventListener("click", () => (
    updateDensityReviewStatus(els.densityReviewRecord.value, "Preferred for formula", els.densityMakePreferred)
  ));
  els.densityDoNotUse.addEventListener("click", () => (
    updateDensityReviewStatus(els.densityReviewRecord.value, "Do not use", els.densityDoNotUse)
  ));
  els.historySearch.addEventListener("input", renderHistory);
  els.historyOwnerFilter.addEventListener("change", renderHistory);
  els.historyStatusFilter.addEventListener("change", renderHistory);
}

function debounce(fn, wait) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

setupNavigation();
setupTheme();
setupQuickMode();
setupEvents();
toggleAmountMode();
toggleDensityEntryMode();
renderMsdsClosetControls();
resetMsdsForm();
renderRecipeEmptyState();
loadAll().catch((error) => {
  els.serviceStatus.textContent = error.message;
  flash(error.message, "error");
});
