
import csv
import io
import sqlite3
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware


# ============================================================
# APPLICATION CONFIGURATION
# ============================================================

app = FastAPI(title="Transaction Reconciliation System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "data" / "reconciliation.db"

CENT = Decimal("0.01")
MAX_FILE_SIZE = 10 * 1024 * 1024

REQUIRED_CSV_COLUMNS = {
    "settlement_id",
    "lifecycle_id",
    "account_id",
    "merchant_name",
    "transaction_date",
    "settlement_date",
    "settlement_amount",
    "settlement_type",
    "currency",
}

ALLOWED_SETTLEMENT_TYPES = {"DEBIT", "CREDIT"}


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_connection():
    if not DATABASE_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Database not found: {DATABASE_PATH}",
        )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def money(value):
    try:
        return Decimal(str(value or "0")).quantize(
            CENT,
            rounding=ROUND_HALF_UP,
        )
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.00")


def normalize_text(value):
    return str(value or "").strip()


def valid_iso_date(value):
    """
    Accept these formats:
    YYYY-MM-DD
    DD-MM-YYYY
    DD/MM/YYYY
    YYYY/MM/DD

    Return a Python date object, or None if invalid.
    """
    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    formats = (
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
    )

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    return None


def parse_date(value, field_name, line_number):
    parsed = valid_iso_date(value)

    if parsed is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid {field_name} on CSV row {line_number}: "
                f"'{value}'. Accepted formats: YYYY-MM-DD or DD-MM-YYYY."
            ),
        )

    # Store all dates consistently in SQLite as YYYY-MM-DD.
    return parsed.isoformat()


def validate_database(connection):
    required_tables = {
        "transactions",
        "settlement_history",
        "settlement_import",
    }

    existing_tables = {
        row["name"]
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()
    }

    missing = required_tables - existing_tables

    if missing:
        raise HTTPException(
            status_code=500,
            detail=(
                "Missing database tables: "
                + ", ".join(sorted(missing))
            ),
        )


# ============================================================
# TRANSACTION MATCHING
# ============================================================

def find_matching_transaction(connection, settlement):
    """
    First try lifecycle_id.
    If that does not identify a transaction, try:
    account_id + merchant_name + transaction_date.

    The fallback must identify exactly one transaction.
    """

    lifecycle_id = normalize_text(
        settlement.get("lifecycle_id")
    )

    if lifecycle_id:
        row = connection.execute(
            """
            SELECT *
            FROM transactions
            WHERE lifecycle_id = ?
            ORDER BY transaction_id
            LIMIT 1
            """,
            (lifecycle_id,),
        ).fetchone()

        if row:
            return dict(row)

    account_id = normalize_text(settlement.get("account_id"))
    merchant_name = normalize_text(settlement.get("merchant_name"))
    transaction_date = settlement["transaction_date"]

    if not account_id or not merchant_name or not transaction_date:
        return None

    candidates = connection.execute(
        """
        SELECT *
        FROM transactions
        WHERE account_id = ?
          AND LOWER(TRIM(merchant_name)) = LOWER(TRIM(?))
          AND transaction_date = ?
        ORDER BY transaction_id
        """,
        (account_id, merchant_name, transaction_date),
    ).fetchall()

    if len(candidates) == 1:
        return dict(candidates[0])

    return None


# ============================================================
# SETTLEMENT CALCULATION AND ISSUE DETECTION
# ============================================================

