# Vercel Lab Website

This is the non-Streamlit Stoichio Buddy website. It uses:

- FastAPI backend
- Static HTML/CSS/JavaScript frontend
- The same locked `stoichio.chemistry.stoich_engine.compute_recipe` function
- The same JSON data model for powders, inventory, material densities, powder sets, and history
- Optional GitHub-backed JSON storage for live Vercel edits

The Vercel website is intended to become the real lab app, not a demo. The page order mirrors the Streamlit app:

1. Powder Mass Calculation
2. Target Density
3. Powder & Inventory
4. Material Density
5. History

## Run Locally

```bash
pip install -r requirements.txt
uvicorn fast_site.app:app --reload --host 0.0.0.0 --port 8701
```

Open:

```text
http://localhost:8701
```

## Deploy To Vercel

Import the GitHub repo into Vercel. Use the repository root as the project root.

If Vercel asks:

```text
Install command: pip install -r requirements.txt
Build command: leave empty/default
Output directory: leave empty/default
```

## Live Data On Vercel

Vercel cannot safely save changing app data into local JSON files. The website supports GitHub-backed JSON storage instead.

Recommended setup:

```text
main branch       -> website code, Vercel deploys this
lab-data branch   -> live JSON data, edited by the app
```

Add these Vercel environment variables:

```text
GITHUB_DATA_REPO=polegy-creator/stoichio-buddy
GITHUB_DATA_BRANCH=lab-data
GITHUB_DATA_TOKEN=your_github_fine_grained_token
STOICHIO_ADMIN_PIN=choose_a_lab_edit_pin
```

The GitHub token should have contents read/write access to this repository. The admin PIN is entered in the app sidebar before editing powders, inventory, densities, or history.

If the GitHub variables are missing, the Vercel site still calculates recipes from the committed seed JSON, but editing is disabled.

## Important Math Rule

The web app does not reimplement recipe math. It imports the exact same engine used by the Streamlit app:

```python
from stoichio.chemistry.stoich_engine import compute_recipe
```

That keeps the lab calculation locked while the UI changes.
