# Assumptions and Business Rules

## 1. Overview

This document describes the assumptions and business rules used by the Transaction Reconciliation System to process settlement CSV files and compare settlement records with existing transactions.

## 2. Input Data Assumptions

- Original transaction records are stored in the SQLite database before reconciliation begins.
- Settlement records are provided through a CSV file.
- The CSV file must contain the required settlement columns.
- Transaction and settlement dates must use a supported date format.
- Settlement amounts must be valid numeric values.
- Settlement types must be either `DEBIT` or `CREDIT`.
- Currency values are expected to be consistent when comparing transaction and settlement amounts.

## 3. Transaction Matching Rules

### Primary Matching

The system first attempts to match a settlement record using its `lifecycle_id`.

### Fallback Matching

If a settlement record does not contain a lifecycle ID, the system uses the following fields for matching:

- Account ID
- Merchant name
- Transaction date

### Unmatched Records

A settlement record that cannot be matched to an existing transaction is reported as unmatched. It should not be assigned to an unrelated transaction.

## 4. Duplicate Handling

Settlement IDs are used to identify duplicate settlement records.

A settlement record that has already been processed should not be added to settlement history again. Re-uploading the same CSV file should therefore avoid duplicating previously processed settlements.

## 5. Settlement Calculation

The system calculates the net settled amount as follows:

Net settled amount = Total debit amount − Total credit amount

For example, if a transaction has a debit settlement of USD 100 and a credit settlement of USD 20, the net settled amount is USD 80.

The net amount is compared with the original transaction amount to determine the settlement status.

## 6. Settlement Status Rules

The application distinguishes between the following settlement statuses:

`PENDING` = No settlement records have been processed
`PARTIAL` = The net settled amount is less than the original transaction amount
`FULLY_SETTLED`= The net settled amount equals the original transaction amount
`OVER_SETTLED`= The net settled amount exceeds the original transaction amount
`REFUNDED`= A credit or refund has resulted in a net amount below the original transaction amount
`NOT_APPLICABLE`= Settlement is not applicable to a failed or declined transaction

When a credit reduces the net settled amount below the original amount, the exact classification depends on the application's implemented business rules.

## 7. Reconciliation Issues

The system identifies settlement discrepancies that may require investigation.

Examples include:

- Settlement amounts exceeding the original transaction amount.
- Transactions remaining unsettled beyond the configured time threshold.
- Transactions with a settlement shortfall and no corresponding credit entry.
- Settlement records that cannot be matched to an original transaction.

Issue severity and classification depend on the implemented reconciliation rules.

## 8. Date and Currency Assumptions

- Dates must be parsed successfully before a settlement record can be processed.
- Transaction and settlement dates serve different purposes: transaction dates help identify the original transaction, while settlement dates indicate when settlement activity occurred.
- Settlement amounts are compared only when the currencies are compatible.
- The system uses the configured settlement rules to identify overdue transactions.

## 9. Data Integrity

- Transaction IDs uniquely identify original transactions.
- Settlement IDs uniquely identify settlement history records.
- Settlement history references original transactions through the transaction ID.
- Invalid or unmatched records should be reported rather than silently associated with incorrect transactions.

## 10. Scope

This application is intended to demonstrate transaction and settlement reconciliation using CSV input, local database records, automated matching, settlement calculations, and issue reporting.

Its behavior is limited to the data fields and business rules implemented in the current application.
