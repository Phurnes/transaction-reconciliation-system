
# Transaction Reconciliation System

A web-based transaction reconciliation application that matches settlement records from CSV files against existing transaction records, calculates net settlement amounts, identifies duplicates and unmatched records, and displays reconciliation results through a dashboard.

## Technology Stack

- Frontend: React
- Backend: Python, FastAPI
- Database: SQLite
- API documentation: FastAPI Swagger UI

## Features

- Upload settlement records using a CSV file.
- Validate CSV structure, required fields, dates, amounts, and settlement types.
- Match settlements against transactions using lifecycle identifiers.
- Use account ID, merchant name, and transaction date as fallback matching fields when the lifecycle identifier is unavailable.
- Skip duplicate settlement IDs.
- Calculate net settlement amounts using debit and credit entries.
- Assign settlement statuses.
- Identify unmatched settlements and reconciliation issues.
- View transaction records, issues, and dashboard summaries.

## Project Structure

```text
TransactionReconciliation/
├── backend/
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── package.json
│   └── src/
├── database/
│   ├── schema.sql
│   └── seed_transactions.sql
├── docs/
└── data/
    ├── reconciliation.db
    └── settlements.csv
```

## Prerequisites

- Python 3.10 or later, compatible with the installed dependencies
- Node.js and npm
- SQLite

## Setup Instructions

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd TransactionReconciliation
```

### 2. Set up the backend

Open a terminal:

```bash
cd backend
python -m venv .venv
```

Activate the environment on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Start the backend:

```bash
python -m uvicorn main:app --reload
```

The API will be available at:

http://127.0.0.1:8000

Interactive API documentation:

http://127.0.0.1:8000/docs

### 3. Set up the frontend

Open a second terminal:

```bash
cd frontend
npm install
npm start
```

The React application will normally open at:

http://localhost:3000

Keep both terminals running while using the application.

## Database Setup

The application uses SQLite. Database initialization and sample data scripts are provided in the `database/` directory.

See `database/README.md` for the exact initialization instructions.

## API Overview

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | API welcome message |
| GET | `/health` | Check API and database availability |
| GET | `/database/tables` | List database tables |
| GET | `/transactions` | Retrieve transactions |
| GET | `/transactions/{transaction_id}` | Retrieve one transaction |
| POST | `/reconcile` | Upload and reconcile a settlement CSV |
| GET | `/dashboard/summary` | Retrieve dashboard statistics |
| GET | `/issues` | Retrieve reconciliation issues |

For request parameters, response formats, and error handling, see `docs/api-documentation.md`.

## Reconciliation Logic

1. Read and validate the uploaded CSV.
2. Match each settlement to an existing transaction.
3. Skip settlement IDs already processed.
4. Calculate net settlement amounts from debit and credit entries.
5. Update settlement totals and statuses.
6. identify unmatched settlements and reconciliation issues.
7. Return the reconciliation results to the frontend.

## Documentation

- `docs/architecture.md` — solution architecture
- `docs/api-documentation.md` — API specifications
- `docs/assumptions.md` — business rules and assumptions
- `docs/limitations.md` — known limitations and future improvements

## Security and Data Handling

This project is intended for local development and demonstration. Production deployment would require additional security, authentication, access control, and operational safeguards.