def calculate_transaction(connection, transaction):
    transaction = dict(transaction)
    transaction_id = transaction["transaction_id"]

    history = connection.execute(
        """
        SELECT *
        FROM settlement_history
        WHERE transaction_id = ?
        ORDER BY settlement_date, settlement_id
        """,
        (transaction_id,),
    ).fetchall()

    debit_total = Decimal("0.00")
    credit_total = Decimal("0.00")
    settlement_dates = []

    for item in history:
        amount = money(item["settlement_amount"])
        settlement_type = normalize_text(
            item["settlement_type"]
        ).upper()

        if settlement_type == "DEBIT":
            debit_total += amount
        elif settlement_type == "CREDIT":
            credit_total += amount

        parsed_date = valid_iso_date(item["settlement_date"])

        if parsed_date:
            settlement_dates.append(parsed_date)

    debit_total = debit_total.quantize(CENT)
    credit_total = credit_total.quantize(CENT)

    original_amount = money(transaction["transaction_amount"])

    # Credits reduce the net amount settled.
    net_amount = (debit_total - credit_total).quantize(CENT)
    displayed_amount = max(net_amount, Decimal("0.00"))

    transaction_status = normalize_text(
        transaction.get("status")
    ).upper()

    has_refund = credit_total > 0

    # Settlement status.
    if transaction_status in {"FAILED", "DECLINED"}:
        settlement_status = "NOT_APPLICABLE"
    elif not history:
        settlement_status = "PENDING"
    elif displayed_amount > original_amount:
        settlement_status = "OVER_SETTLED"
    elif has_refund and displayed_amount < original_amount:
        settlement_status = "REFUNDED"
    elif displayed_amount == original_amount:
        settlement_status = "FULLY_SETTLED"
    else:
        settlement_status = "PARTIAL"

    last_settlement_date = (
        max(settlement_dates).isoformat()
        if settlement_dates
        else None
    )

    # Issue detection is independent of settlement status.
    issues = []
    transaction_date = valid_iso_date(
        transaction.get("transaction_date")
    )

    if transaction_status not in {"FAILED", "DECLINED"}:

        if displayed_amount > original_amount:
            issues.append({
                "transaction_id": transaction_id,
                "merchant_name": transaction["merchant_name"],
                "severity": "CRITICAL",
                "transaction_amount": float(original_amount),
                "total_settled_amount": float(displayed_amount),
                "message": "Net settlement exceeds the transaction amount.",
            })

        elif (
            not history
            and transaction_date is not None
            and (date.today() - transaction_date).days > 7
        ):
            issues.append({
                "transaction_id": transaction_id,
                "merchant_name": transaction["merchant_name"],
                "severity": "CRITICAL",
                "transaction_amount": float(original_amount),
                "total_settled_amount": float(displayed_amount),
                "message": "No settlement received within 7 days.",
            })

        elif (
            history
            and displayed_amount < original_amount
            and not has_refund
        ):
            issues.append({
                "transaction_id": transaction_id,
                "merchant_name": transaction["merchant_name"],
                "severity": "WARNING",
                "transaction_amount": float(original_amount),
                "total_settled_amount": float(displayed_amount),
                "message": "Transaction is under-settled.",
            })

    # Persist the recalculated values.
    connection.execute(
        """
        UPDATE transactions
        SET total_settled_amount = ?,
            settlement_status = ?,
            last_settlement_date = ?
        WHERE transaction_id = ?
        """,
        (
            str(displayed_amount),
            settlement_status,
            last_settlement_date,
            transaction_id,
        ),
    )

    transaction["transaction_amount"] = float(original_amount)
    transaction["total_settled_amount"] = float(displayed_amount)
    transaction["settlement_status"] = settlement_status
    transaction["last_settlement_date"] = last_settlement_date
    transaction["debit_total"] = float(debit_total)
    transaction["credit_total"] = float(credit_total)
    transaction["settlement_count"] = len(history)
    transaction["issues"] = issues
    transaction["issue_flag"] = (
        "CRITICAL"
        if any(i["severity"] == "CRITICAL" for i in issues)
        else "WARNING"
        if any(i["severity"] == "WARNING" for i in issues)
        else "NONE"
    )

    return transaction


def refresh_all_transactions(connection):
    rows = connection.execute(
        """
        SELECT *
        FROM transactions
        ORDER BY transaction_id
        """
    ).fetchall()

    results = []

    for row in rows:
        results.append(
            calculate_transaction(connection, dict(row))
        )

    return results


# ============================================================
# CSV PARSING AND VALIDATION
# ============================================================

