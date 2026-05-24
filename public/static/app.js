const api = {
  async get(path) {
    const response = await fetch(path);
    if (!response.ok) throw new Error(await errorMessage(response));
    return response.json();
  },
  async send(path, method, body) {
    const response = await fetch(path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(await errorMessage(response));
    return response.json();
  },
};

const state = {
  powders: {},
  relevant: [],
  hidden: [],
  selected: new Set(["Fe2O3", "TiO2"]),
};

const els = {
  status: document.getElementById("serviceStatus"),
  target: document.getElementById("targetFormula"),
  amountMode: document.getElementById("amountMode"),
  massField: document.getElementById("massField"),
  heightField: document.getElementById("heightField"),
  densityField: document.getElementById("densityField"),
  targetMass: document.getElementById("targetMass"),
  targetHeight: document.getElementById("targetHeight"),
  heightDensity: document.getElementById("heightDensity"),
  powderList: document.getElementById("powderList"),
  powderFilterHint: document.getElementById("powderFilterHint"),
  recipeForm: document.getElementById("recipeForm"),
  recipeMessage: document.getElementById("recipeMessage"),
  recipeTableBody: document.querySelector("#recipeTable tbody"),
  recipeDetails: document.getElementById("recipeDetails"),
  densityForm: document.getElementById("densityForm"),
  densityResult: document.getElementById("densityResult"),
  inventoryTableBody: document.querySelector("#inventoryTable tbody"),
  refreshInventory: document.getElementById("refreshInventory"),
};

async function errorMessage(response) {
  try {
    const data = await response.json();
    return data.detail || JSON.stringify(data);
  } catch {
    return response.statusText;
  }
}

function formatNumber(value, digits = 4) {
  if (value === null || value === undefined || value === "") return "";
  const number = Number(value);
  if (!Number.isFinite(number)) return "";
  return number.toFixed(digits).replace(/\.?0+$/, "");
}

function setMessage(element, text, kind = "") {
  element.className = `message ${kind}`.trim();
  element.textContent = text;
}

async function loadHealth() {
  const health = await api.get("/api/health");
  els.status.textContent = health.ok ? health.storage_mode : "API unavailable";
}

async function loadPowders() {
  const target = encodeURIComponent(els.target.value.trim());
  const data = await api.get(`/api/powders?target=${target}`);
  state.powders = data.powders;
  state.relevant = data.relevant;
  state.hidden = data.hidden;

  const options = data.relevant.length ? data.relevant : Object.keys(data.powders);
  state.selected = new Set(Array.from(state.selected).filter((powder) => options.includes(powder)));
  for (const powder of options) {
    if (["Fe2O3", "TiO2"].includes(powder)) state.selected.add(powder);
  }
  renderPowders(options, data);
  renderInventory(data.powders);
}

function renderPowders(options, data) {
  els.powderList.innerHTML = "";
  els.powderFilterHint.textContent = data.filter_error
    ? `Formula filter error: ${data.filter_error}`
    : `Showing ${options.length} relevant powder(s). Hidden: ${data.hidden.length}.`;

  for (const powder of options) {
    const record = state.powders[powder];
    const row = document.createElement("div");
    row.className = "powder-option";
    row.innerHTML = `
      <label>
        <input type="checkbox" value="${powder}">
        <span>${powder}</span>
      </label>
      <span class="pill">${formatNumber(record.molar_mass_g_mol, 3)} g/mol</span>
    `;
    const checkbox = row.querySelector("input");
    checkbox.checked = state.selected.has(powder);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) state.selected.add(powder);
      else state.selected.delete(powder);
    });
    els.powderList.appendChild(row);
  }
}

function renderInventory(powders) {
  const rows = Object.entries(powders)
    .filter(([, record]) => record.available_g !== null && record.available_g !== undefined)
    .sort(([a, ra], [b, rb]) => {
      const lowA = Number(ra.available_g) < 10 ? 0 : 1;
      const lowB = Number(rb.available_g) < 10 ? 0 : 1;
      return lowA - lowB || a.localeCompare(b);
    });

  els.inventoryTableBody.innerHTML = "";
  for (const [powder, record] of rows) {
    const available = Number(record.available_g);
    const tr = document.createElement("tr");
    tr.className = available < 10 ? "low" : "";
    tr.innerHTML = `
      <td>${powder}</td>
      <td>${formatNumber(available, 3)}</td>
      <td>${available < 10 ? "Low stock" : "OK"}</td>
    `;
    els.inventoryTableBody.appendChild(tr);
  }
}

