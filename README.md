# Stoichio Buddy

Stoichio Buddy is a Streamlit app for deterministic solid-state synthesis recipe calculations. It uses a user-controlled powder database, cation-first stoichiometry, inventory tracking, and recipe history.

## App features

- Light and dark display modes
- User-selected precursor powders only
- Non-negative deterministic stoichiometry solver, with no automatic powder picking
- Add a powder and its starting inventory in one workflow
- Update inventory quantities
- Delete powders added by mistake
- Save theoretical densities for target materials
- Calculate theoretical density from full lattice parameters (`a`, `b`, `c`, `alpha`, `beta`, `gamma`) and `Z`
- Calculate precursor masses from a total powder basis or desired target height with a 25.05 mm die
- Calculate target density and relative density from final sintered dimensions and mass
- Save recipes and target-density results with optional shared per-person target IDs
- Link after-sintering target-density results back to the saved before-sintering recipe
- View each target lifecycle with before-sintering recipe and after-sintering density together
- Store exact linked recipe snapshots on target-density records for traceability
- Printable HTML reports for recipes and target lifecycle records
- Search and filter target lifecycle history by owner, formula, target ID, status, powders, and notes
- Copy-friendly lab notebook summaries for recipe and target-density results, with TXT downloads
- Full JSON data backup download for powders, inventory, densities, and history
- Safe JSON data backup restore with validation and confirmation
- Stoichiometry audit tables for precursor coefficients and element balance
- Saved recipes keep calculation metadata for later audit and CSV export
- Recipe history grouped by target formula, with manual save after calculation
- Target-density history grouped by person
- Save notes with recipe and target-density history entries
- Delete individual history items or clear a whole history group
- Inventory tables flag recipe shortages and stock below 10 g
- CSV export for recipes, powders, inventory, target lifecycle, and history

## Run locally

```bash
pip install -r requirements.txt
streamlit run stochio_buddy.py
```

## Share on a local network

```bash
streamlit run stochio_buddy.py --server.address 0.0.0.0
```

People on the same network can open the Network URL printed by Streamlit.

This is the recommended setup for a fast lab tool: one lab computer runs the app, and everyone on the same network opens that computer's Streamlit URL. Data stays in the local JSON files on that computer.

## Deploy for everyone

The simplest free hosted path is Streamlit Community Cloud plus Google Sheets for shared lab data:

1. Put this folder in a GitHub repository.
2. Go to Streamlit Community Cloud and create a new app from the repository.
3. Set the main file to `stochio_buddy.py`.
4. Add Google Sheets secrets if you want shared persistent powder, inventory, density, and history data.

Shared Google Sheets storage is disabled by default because it is much slower than local JSON. If Google Sheets is not explicitly enabled, the app uses local JSON files. This is good for local/offline use, but local writes on Streamlit Community Cloud are not reliable after app restarts.

## Google Sheets shared storage, no Google Cloud

This option uses a normal Google Sheet plus a small Google Apps Script web app. It avoids Google Cloud service accounts.

Setup:

1. Create a Google Sheet named `Stoichio Buddy Data`.
2. In the Sheet, open Extensions -> Apps Script.
3. Paste this script:

