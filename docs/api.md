# API Documentation

## 1. Overview

The Transaction Reconciliation System exposes REST API endpoints through a FastAPI backend. The React frontend uses these endpoints to upload settlement data, retrieve transaction records, view reconciliation issues, and display dashboard summaries.

**Base URL:** `http://127.0.0.1:8000`

**API interface:** `http://127.0.0.1:8000/docs`

## 2. API Endpoints

GET = `/health` - Checks whether the backend is running 
GET = `/database/tables` - Retrieves database table information 
POST = `/reconcile` - Uploads and processes a settlement CSV file 
GET = `/transactions` - Retrieves transaction records 
GET = `/transactions/{transaction_id}` - Retrieves details for a specific transaction 
GET = `/issues` - Retrieves identified reconciliation issues 
GET = `/dashboard/summary` - Retrieves summary information for the dashboard 

These endpoints describe the intended interface based on the current project implementation. Confirm the available routes and exact response fields using the running FastAPI application's `/docs` page.

## 3. Endpoint Details

### 3.1 Health Check

**Request**

`GET /health`

**Purpose:** Checks whether the backend service is running.

**Example response**

```json
{
  "status": "ok"
}
```

The exact response depends on the implementation in `main.py`.

### 3.2 Database Tables

**Request**

`GET /database/tables`

**Purpose:** Provides information about the tables available in the SQLite database.

### 3.3 Reconcile Settlement CSV

**Request**

`POST /reconcile`

**Purpose:** Uploads a settlement CSV file and processes its records against existing transactions.

**Content type:** `multipart/form-data`

**Input:** A CSV file containing the required settlement fields.

Expected CSV columns:

- `settlement_id`
- `lifecycle_id`
- `account_id`
- `merchant_name`
- `transaction_date`
- `settlement_date`
- `settlement_amount`
- `settlement_type`
- `currency`

**Processing includes:**

1. Validating the CSV structure and record values.
2. Matching settlements against existing transactions.
3. Identifying unmatched and duplicate records.
4. Recording matched settlements.
5. Updating settlement amounts and statuses.
6. Returning a reconciliation report.

**Response information:** The report includes counts for received rows, matched records, unmatched records, duplicates, and issues, subject to the implemented response schema.

### 3.4 List Transactions

**Request**

`GET /transactions`

**Purpose:** Retrieves transaction records for display in the transactions interface.

The returned information may include transaction identifiers, merchant details, original amounts, settlement amounts, and settlement statuses.

### 3.5 Get a Specific Transaction

**Request**

`GET /transactions/{transaction_id}`

**Example**

`GET /transactions/TXN001`

**Purpose:** Retrieves the details of an individual transaction.

The transaction ID must identify a record in the database.

### 3.6 List Reconciliation Issues

**Request**

`GET /issues`

**Purpose:** Retrieves reconciliation issues identified by the backend, allowing users to review records requiring attention.

### 3.7 Dashboard Summary

**Request**

`GET /dashboard/summary`

**Purpose:** Retrieves summary statistics used by the dashboard, such as transaction and settlement information supported by the implementation.

## 4. Error Handling

The API may return HTTP error responses when requests contain invalid data, required fields are missing, a requested transaction cannot be found, or an internal processing error occurs.

Clients should check the HTTP status code and response body before displaying a result.

Typical HTTP status codes include:


200 - Request processed successfully 
400 - Invalid request or input data 
404 - Requested resource not found 
422 - Request validation failed 
500 - Unexpected server-side error 

The exact status codes depend on each endpoint's implementation.

## 5. Running and Exploring the API

Start the backend from the project directory:

```powershell
cd D:\TransactionReconciliation\backend
python -m uvicorn main:app --reload
```

Open the interactive API documentation:

`http://127.0.0.1:8000/docs`

The Swagger UI allows users to inspect the available endpoints, review request parameters, and send test requests.

## 6. Frontend Integration

The React frontend communicates with the FastAPI backend over HTTP. The backend processes requests and returns responses, which the frontend displays in the upload report, dashboard, transactions list, and issues page.

The frontend does not connect directly to SQLite. All database operations are handled by the backend.
