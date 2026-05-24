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
};

const state = {
  powders: {},
  inventory: {},
  inventoryLog: [],
  densities: {},
  history: [],
  linkedRecipes: [],
  powderSets: {},
  selectedPowders: new Set(["Fe2O3", "TiO2"]),
  lastRecipe: null,
  lastRecipeMass: null,
  lastDensityResult: null,
};

const pageMeta = {
  "powder-mass": ["Powder Mass Calculation", "Choose the exact powders and calculate deterministic precursor masses."],
  "target-density": ["Target Density", "Measure the sintered target and compare it to a theoretical density."],
  "powders-inventory": ["Powder & Inventory", "Add powders, edit stock, delete mistakes, and review low inventory."],
  "material-density": ["Material Density", "Store theoretical density records, unit cells, sources, and verification status."],
  history: ["History", "Trace recipes and after-sintering density records by person and target number."],
};

const els = {
  serviceStatus: $("#serviceStatus"),
  adminPin: $("#adminPin"),
  savePin: $("#savePin"),
  themeToggle: $("#themeToggle"),
  globalMessage: $("#globalMessage"),
  pageTitle: $("#pageTitle"),
  pageSubtitle: $("#pageSubtitle"),
  powderCount: $("#powderCount"),
  densityCount: $("#densityCount"),
  historyCount: $("#historyCount"),

  targetFormula: $("#targetFormula"),
  recipeTargetFor: $("#recipeTargetFor"),
  recipeTargetPreview: $("#recipeTargetPreview"),
  targetMass: $("#targetMass"),
  targetHeight: $("#targetHeight"),
  targetDiameter: $("#targetDiameter"),
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
  recipeMetrics: $("#recipeMetrics"),
  recipeTableBody: $("#recipeTable tbody"),
  recipeDetails: $("#recipeDetails"),
  recipeNotes: $("#recipeNotes"),
  saveRecipe: $("#saveRecipe"),
  deductInventory: $("#deductInventory"),
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
  lowStockDashboard: $("#lowStockDashboard"),
  inventoryTableBody: $("#inventoryTable tbody"),
  ledgerTableBody: $("#ledgerTable tbody"),

  materialDensityForm: $("#materialDensityForm"),
  materialFormula: $("#materialFormula"),
  materialPhase: $("#materialPhase"),
  densityEntryMode: $("#densityEntryMode"),
  latticeFields: $("#latticeFields"),
  unitCellFields: $("#unitCellFields"),
  manualDensityFields: $("#manualDensityFields"),
  crystalSystem: $("#crystalSystem"),
  latticeA: $("#latticeA"),
  latticeB: $("#latticeB"),
  latticeC: $("#latticeC"),
  latticeAlpha: $("#latticeAlpha"),
  latticeBeta: $("#latticeBeta"),
  latticeGamma: $("#latticeGamma"),
  unitCellVolume: $("#unitCellVolume"),
  zValue: $("#zValue"),
  manualMaterialDensity: $("#manualMaterialDensity"),
  materialDensityPreview: $("#materialDensityPreview"),
  densityTrustStatus: $("#densityTrustStatus"),
  densityVerifiedBy: $("#densityVerifiedBy"),
  densityVerifiedDate: $("#densityVerifiedDate"),
  densitySource: $("#densitySource"),
  densitySourceUrl: $("#densitySourceUrl"),
  densityDoi: $("#densityDoi"),
  densityCod: $("#densityCod"),
  densityPaperTitle: $("#densityPaperTitle"),
  densityRecordNotes: $("#densityRecordNotes"),
  densitySearch: $("#densitySearch"),
  densityReviewScope: $("#densityReviewScope"),
  materialDensityTableBody: $("#materialDensityTable tbody"),

  historySearch: $("#historySearch"),
  historyOwnerFilter: $("#historyOwnerFilter"),
  historyStatusFilter: $("#historyStatusFilter"),
  historyLog: $("#historyLog"),
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

function selectedAmountMode() {
  return $("input[name='amountMode']:checked").value;
}

function densityRecordLabel(record, prefix = "") {
  const phase = record.phase ? `, ${record.phase}` : "";
  const status = record.verification_status ? ` - ${record.verification_status}` : "";
  return `${prefix}${record.display_name || record.formula}${phase}: ${formatNumber(record.theoretical_density_g_cm3, 5)} g/cm3${status}`;
}

function densityChoiceValue(select) {
  const key = select.value;
  if (!key || key === "__manual__") return null;
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
  if (data.filter_error) {
    els.powderFilterHint.textContent = `Formula filter error: ${data.filter_error}. Showing all powders.`;
  } else if (els.showAllPowders.checked) {
    els.powderFilterHint.textContent = `Showing all ${Object.keys(state.powders).length} powders. Relevant filter is off.`;
  } else {
    const elements = (data.target_elements || []).join(", ");
    els.powderFilterHint.textContent = elements
      ? `Showing ${options.length} relevant powder(s) for ${elements}. Hidden: ${(data.hidden || []).length}.`
      : `Showing ${options.length} powder(s).`;
  }

  for (const powder of options) {
    const record = state.powders[powder] || {};
    const row = document.createElement("div");
    row.className = "selector-row";
    row.innerHTML = `
      <label>
        <input type="checkbox" value="${escapeHtml(powder)}">
        <span>${escapeHtml(powder)}</span>
      </label>
      <span class="pill">${formatNumber(record.molar_mass_g_mol, 3)} g/mol</span>
      <span class="pill">${record.available_g === null || record.available_g === undefined ? "no stock" : `${formatNumber(record.available_g, 3)} g`}</span>
    `;
    const checkbox = row.querySelector("input");
    checkbox.checked = state.selectedPowders.has(powder);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) state.selectedPowders.add(powder);
      else state.selectedPowders.delete(powder);
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
        <span>${escapeHtml(record.name || record.record_id)} (${escapeHtml((record.powders || []).join(", "))})</span>
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
      await api.send(`/api/powder-sets/${encodeURIComponent(button.dataset.deleteSet)}`, "DELETE");
      flash("Powder set deleted.");
      await loadAll();
    });
  });
}