def parse_csv(contents):
    try:
        text_content = contents.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text_content))
    except (UnicodeDecodeError, csv.Error):
        raise HTTPException(
            status_code=400,
            detail="The CSV could not be read. Please use UTF-8 encoding.",
        )

    if not reader.fieldnames:
        raise HTTPException(
            status_code=400,
            detail="The CSV is empty or has no header row.",
        )

    # Normalize headers, including a possible UTF-8 BOM.
    headers = [
        normalize_text(header).lower()
        for header in reader.fieldnames
    ]

    if len(headers) != len(set(headers)):
        raise HTTPException(
            status_code=400,
            detail="The CSV contains duplicate column headers.",
        )

    reader.fieldnames = headers

    missing_columns = REQUIRED_CSV_COLUMNS - set(headers)

    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=(
                "Missing required CSV columns: "
                + ", ".join(sorted(missing_columns))
            ),
        )

    records = []
    seen_ids = set()

    for line_number, raw_row in enumerate(reader, start=2):
        if None in raw_row:
            raise HTTPException(
                status_code=400,
                detail=f"CSV row {line_number} has too many columns.",
            )

        row = {
            normalize_text(key).lower(): normalize_text(value)
            for key, value in raw_row.items()
            if key is not None
        }

        if not any(row.values()):
            continue

        settlement_id = row.get("settlement_id", "")

        if not settlement_id:
            raise HTTPException(
                status_code=400,
                detail=f"Settlement ID is missing on CSV row {line_number}.",
            )

        if settlement_id in seen_ids:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Duplicate settlement ID '{settlement_id}' "
                    f"inside the CSV (row {line_number})."
                ),
            )

        seen_ids.add(settlement_id)

        required_values = [
            "account_id",
            "merchant_name",
            "transaction_date",
            "settlement_date",
            "settlement_amount",
            "settlement_type",
            "currency",
        ]

        missing_values = [
            field for field in required_values if not row.get(field)
        ]

        if missing_values:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Missing values on CSV row {line_number}: "
                    + ", ".join(missing_values)
                ),
            )

        row["settlement_type"] = row["settlement_type"].upper()
        row["currency"] = row["currency"].upper()
        row["lifecycle_id"] = row.get("lifecycle_id") or ""

        if row["settlement_type"] not in ALLOWED_SETTLEMENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid settlement type on CSV row {line_number}. "
                    "Use DEBIT or CREDIT."
                ),
            )

        if len(row["currency"]) != 3:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid currency on CSV row {line_number}.",
            )

        try:
            amount = Decimal(row["settlement_amount"])

            if not amount.is_finite() or amount <= 0:
                raise InvalidOperation

            row["settlement_amount"] = str(
                amount.quantize(CENT, rounding=ROUND_HALF_UP)
            )

        except (InvalidOperation, ValueError):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid settlement amount on CSV row {line_number}. "
                    "Enter a positive numeric amount."
                ),
            )

        row["transaction_date"] = parse_date(
            row["transaction_date"],
            "transaction date",
            line_number,
        )

        row["settlement_date"] = parse_date(
            row["settlement_date"],
            "settlement date",
            line_number,
        )

        if (
            valid_iso_date(row["settlement_date"])
            < valid_iso_date(row["transaction_date"])
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Settlement date precedes transaction date "
                    f"on CSV row {line_number}."
                ),
            )

        row["_line_number"] = line_number
        records.append(row)

    if not records:
        raise HTTPException(
            status_code=400,
            detail="The CSV contains no settlement records.",
        )

    return records


# ============================================================
# BASIC ENDPOINTS
# ============================================================

@app.get("/")
def home():
    return {
        "message": "Transaction Reconciliation API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "database_path": str(DATABASE_PATH),
        "database_exists": DATABASE_PATH.exists(),
    }


@app.get("/database/tables")
def get_tables():
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

    return {"tables": [row["name"] for row in rows]}


# ============================================================
# POST /reconcile
# ============================================================