```javascript
const TOKEN_PROPERTY = "STOICHIO_TOKEN";
const TAB_BY_PATH = {
  "powders.json": "powders",
  "inventory.json": "inventory",
  "history.json": "history",
  "material_densities.json": "material_densities",
};

function jsonResponse(payload) {
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}

function tabFor(path) {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();

  if (!spreadsheet) {
    throw new Error("Open Apps Script from the Google Sheet: Extensions -> Apps Script.");
  }

  const title = TAB_BY_PATH[path] || path.replace(".json", "");
  return spreadsheet.getSheetByName(title) || spreadsheet.insertSheet(title);
}

function doGet() {
  return jsonResponse({
    ok: true,
    service: "Stoichio Buddy storage",
  });
}

function doPost(event) {
  try {
    const body = JSON.parse((event.postData && event.postData.contents) || "{}");

    const expectedToken = PropertiesService
      .getScriptProperties()
      .getProperty(TOKEN_PROPERTY);

    if (!expectedToken) {
      return jsonResponse({
        ok: false,
        error: "Missing STOICHIO_TOKEN script property",
      });
    }

    if (body.token !== expectedToken) {
      return jsonResponse({
        ok: false,
        error: "Unauthorized",
      });
    }

    const sheet = tabFor(body.path);

    if (body.action === "load") {
      const lastRow = sheet.getLastRow();
      if (lastRow < 1) {
        return jsonResponse({ ok: true, data: null });
      }

      const chunks = sheet.getRange(1, 1, lastRow, 1).getValues().flat();
      const payload = chunks.join("").trim();
      return jsonResponse({ ok: true, data: payload ? JSON.parse(payload) : null });
    }

    if (body.action === "save") {
      const payload = JSON.stringify(body.data, null, 2);
      const chunks = payload.match(/[\s\S]{1,40000}/g) || [""];
      sheet.clearContents();
      sheet.getRange(1, 1, chunks.length, 1).setValues(chunks.map(chunk => [chunk]));
      return jsonResponse({ ok: true, data: true });
    }

    return jsonResponse({
      ok: false,
      error: "Unknown action: " + body.action,
    });
  } catch (error) {
    return jsonResponse({
      ok: false,
      error: String(error.stack || error),
    });
  }
}
```

4. In Apps Script, open Project Settings -> Script properties.
5. Add property `STOICHIO_TOKEN` with a long random password.
6. Click Deploy -> New deployment -> Web app.
7. Set "Execute as" to yourself.
8. Set "Who has access" to anyone with the link.
9. Copy the web app URL.
10. In Streamlit Community Cloud, open app settings and paste secrets:

```toml
enable_shared_storage = true
apps_script_url = "https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec"
apps_script_token = "the-same-long-random-password"
```

On first connection, the app will create four tabs in the sheet if needed: `powders`, `inventory`, `history`, and `material_densities`. If those tabs are empty, it seeds them from the local JSON files in the repository.

## Google Sheets shared storage, service account

This option also works, but it requires Google Cloud service-account setup. A service account itself is not a running server, but Google Cloud may require billing/payment verification.

1. In Google Cloud Console, create or choose a project.
2. Enable the Google Sheets API. Enable the Google Drive API too if you want the app to create/open sheets by name.
3. Create a service account.
4. Create a JSON key for that service account.
5. Create a Google Sheet named `Stoichio Buddy Data`.
6. Copy the sheet ID from the URL:

```text
https://docs.google.com/spreadsheets/d/SHEET_ID_IS_HERE/edit
```

7. Share the Google Sheet with the service account `client_email` as an editor.
8. In Streamlit Community Cloud, open the app settings and paste secrets in this format:

```toml
enable_shared_storage = true
google_sheet_id = "paste-your-google-sheet-id-here"
google_sheet_name = "Stoichio Buddy Data"

[gcp_service_account]
type = "service_account"
project_id = "your-google-cloud-project-id"
private_key_id = "your-private-key-id"
private_key = """-----BEGIN PRIVATE KEY-----
paste-private-key-here
-----END PRIVATE KEY-----"""
client_email = "your-service-account@your-project.iam.gserviceaccount.com"
client_id = "your-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/your-service-account%40your-project.iam.gserviceaccount.com"
universe_domain = "googleapis.com"
```

There is also a template at `.streamlit/secrets.example.toml`. Do not commit a real `.streamlit/secrets.toml`; it is ignored by Git.

## Data files

- `atomic_masses.json`: atomic masses used for molar mass calculation
- `powders.json`: powder formulas and element compositions
- `inventory.json`: available grams by powder
- `material_densities.json`: target material theoretical densities and unit cell data
- `history.json`: saved recipe calculations

Local JSON writes use small `.json.lock` files to avoid partially written data if two browser sessions save at the same time.