async function updateDensityChoicesForTarget(target, select, manualWrap) {
  const data = await api.get(`/api/densities?target=${encodeURIComponent(target || "")}`);
  state.densities = data.records || state.densities;
  const previous = select.value;
  select.innerHTML = `<option value="__manual__">Manual theoretical density</option>`;
  for (const record of data.exact || []) {
    select.insertAdjacentHTML("beforeend", `<option value="${escapeHtml(record.record_key)}">${escapeHtml(densityRecordLabel(record, "Exact - "))}</option>`);
  }
  for (const record of data.related || []) {
    select.insertAdjacentHTML("beforeend", `<option value="${escapeHtml(record.record_key)}">${escapeHtml(densityRecordLabel(record, "Related - "))}</option>`);
  }
  if ([...select.options].some((option) => option.value === previous)) {
    select.value = previous;
  } else if (select.options.length > 1) {
    select.selectedIndex = 1;
  }
  manualWrap.hidden = select.value !== "__manual__";
}

function renderDensityChoices() {
  updateDensityChoicesForTarget(els.targetFormula.value, els.heightDensityChoice, els.manualHeightDensityWrap)
    .then(previewHeightMass)
    .catch(() => {});
  updateDensityChoicesForTarget(els.densityTargetFormula.value, els.relativeDensityChoice, els.manualRelativeDensityWrap)
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
  if (!(density > 0 && height > 0 && diameter > 0)) {
    els.heightMassPreview.textContent = "Enter height and density to calculate target formula mass.";
    return;
  }
  try {
    const data = await api.send("/api/target-mass-from-height", "POST", {
      theoretical_density_g_cm3: density,
      height_mm: height,
      diameter_mm: diameter,
    });
    els.heightMassPreview.textContent = `Calculated target formula mass: ${formatNumber(data.target_mass_g, 6)} g from ${formatNumber(data.volume_cm3, 6)} cm3.`;
  } catch (error) {
    els.heightMassPreview.textContent = error.message;
  }
}

async function currentTargetMass() {
  if (selectedAmountMode() === "mass") {
    return Number(els.targetMass.value);
  }
  const density = theoreticalDensityFromSelect(els.heightDensityChoice, els.heightDensity);
  const data = await api.send("/api/target-mass-from-height", "POST", {
    theoretical_density_g_cm3: density,
    height_mm: Number(els.targetHeight.value),
    diameter_mm: Number(els.targetDiameter.value),
  });
  return Number(data.target_mass_g);
}