@app.post("/reconcile")
async def reconcile_csv(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a CSV file.",
        )

    contents = await file.read()

    if not contents:
        raise HTTPException(
            status_code=400,
            detail="The uploaded CSV file is empty.",
        )

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File size must not exceed 10 MB.",
        )

    records = parse_csv(contents)

    matched = []
    unmatched = []
    skipped_duplicates = []

    try:
        with get_connection() as connection:
            validate_database(connection)

            existing_ids = {
                row["settlement_id"]
                for row in connection.execute(
                    "SELECT settlement_id FROM settlement_history"
                ).fetchall()
            }

            # Process each row independently, but commit the upload together.
            for settlement in records:
                settlement_id = settlement["settlement_id"]

                if settlement_id in existing_ids:
                    skipped_duplicates.append(settlement_id)
                    continue

                transaction = find_matching_transaction(
                    connection,
                    settlement,
                )

                if transaction is None:
                    unmatched.append({
                        "settlement_id": settlement_id,
                        "reason": (
                            "No matching transaction found. Check lifecycle "
                            "ID or account, merchant and transaction date."
                        ),
                    })
                    continue

                transaction_status = normalize_text(
                    transaction["status"]
                ).upper()

                if transaction_status in {"FAILED", "DECLINED"}:
                    unmatched.append({
                        "settlement_id": settlement_id,
                        "reason": (
                            f"Transaction is {transaction_status}."
                        ),
                    })
                    continue

                if (
                    normalize_text(transaction["currency"]).upper()
                    != settlement["currency"]
                ):
                    unmatched.append({
                        "settlement_id": settlement_id,
                        "reason": "Settlement currency does not match transaction currency.",
                    })
                    continue

                connection.execute(
                    """
                    INSERT INTO settlement_history (
                        settlement_id,
                        transaction_id,
                        lifecycle_id,
                        settlement_date,
                        settlement_amount,
                        settlement_type,
                        currency
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        settlement_id,
                        transaction["transaction_id"],
                        settlement["lifecycle_id"] or None,
                        settlement["settlement_date"],
                        settlement["settlement_amount"],
                        settlement["settlement_type"],
                        settlement["currency"],
                    ),
                )

                existing_ids.add(settlement_id)

                matched.append({
                    "settlement_id": settlement_id,
                    "transaction_id": transaction["transaction_id"],
                })

            # Store the uploaded CSV in the staging table.
            connection.execute("DELETE FROM settlement_import")

            for settlement in records:
                connection.execute(
                    """
                    INSERT INTO settlement_import (
                        settlement_id,
                        lifecycle_id,
                        account_id,
                        merchant_name,
                        transaction_date,
                        settlement_date,
                        settlement_amount,
                        settlement_type,
                        currency
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        settlement["settlement_id"],
                        settlement["lifecycle_id"] or None,
                        settlement["account_id"],
                        settlement["merchant_name"],
                        settlement["transaction_date"],
                        settlement["settlement_date"],
                        settlement["settlement_amount"],
                        settlement["settlement_type"],
                        settlement["currency"],
                    ),
                )

            transaction_results = refresh_all_transactions(connection)

            issues = [
                issue
                for result in transaction_results
                for issue in result["issues"]
            ]

    except HTTPException:
        raise
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Database integrity error: {exc}",
        )
    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {exc}",
        )

    return {
        "message": "Reconciliation completed.",
        "filename": file.filename,
        "rows_received": len(records),
        "matched_count": len(matched),
        "unmatched_count": len(unmatched),
        "duplicate_count": len(skipped_duplicates),
        "matched": matched,
        "unmatched": unmatched,
        "skipped_duplicates": skipped_duplicates,
        "issues": issues,
    }


# ============================================================
# GET /transactions
# ============================================================

@app.get("/transactions")
def get_transactions():
    try:
        with get_connection() as connection:
            validate_database(connection)
            transactions = refresh_all_transactions(connection)

        return {
            "count": len(transactions),
            "transactions": transactions,
        }

    except HTTPException:
        raise
    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {exc}",
        )


# ============================================================
# GET /transactions/{transaction_id}
# ============================================================