async function currentTargetMass() {
  if (els.amountMode.value === "mass") {
    return Number(els.targetMass.value);
  }

  const data = await api.send("/api/target-mass-from-height", "POST", {
    theoretical_density_g_cm3: Number(els.heightDensity.value),
    height_mm: Number(els.targetHeight.value),
  });
  return data.target_mass_g;
}

async function calculateRecipe(event) {
  event.preventDefault();
  setMessage(els.recipeMessage, "Calculating...");
  els.recipeTableBody.innerHTML = "";
  els.recipeDetails.textContent = "";

  try {
    const mass = await currentTargetMass();
    const data = await api.send("/api/recipe", "POST", {
      target: els.target.value.trim(),
      mass_g: mass,
      selected_powders: Array.from(state.selected),
    });
    const result = data.result;
    if (!result.recipe) {
      setMessage(els.recipeMessage, result.warning || "No recipe generated", "error");
      return;
    }

    setMessage(
      els.recipeMessage,
      result.warning || (data.stock_ok ? "Recipe calculated." : data.stock_messages.join("; ")),
      data.stock_ok && !result.warning ? "good" : "warning",
    );

    for (const [powder, grams] of Object.entries(result.recipe)) {
      const available = data.inventory[powder];
      const after = available === undefined ? null : Number(available) - Number(grams);
      const tr = document.createElement("tr");
      tr.className = after !== null && after < 0 ? "short" : after !== null && after < 10 ? "low" : "";
      tr.innerHTML = `
        <td>${powder}</td>
        <td>${formatNumber(grams, 6)}</td>
        <td>${available === undefined ? "Not in inventory" : formatNumber(available, 3)}</td>
        <td>${after === null ? "" : formatNumber(after, 3)}</td>
      `;
      els.recipeTableBody.appendChild(tr);
    }

    els.recipeDetails.textContent =
      `Basis: ${result.basis}; residual: ${formatNumber(result.residual, 10)}; ` +
      `estimated target mass: ${formatNumber(result.estimated_target_mass, 6)} g; ` +
      `total precursor powder: ${formatNumber(result.powder_basis, 6)} g.`;
  } catch (error) {
    setMessage(els.recipeMessage, error.message, "error");
  }
}

async function calculateDensity(event) {
  event.preventDefault();
  try {
    const data = await api.send("/api/relative-density", "POST", {
      final_mass_g: Number(document.getElementById("finalMass").value),
      final_diameter_mm: Number(document.getElementById("finalDiameter").value),
      final_height_mm: Number(document.getElementById("finalHeight").value),
      theoretical_density_g_cm3: Number(document.getElementById("relativeTheoreticalDensity").value),
    });
    setMessage(
      els.densityResult,
      `Measured density ${formatNumber(data.measured_density_g_cm3, 5)} g/cm3, ` +
        `relative density ${formatNumber(data.relative_density_percent, 2)}%, ` +
        `volume ${formatNumber(data.final_volume_cm3, 6)} cm3.`,
      Number(data.relative_density_percent) > 100 ? "warning" : "good",
    );
  } catch (error) {
    setMessage(els.densityResult, error.message, "error");
  }
}

function toggleAmountMode() {
  const heightMode = els.amountMode.value === "height";
  els.massField.hidden = heightMode;
  els.heightField.hidden = !heightMode;
  els.densityField.hidden = !heightMode;
}

let powderTimer = null;
function queuePowderReload() {
  clearTimeout(powderTimer);
  powderTimer = setTimeout(loadPowders, 180);
}

els.amountMode.addEventListener("change", toggleAmountMode);
els.target.addEventListener("input", queuePowderReload);
els.recipeForm.addEventListener("submit", calculateRecipe);
els.densityForm.addEventListener("submit", calculateDensity);
els.refreshInventory.addEventListener("click", loadPowders);

toggleAmountMode();
loadHealth().catch((error) => {
  els.status.textContent = error.message;
});
loadPowders().catch((error) => {
  els.powderFilterHint.textContent = error.message;
});