async function calculateRecipe(event) {
  event.preventDefault();
  setMessage(els.recipeMessage, "Calculating...");
  els.recipeTableBody.innerHTML = "";
  els.recipeMetrics.innerHTML = "";
  els.recipeSummary.textContent = "";

  try {
    const mass = await currentTargetMass();
    const payload = {
      target: els.targetFormula.value.trim(),
      mass_g: mass,
      selected_powders: Array.from(state.selectedPowders),
    };
    const data = await api.send("/api/recipe", "POST", payload);
    state.lastRecipe = { payload, result: data.result, stock_ok: data.stock_ok, stock_messages: data.stock_messages };
    state.lastRecipeMass = mass;
    renderRecipeResult(data, mass);
  } catch (error) {
    setMessage(els.recipeMessage, error.message, "error");
  }
}

function renderRecipeResult(data, mass) {
  const result = data.result || {};
  if (!result.recipe) {
    setMessage(els.recipeMessage, result.warning || "No recipe generated", "error");
    return;
  }

  setMessage(
    els.recipeMessage,
    result.warning || (data.stock_ok ? "Recipe calculated." : data.stock_messages.join("; ")),
    data.stock_ok && !result.warning ? "good" : "warning",
  );

  els.recipeDetails.textContent =
    `Basis: ${result.basis}; residual: ${formatNumber(result.residual, 10)}; target formula mass: ${formatNumber(mass, 6)} g; total precursor powder: ${formatNumber(result.powder_basis, 6)} g.`;
  els.recipeMetrics.innerHTML = `
    <div class="metric-card"><strong>${formatNumber(result.estimated_target_mass, 6)}</strong><small>estimated target mass g</small></div>
    <div class="metric-card"><strong>${formatNumber(result.powder_basis, 6)}</strong><small>total precursor powder g</small></div>
    <div class="metric-card"><strong>${result.exact ? "Exact" : "Approx"}</strong><small>stoichiometry</small></div>
  `;

  els.recipeTableBody.innerHTML = "";
  for (const [powder, grams] of Object.entries(result.recipe)) {
    const available = data.inventory[powder];
    const after = available === undefined ? null : Number(available) - Number(grams);
    const tr = document.createElement("tr");
    tr.className = after !== null && after < 0 ? "short" : after !== null && after < 10 ? "low" : "";
    tr.innerHTML = `
      <td>${escapeHtml(powder)}</td>
      <td>${formatNumber(grams, 6)}</td>
      <td>${available === undefined ? "Not in inventory" : formatNumber(available, 3)}</td>
      <td>${after === null ? "" : formatNumber(after, 3)}</td>
    `;
    els.recipeTableBody.appendChild(tr);
  }

  els.recipeSummary.textContent = recipeSummaryText(result, mass);
}

function recipeSummaryText(result, mass) {
  const lines = [
    `Target: ${result.normalized_target || els.targetFormula.value.trim()}`,
    `Target for: ${normalizeOwner(els.recipeTargetFor.value) || "quick calculation"}`,
    `Target formula mass: ${formatNumber(mass, 6)} g`,
    `Total precursor powder: ${formatNumber(result.powder_basis, 6)} g`,
    "Powders:",
  ];
  for (const [powder, grams] of Object.entries(result.recipe || {})) {
    lines.push(`- ${powder}: ${formatNumber(grams, 6)} g`);
  }
  if (els.recipeNotes.value.trim()) lines.push(`Notes: ${els.recipeNotes.value.trim()}`);
  return lines.join("\n");
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

async function deductInventory() {
  if (!state.lastRecipe?.result?.recipe) {
    flash("Calculate a recipe before deducting inventory.", "warning");
    return;
  }
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
    return;
  }
  els.densityTargetFormula.value = linked.target || "";
  els.densityTargetFor.value = linked.target_for || "";
  els.linkedRecipeInfo.textContent = `After-sintering density will be linked to ${linked.target_id || linked.recipe_id}.`;
  updateDensityChoicesForTarget(els.densityTargetFormula.value, els.relativeDensityChoice, els.manualRelativeDensityWrap).catch(() => {});
}