@app.get("/transactions/{transaction_id}")
def get_transaction_details(transaction_id: str):
    try:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM transactions
                WHERE transaction_id = ?
                """,
                (transaction_id,),
            ).fetchone()

            if row is None:
                raise HTTPException(
                    status_code=404,
                    detail="Transaction not found.",
                )

            transaction = calculate_transaction(
                connection,
                dict(row),
            )

            history = connection.execute(
                """
                SELECT *
                FROM settlement_history
                WHERE transaction_id = ?
                ORDER BY settlement_date, settlement_id
                """,
                (transaction_id,),
            ).fetchall()

            transaction["settlement_history"] = [
                dict(item) for item in history
            ]

        return transaction

    except HTTPException:
        raise
    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {exc}",
        )


# ============================================================
# GET /issues
# ============================================================

@app.get("/issues")
def get_issues(severity: str = "ALL"):
    severity = severity.strip().upper()

    if severity not in {"ALL", "CRITICAL", "WARNING"}:
        raise HTTPException(
            status_code=400,
            detail="Severity must be ALL, CRITICAL or WARNING.",
        )

    try:
        with get_connection() as connection:
            transactions = refresh_all_transactions(connection)

        issues = [
            issue
            for transaction in transactions
            for issue in transaction["issues"]
            if severity == "ALL" or issue["severity"] == severity
        ]

        return {
            "count": len(issues),
            "issues": issues,
        }

    except HTTPException:
        raise
    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {exc}",
        )


# ============================================================
# GET /dashboard/summary
# ============================================================

@app.get("/dashboard/summary")
def dashboard_summary():
    try:
        with get_connection() as connection:
            transactions = refresh_all_transactions(connection)

            total_settlements = connection.execute(
                "SELECT COUNT(*) FROM settlement_history"
            ).fetchone()[0]

        status_breakdown = {
            "PENDING": 0,
            "PARTIAL": 0,
            "FULLY_SETTLED": 0,
            "OVER_SETTLED": 0,
            "REFUNDED": 0,
            "NOT_APPLICABLE": 0,
        }

        critical_issues = 0
        warnings = 0
        outstanding_amount = Decimal("0.00")
        days_to_settle = []
        fully_settled_count = 0

        for transaction in transactions:
            status = transaction["settlement_status"]
            status_breakdown[status] = status_breakdown.get(status, 0) + 1

            for issue in transaction["issues"]:
                if issue["severity"] == "CRITICAL":
                    critical_issues += 1
                elif issue["severity"] == "WARNING":
                    warnings += 1

            original_amount = money(transaction["transaction_amount"])
            settled_amount = money(transaction["total_settled_amount"])

            if status not in {"NOT_APPLICABLE", "OVER_SETTLED"}:
                outstanding_amount += max(
                    original_amount - settled_amount,
                    Decimal("0.00"),
                )

            if status == "FULLY_SETTLED":
                fully_settled_count += 1

            if status in {"FULLY_SETTLED", "REFUNDED"}:
                start_date = valid_iso_date(
                    transaction["transaction_date"]
                )
                end_date = valid_iso_date(
                    transaction["last_settlement_date"]
                )

                if start_date and end_date:
                    days_to_settle.append(
                        max((end_date - start_date).days, 0)
                    )

        applicable_count = sum(
            1
            for transaction in transactions
            if transaction["settlement_status"] != "NOT_APPLICABLE"
        )

        settlement_rate = (
            round(fully_settled_count / applicable_count * 100, 2)
            if applicable_count
            else 0
        )

        average_days = (
            round(sum(days_to_settle) / len(days_to_settle), 2)
            if days_to_settle
            else None
        )

        return {
            "total_transactions": len(transactions),
            "total_settlements": total_settlements,
            "critical_issues": critical_issues,
            "warnings": warnings,
            "total_outstanding_amount": f"{outstanding_amount:.2f}",
            "settlement_rate_percent": settlement_rate,
            "average_days_to_settle": average_days,
            "status_breakdown": status_breakdown,
        }

    except HTTPException:
        raise
    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {exc}",
        )
