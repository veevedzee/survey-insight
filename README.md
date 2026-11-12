# Survey Insight

> Open-source survey analytics dashboard. **Work in progress**: the full README
> (features, screenshots, architecture, design decisions) arrives in Milestone 8.

## Run locally

**Backend** (Python 3.11+), from `backend/`:

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
uvicorn survey_insight.api:app --reload --port 8000
```

API docs: http://127.0.0.1:8000/docs

**Frontend** (Node 20+), from `frontend/`:

```bash
npm install
npm run dev
```

Open http://localhost:5173.

**Sample data**, from the project root:

```bash
python sample_data/generate_sample.py
```

## Run tests

```bash
cd backend && pytest
cd frontend && npm test
```