async function calculateDensity(event) {
  event.preventDefault();
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
    <div class="metric-card"><strong>${formatNumber(data.measured_density_g_cm3, 5)}</strong><small>measured density g/cm3</small></div>
    <div class="metric-card"><strong>${formatNumber(theoretical, 5)}</strong><small>theoretical density g/cm3</small></div>
    <div class="metric-card"><strong>${formatNumber(relative, 2)}%</strong><small>relative density</small></div>
  `;
  els.densitySummary.textContent = [
    `Target: ${els.densityTargetFormula.value.trim()}`,
    `Target for: ${normalizeOwner(els.densityTargetFor.value) || "quick calculation"}`,
    `Measured density: ${formatNumber(data.measured_density_g_cm3, 5)} g/cm3`,
    `Theoretical density: ${formatNumber(theoretical, 5)} g/cm3`,
    `Relative density: ${formatNumber(relative, 2)}%`,
    `Final volume: ${formatNumber(data.final_volume_cm3, 6)} cm3`,
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
      target: els.densityTargetFormula.value.trim(),
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
      select.insertAdjacentHTML("beforeend", `<option value="${escapeHtml(powder)}">${escapeHtml(powder)}</option>`);
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
    `${powder} current stock: ${formatNumber(current, 4)} g`,
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
      <td>${escapeHtml(powder)}</td>
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
  const low = rows.filter(([, grams]) => Number(grams) < 10).map(([powder]) => powder);
  els.lowStockDashboard.textContent = low.length ? `Low inventory below 10 g: ${low.join(", ")}` : "No powder below 10 g.";
  els.lowStockDashboard.className = `message ${low.length ? "warning" : "good"}`;

  els.inventoryTableBody.innerHTML = "";
  for (const [powder, grams] of rows) {
    const need = recipe[powder];
    const after = need === undefined ? null : Number(grams) - Number(need);
    const tr = document.createElement("tr");
    tr.className = after !== null && after < 0 ? "short" : Number(grams) < 10 || (after !== null && after < 10) ? "low" : "";
    tr.innerHTML = `
      <td>${escapeHtml(powder)}</td>
      <td>${formatNumber(grams, 3)}</td>
      <td>${need === undefined ? "" : formatNumber(need, 6)}</td>
      <td>${after === null ? "" : formatNumber(after, 3)}</td>
    `;
    els.inventoryTableBody.appendChild(tr);
  }

  els.ledgerTableBody.innerHTML = "";
  for (const entry of [...state.inventoryLog].reverse().slice(0, 200)) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${niceTime(entry.time)}</td>
      <td>${escapeHtml(entry.powder)}</td>
      <td>${formatNumber(entry.change_g, 6)}</td>
      <td>${formatNumber(entry.before_g, 6)}</td>
      <td>${formatNumber(entry.after_g, 6)}</td>
      <td>${escapeHtml(entry.action)}</td>
      <td class="wrap">${escapeHtml(entry.reason || entry.notes || "")}</td>
    `;
    els.ledgerTableBody.appendChild(tr);
  }
}

