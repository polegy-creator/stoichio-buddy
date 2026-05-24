# Fast Site Version

This is the non-Streamlit version. It uses:

- FastAPI backend
- Static HTML/CSS/JavaScript frontend
- The same locked `stoichio.chemistry.stoich_engine.compute_recipe` function
- The same local JSON powder, inventory, and material-density files

It is intentionally smaller than the Streamlit app right now. The first version covers the fast daily workflows:

- powder mass calculation
- relevant powder filtering
- inventory preview
- pellet-height target mass mode
- target-density calculation after sintering

## Run

```bash
pip install -r requirements.txt
uvicorn fast_site.app:app --reload --host 0.0.0.0 --port 8701
```

Open:

```text
http://localhost:8701
```

Other computers on the same lab network can use the Network URL for port `8701`.

## Vercel

This repository is ready for Vercel with the root `app.py` entry point and `public/` static assets. Import the GitHub repo into Vercel as a Python/FastAPI project. Vercel installs `requirements.txt`, so that file is intentionally the small fast-site dependency set, not the Streamlit lab app dependency set.

The Vercel deployment uses committed JSON as read-only seed data. Calculations work, but shared editing of powders/inventory/history needs a real database backend later.

## Why It Is Faster Than Streamlit

Streamlit reruns much of the Python page after many UI actions. The fast site only calls small API endpoints, for example `/api/recipe`, when calculation is needed.

## Important Math Rule

The fast site does not reimplement the solver. It imports the exact same engine used by the main app:

```python
from stoichio.chemistry.stoich_engine import compute_recipe
```

That is the key protection: UI can change, but recipe math stays in one place.

## Next Upgrade

The best next step is to move shared lab data from JSON to SQLite. That would make both the lab-computer launcher and the fast site safer for multiple users.
