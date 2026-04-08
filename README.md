# ResQNet Backend

FastAPI backend for the ResQNet disaster intelligence platform.

## Prerequisites

- Python 3.10+
- pip

---

## Setup

### 1. Clone / navigate to the backend folder
```bash
cd "Hackathon 10/backend"
```

### 2. Create a virtual environment
```bash
python -m venv venv
```

Activate it:

**Windows**
```bash
venv\Scripts\activate
```

**Mac / Linux**
```bash
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

The `.env` file is already present in the `backend/` folder with Supabase credentials. No changes needed.

```
SUPABASE_URL=https://avqylsoystodlrvdzsdh.supabase.co
SUPABASE_ANON_KEY=sb_publishable_...
SUPABASE_SERVICE_KEY=sb_secret_...
```

---

## Run the Server

```bash
uvicorn app.main:app --reload --port 8080
```

- `--reload` — auto-restarts on code changes (dev only)
- Server runs at: **http://localhost:8080**

---

## API Docs

Interactive Swagger UI (test all endpoints in browser):
```
http://localhost:8080/docs
```

Full written documentation: see `API_DOCS.md` in the project root.

---

## Database Setup (One-time)

Two SQL files need to be run in the **Supabase SQL Editor** (Dashboard → SQL Editor):

1. **`schema.sql`** — creates all tables and seeds rescue units
2. **`migration.sql`** — adds extra columns for full functionality

Run `schema.sql` first, then `migration.sql`.

---

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app entry point, router registration
│   ├── supabase_client.py   # Supabase admin + anon clients
│   ├── routers/
│   │   ├── auth.py          # Signup, login, phone OTP
│   │   ├── reports.py       # Report submission + geo-clustering
│   │   ├── events.py        # Disaster events
│   │   ├── rescue.py        # Rescue unit allocation
│   │   ├── grid.py          # Risk heatmap grid
│   │   ├── predictions.py   # Early warning engine
│   │   ├── simulation.py    # Digital twin simulation
│   │   ├── dashboard.py     # Stats + activity feed
│   │   └── external.py      # News / social / weather ingestion
│   └── services/
│       ├── confidence.py    # Weighted confidence scoring
│       ├── clustering.py    # Haversine distance + geo-clustering
│       ├── rescue_allocator.py  # Nearest unit finder + ETA
│       ├── predictor.py     # Early warning trigger logic
│       └── simulator.py     # Spread simulation + impact comparison
├── .env                     # Supabase credentials (do not commit)
├── requirements.txt
└── README.md
```

---

## Test Credentials

| Type | Value |
|------|-------|
| Email | `admin@resqnet.com` |
| Password | `Admin1234!` |
| Phone | `+919999999999` |
| OTP | `222222` |

> Phone OTP must be added in Supabase Dashboard → Authentication → Phone → Test numbers.

---

## Quick Endpoint Test

After starting the server, run these to verify everything works:

```bash
# Health check
curl http://localhost:8080/

# Dashboard stats
curl http://localhost:8080/dashboard/stats

# List rescue units
curl http://localhost:8080/rescue/units

# Submit a test report
curl -X POST http://localhost:8080/reports \
  -H "Content-Type: application/json" \
  -d '{
    "source": "app",
    "latitude": 12.9352,
    "longitude": 77.6245,
    "disaster_type": "flood",
    "description": "Test report",
    "people_count": 3,
    "injuries": false
  }'
```