async function addPowder(event) {
  event.preventDefault();
  const done = setBusy(event.submitter, "Adding...");
  try {
    const data = await api.send("/api/powders", "POST", {
      formula: els.newPowderFormula.value,
      initial_grams: Number(els.newPowderGrams.value),
    });
    state.powders = data.powders || state.powders;
    state.inventory = data.inventory || state.inventory;
    renderEverything();
    await loadPowderOptions();
    flash(`Added ${data.powder}.`);
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
    flash(`${verb} ${formatNumber(amount, 4)} g for ${powder}. New stock: ${formatNumber(next, 4)} g.`);
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
  const done = setBusy(event.submitter, "Deleting...");
  try {
    const params = new URLSearchParams({ remove_inventory: String(els.removeDeletedStock.checked) });
    const data = await api.send(`/api/powders/${encodeURIComponent(powder)}?${params.toString()}`, "DELETE");
    state.powders = data.powders || state.powders;
    state.inventory = data.inventory || state.inventory;
    renderEverything();
    await loadPowderOptions();
    flash(`Deleted ${powder}.`);
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
  previewMaterialDensity().catch(() => {});
}

function densityCellPayload() {
  return {
    formula: els.materialFormula.value.trim(),
    crystal_system: els.crystalSystem.value,
    a_A: numberOrNull(els.latticeA.value),
    b_A: numberOrNull(els.latticeB.value),
    c_A: numberOrNull(els.latticeC.value),
    alpha_deg: numberOrNull(els.latticeAlpha.value),
    beta_deg: numberOrNull(els.latticeBeta.value),
    gamma_deg: numberOrNull(els.latticeGamma.value),
    unit_cell_volume_A3: numberOrNull(els.unitCellVolume.value),
    z: Number(els.zValue.value),
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
    els.materialDensityPreview.textContent = `Manual density: ${formatNumber(els.manualMaterialDensity.value, 5)} g/cm3`;
    return;
  }
  try {
    const payload = densityCellPayload();
    if (mode === "From lattice parameters") payload.unit_cell_volume_A3 = null;
    const data = await api.send("/api/density-from-cell", "POST", payload);
    els.materialDensityPreview.textContent = `Unit cell volume: ${formatNumber(data.unit_cell_volume_A3, 5)} A3; theoretical density: ${formatNumber(data.theoretical_density_g_cm3, 5)} g/cm3.`;
  } catch (error) {
    els.materialDensityPreview.textContent = error.message;
  }
}

async function saveMaterialDensity(event) {
  event.preventDefault();
  const done = setBusy(event.submitter, "Saving...");
  try {
    const mode = els.densityEntryMode.value;
    const payload = {
      ...densityCellPayload(),
      phase: els.materialPhase.value,
      theoretical_density_g_cm3: mode === "Manual theoretical density" ? Number(els.manualMaterialDensity.value) : null,
      density_source: mode === "Manual theoretical density" ? "manual" : mode === "From unit cell volume" ? "unit cell" : "lattice parameters",
      source: els.densitySource.value,
      source_url: els.densitySourceUrl.value,
      doi: els.densityDoi.value,
      cod_id: els.densityCod.value,
      paper_title: els.densityPaperTitle.value,
      notes: els.densityRecordNotes.value,
      verification_status: els.densityTrustStatus.value,
      verified_by: els.densityVerifiedBy.value,
      verified_date: els.densityVerifiedDate.value,
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

function renderMaterialDensityTable() {
  const search = els.densitySearch.value.trim().toLowerCase();
  const scope = els.densityReviewScope.value;
  const rows = Object.values(state.densities)
    .filter((record) => {
      const text = JSON.stringify(record).toLowerCase();
      if (search && !text.includes(search)) return false;
      const status = String(record.verification_status || "").toLowerCase();
      if (scope === "Needs review") return !status.includes("checked") && !status.includes("preferred") && !status.includes("do not use");
      if (scope === "Verified/preferred") return status.includes("checked") || status.includes("preferred");
      return true;
    })
    .sort((a, b) => String(a.formula).localeCompare(String(b.formula)) || String(a.phase).localeCompare(String(b.phase)));

  els.materialDensityTableBody.innerHTML = "";
  for (const record of rows.slice(0, 600)) {
    const tr = document.createElement("tr");
    const status = String(record.verification_status || "").toLowerCase();
    tr.className = [
      String(record.origin || "").toLowerCase().startsWith("codex") ? "codex" : "",
      status.includes("do not use") ? "blocked" : "",
    ].join(" ").trim();
    const sourceLink = record.source_url
      ? `<a href="${escapeHtml(record.source_url)}" target="_blank" rel="noopener">${escapeHtml(record.source_url)}</a>`
      : escapeHtml(record.doi || record.source || record.paper_title || "");
    tr.innerHTML = `
      <td>${escapeHtml(record.formula)}</td>
      <td>${escapeHtml(record.phase || "")}</td>
      <td>${formatNumber(record.theoretical_density_g_cm3, 5)}</td>
      <td>${formatNumber(record.unit_cell_volume_A3, 5)}</td>
      <td>${formatNumber(record.z, 4)}</td>
      <td class="wrap">${escapeHtml(record.verification_status || "")}</td>
      <td class="wrap">${sourceLink}</td>
      <td><button class="icon" title="Delete density record" data-delete-density="${escapeHtml(record.record_key || record.record_id)}">&#128465;</button></td>
    `;
    els.materialDensityTableBody.appendChild(tr);
  }
  els.materialDensityTableBody.querySelectorAll("[data-delete-density]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
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
    ? `${entry.recipe_id || "Recipe"} - ${formatNumber(entry.mass, 6)} g target basis`
    : `Density ${formatNumber(entry.relative_density_percent, 2)}%`;
  const meta = type === "Before sintering"
    ? `${niceTime(entry.time)} | powders: ${Object.entries(entry.recipe || {}).map(([p, g]) => `${p} ${formatNumber(g, 6)} g`).join(", ")}`
    : `${niceTime(entry.time)} | measured ${formatNumber(entry.measured_density_g_cm3, 5)} g/cm3, theoretical ${formatNumber(entry.theoretical_density_g_cm3, 5)} g/cm3`;
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

function setupEvents() {
  els.adminPin.value = localStorage.getItem("stoichioAdminPin") || "";
  els.savePin.addEventListener("click", () => {
    localStorage.setItem("stoichioAdminPin", els.adminPin.value.trim());
    flash("Admin PIN saved in this browser.");
  });
  $$("input[name='amountMode']").forEach((input) => input.addEventListener("change", toggleAmountMode));
  els.targetFormula.addEventListener("input", debounce(async () => {
    await loadPowderOptions();
    await updateDensityChoicesForTarget(els.targetFormula.value, els.heightDensityChoice, els.manualHeightDensityWrap);
    previewHeightMass().catch(() => {});
  }, 220));
  els.recipeTargetFor.addEventListener("input", () => updateTargetPreview(els.recipeTargetFor, els.recipeTargetPreview));
  els.densityTargetFor.addEventListener("input", () => updateTargetPreview(els.densityTargetFor, els.densityTargetPreview));
  els.showAllPowders.addEventListener("change", () => loadPowderOptions().catch((error) => flash(error.message, "error")));
  els.reloadPowders.addEventListener("click", () => loadPowderOptions().catch((error) => flash(error.message, "error")));
  [els.targetHeight, els.targetDiameter, els.heightDensity, els.heightDensityChoice].forEach((input) => {
    input.addEventListener("input", () => previewHeightMass().catch(() => {}));
    input.addEventListener("change", () => {
      els.manualHeightDensityWrap.hidden = els.heightDensityChoice.value !== "__manual__";
      previewHeightMass().catch(() => {});
    });
  });
  els.recipeForm.addEventListener("submit", calculateRecipe);
  els.saveRecipe.addEventListener("click", saveRecipe);
  els.deductInventory.addEventListener("click", deductInventory);

  els.linkedRecipe.addEventListener("change", onLinkedRecipeChange);
  els.densityTargetFormula.addEventListener("input", debounce(() => updateDensityChoicesForTarget(els.densityTargetFormula.value, els.relativeDensityChoice, els.manualRelativeDensityWrap), 220));
  els.relativeDensityChoice.addEventListener("change", () => {
    els.manualRelativeDensityWrap.hidden = els.relativeDensityChoice.value !== "__manual__";
  });
  els.densityForm.addEventListener("submit", calculateDensity);
  els.saveDensityHistory.addEventListener("click", saveDensityHistory);

  els.addPowderForm.addEventListener("submit", addPowder);
  els.inventoryForm.addEventListener("submit", (event) => event.preventDefault());
  els.inventoryPowder.addEventListener("change", renderInventoryAdjustment);
  els.inventoryAdd.addEventListener("click", () => adjustInventory("add", els.inventoryAdd));
  els.inventoryRemove.addEventListener("click", () => adjustInventory("remove", els.inventoryRemove));
  els.deletePowderForm.addEventListener("submit", removePowder);

  els.densityEntryMode.addEventListener("change", toggleDensityEntryMode);
  [
    els.materialFormula, els.crystalSystem, els.latticeA, els.latticeB, els.latticeC,
    els.latticeAlpha, els.latticeBeta, els.latticeGamma, els.unitCellVolume,
    els.zValue, els.manualMaterialDensity,
  ].forEach((input) => input.addEventListener("input", debounce(() => previewMaterialDensity(), 260)));
  els.materialDensityForm.addEventListener("submit", saveMaterialDensity);
  els.densitySearch.addEventListener("input", renderMaterialDensityTable);
  els.densityReviewScope.addEventListener("change", renderMaterialDensityTable);
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
setupEvents();
toggleAmountMode();
toggleDensityEntryMode();
loadAll().catch((error) => {
  els.serviceStatus.textContent = error.message;
  flash(error.message, "error");
});
