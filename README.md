# SmartFlow

SmartFlow is now arranged as a standalone React/Vite + FastAPI project. The React app lives in `src/`, while the Python backend and SUMO runtime live beside it in `backend/`, `simulation/`, `services/`, `tools/`, `sumo/`, `data/`, `auth.py`, `config.py`, and `database.py`.

## Requirements

- Node.js and npm
- Python 3.11+ recommended
- SUMO installed and available to `sumolib`/`traci`

## First Setup

```powershell
npm install
npm run venv:create
npm run venv:install
```

If you move the `SmartFlow` folder to a new location, recreate `.venv` in the new folder. Windows virtual environments store absolute paths, so the workflow above is the reliable portable setup.

## Run Locally

Start the FastAPI backend:

```powershell
npm run api
```

Start the React app in another terminal:

```powershell
npm run dev
```

The React app defaults to `http://127.0.0.1:8000` for API calls. Override it with `VITE_SMARTFLOW_API_BASE_URL` if the backend is hosted somewhere else.

`npm run api` uses `.venv` automatically when it exists, and supplies local development defaults for `SMARTFLOW_SECRET_KEY` and `SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD`. For real use, set your own environment variables before starting the backend.

## Useful Checks

```powershell
npm run check:api
npm run build
```
