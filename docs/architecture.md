# System Architecture

## 1. Overview

The Transaction Reconciliation System is a web application designed to reconcile transaction records with settlement data imported from a CSV file. It identifies matched and unmatched settlements, detects duplicate records, calculates settlement totals, and reports reconciliation issues.

The application uses React for the frontend, FastAPI for the backend, and SQLite for persistent data storage.

## 2. Technology Stack

Frontend: React - User interface for CSV uploads, dashboard summaries, transactions, and issues
Backend: Python, FastAPI - API endpoints, input validation, reconciliation logic, and database operations
Database: SQLite - Stores transactions, settlement history, and imported settlement data
Input Data: CSV - Supplies settlement records for reconciliation
API Server: Uvicorn - Runs the FastAPI application

## 3. High-Level Architecture

```text
+-----------------------------+
|       User / Browser        |
|      React Frontend         |
|      localhost:3000         |
+--------------+--------------+
               |
               | HTTP requests / JSON responses
               | CSV file upload
               v
+-----------------------------+
|       FastAPI Backend       |
|      localhost:8000         |
|                             |
|  - CSV validation           |
|  - Transaction matching     |
|  - Duplicate detection      |
|  - Settlement calculations  |
|  - Issue identification     |
|  - REST API endpoints       |
+--------------+--------------+
               |
               | SQL queries
               v
+-----------------------------+
|        SQLite Database      |
|                             |
|  - transactions             |
|  - settlement_history       |
|  - settlement_import        |
+-----------------------------+
```

## 4. Main Components

# Frontend

The React frontend provides the user interface. Its main functions include:

- Uploading settlement CSV files.
- Displaying reconciliation results.
- Showing dashboard summaries.
- Listing transactions and their settlement statuses.
- Displaying identified reconciliation issues.

The frontend sends HTTP requests to the FastAPI backend and displays the responses.

# Backend

The FastAPI backend processes requests from the frontend. It contains the application's reconciliation logic and database access functions.

Its responsibilities include:

- Validating uploaded CSV files and their required fields.
- Validating settlement dates, amounts, and settlement types.
- Matching settlement records with existing transactions.
- Detecting duplicate and unmatched settlement records.
- Calculating net settlement amounts using debit and credit entries.
- Updating transaction settlement statuses.
- Identifying reconciliation issues.
- Providing dashboard, transaction, and issue information through API endpoints.

# Database

SQLite stores the application's transaction and settlement data in `data/reconciliation.db`.

The database contains three main tables:

transactions: Stores original transaction details and calculated settlement information.

settlement_history: Stores settlement records successfully matched to transactions.

settlement_import: Provides a staging area for settlement CSV records during processing.

# Input Data

The settlement CSV file provides the records to reconcile. Each record includes information such as settlement ID, lifecycle ID, account ID, merchant name, transaction date, settlement date, amount, settlement type, and currency.

## 5. Reconciliation Workflow

1. The user uploads a settlement CSV file through the React interface.
2. The frontend sends the file to the backend reconciliation endpoint.
3. The backend validates the file structure and its records.
4. The backend attempts to match each settlement record to an existing transaction.
5. Matched records are checked for duplicates and processed into settlement history.
6. The backend calculates net settlement amounts from debit and credit entries.
7. Transaction settlement statuses and applicable reconciliation issues are updated.
8. The backend returns a reconciliation report.
9. The frontend displays the results to the user.

## 6. Transaction Matching

The system primarily uses the lifecycle ID to match settlement records to transactions.

When a settlement record has no lifecycle ID, the system can use the account ID, merchant name, and transaction date as fallback matching fields.

Records that cannot be matched are reported as unmatched rather than being assigned to an unrelated transaction.

## 7. Settlement Calculation

Debit and credit entries are used to calculate the net settled amount:

Net settled amount = Total debit amount − Total credit amount

The calculated amount is compared with the original transaction amount to determine the settlement status.

The system distinguishes between pending, partially settled, fully settled, over-settled, and refunded transactions, subject to the application's implemented business rules. Failed or declined transactions are marked as not applicable for settlement.

## 8. Error Handling and Data Integrity

The backend validates uploaded data before processing it. Invalid records and unmatched settlements are reported so they can be investigated.

Duplicate settlement IDs are handled to reduce repeated processing. SQLite primary keys and the foreign-key relationship between settlement history and transactions help maintain data integrity.

## 9. Deployment

During development, the React frontend and FastAPI backend run locally on separate ports. The SQLite database is stored locally and accessed by the backend.

The frontend communicates with the backend through HTTP API requests. The database is not accessed directly by the frontend.
