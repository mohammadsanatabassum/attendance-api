# Employee Attendance & Analytics API

An enterprise-ready attendance tracking and analytics API built with **FastAPI** and **MongoDB 7.0**, adhering strictly to the contract defined in `openapi.yaml`, data model in `DATA_MODEL.md`, and business rules R1–R10.

---

## Features & Implementation Highlights

- **Full OpenAPI 3.0.3 Compliance:** Implements all 11 endpoints across Employees, Attendance, Analytics, and Admin categories.
- **Concurrency & Atomicity:** 
  - Unique compound index on `(emp_code, date)` guarantees zero duplicate punch-in records even under high-concurrency races.
  - Atomic `find_one_and_update` operations prevent duplicate punch-outs and race conditions during attendance regularization.
- **Audit History:** Full immutable audit log for manual regularizations tracking exact field-level state changes (`from` / `to`).
- **MongoDB Aggregation Pipelines:** Real-time analytics built entirely in MongoDB aggregation stages (`$densify` for gap filling across calendar days, `$setWindowFields` for competition ranking and 7-day moving averages, and multi-collection `$lookup`).
- **High-Performance Querying:** Backed by targeted compound indexes ensuring `IXSCAN` plans and eliminating `COLLSCAN` across ~100k-record collections.
- **Accurate Time & Date Math:** Full support for IST (UTC+05:30) timezone, overnight shift transitions, grace period evaluation, and standard half-up Decimal rounding.

---

## Requirements

- Python 3.10+
- MongoDB 7.0+ (requires `$densify` support)

---

## Setup & Running

### 1. Install Dependencies
```bash
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 2. Environment Configuration
The application reads configuration from environment variables with sensible defaults:
- `MONGO_URI`: MongoDB connection string (defaults to `mongodb://localhost:27017`)
- `MONGO_DB`: Database name (defaults to `attendance_db`)

### 3. Seed Sample Data (Optional)
```bash
python sample_seed.py
```

### 4. Start the Application
```bash
uvicorn app.main:app --port 8000
```
Interactive Swagger documentation is available at `http://localhost:8000/docs`.

---

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Readiness probe (pings MongoDB, returns 200 or 503) |
| `POST` | `/employees` | Create a new employee with unique `emp_code` |
| `GET` | `/employees` | Paginated list of employees sorted by `emp_code` ascending |
| `POST` | `/attendance/punch-in` | Punch-in recording with overnight shift and late detection |
| `POST` | `/attendance/punch-out` | Punch-out recording with work hours & overtime calculation |
| `GET` | `/attendance` | Paginated attendance logs sorted by `date` desc, `emp_code` asc |
| `PATCH` | `/attendance/{emp_code}/{date}` | Regularize/correct attendance with immutable audit trail |
| `GET` | `/analytics/employees/{emp_code}/monthly` | Monthly employee summary with attendance percentage |
| `GET` | `/analytics/departments/summary` | Department-level monthly summary including zero-log headcount |
| `GET` | `/analytics/leaderboard/late` | Competition-ranked late-comers leaderboard (`rank <= limit`) |
| `GET` | `/analytics/departments/{department}/trend` | Daily attendance trend with 7-day moving average |
| `GET` | `/admin/explain/{endpoint}` | Execution plan explain endpoint verifying `IXSCAN` coverage |

---

## Testing

A test suite verifying all 11 endpoints, business rules, edge cases, and execution plans:
```bash
python test_app.py
```

---

## Submission Artifacts

- `app/main.py`: Complete implementation in a single file.
- `REVIEW.md`: Comprehensive review of starter defects, impact, and fixes.
- `DECISIONS.md`: Design rationale for indexing, concurrency, ranking, and scalability.
- `requirements.txt`: Python package dependencies.
- `README.md`: Setup, architecture, and running guide.
