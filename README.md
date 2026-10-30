# EquiPay — Compensation Equity Audit

## Project Overview

EquiPay is a Flask-based compensation audit application developed to compare employee salaries across roles, levels, locations, and documented job-related factors.

The application identifies potential compensation disparities, supports salary adjustment proposals, records manager and HR approval decisions, and maintains an audit history.

## Technology Stack

- Backend: Python, Flask, Flask-SQLAlchemy
- Database: SQLite
- Frontend: HTML, CSS, Bootstrap, JavaScript
- Testing: Pytest

## Key Features

1. Synthetic employee and compensation dataset generation.
2. Role, level, location, and effective-dated compensation bands.
3. Salary history tracking.
4. Currency and full-time-equivalent salary normalization.
5. Compa-ratio and within-band position calculations.
6. Comparable employee group analysis.
7. Rule-based compensation anomaly detection.
8. Salary adjustment proposals with manager and HR approval steps.
9. Append-only salary adjustment records and audit events through the application workflow.
10. Synthetic scenario checks and evaluation reporting.

## Dataset Generation

The project includes a synthetic dataset generator:

generator/generate_data.py

To generate the dataset, run:

```powershell
python -m generator.generate_data

## Evaluation Results

The evaluation identified all 10 labeled synthetic disparity cases.

- True positives: 10
- False negatives: 0
- Recall on labeled disparity cases: 100%

The other 50 cases are scenario-label checks rather than independent operational detections. Precision, accuracy, and false-positive rate have not been established.

## Installation

Create a virtual environment:

```powershell
python -m venv venv
```

Activate it on Windows:

```powershell
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Start the application:

```powershell
python app.py
```

Open the dashboard at:

`http://127.0.0.1:5000`

The application requires the project database to be populated using its dataset-generation scripts before the full dashboard and audit workflows can be demonstrated.

## Testing

Run the existing compensation calculation tests:

```powershell
python -m pytest tests/test_project.py -v
```

Current result: 6 tests passed.

## API Endpoints

| Endpoint | Purpose |
|---|---|
| `/api/health` | Application health |
| `/api/summary` | Dataset summary |
| `/api/employees` | Employee directory |
| `/api/compensation/<employee_id>` | Compensation analysis |
| `/api/comparable/<employee_id>` | Comparable employees |
| `/api/anomalies/<employee_id>` | Anomaly detection |
| `/api/scenarios` | Synthetic scenario checks |
| `/api/evaluation` | Evaluation metrics |
| `/api/proposals` | Salary adjustment proposals |

Additional proposal endpoints support review and application of approved salary adjustments.

## Current Limitations

EquiPay is an assessment prototype, not a production HR platform.

- The approval workflow does not yet authenticate reviewers or enforce user roles.
- Database-level immutability protections are not implemented.
- Five synthetic negative-scenario categories are label-based checks.
- Evaluation metrics are limited to labeled disparity cases.
- Compensation findings require human review and consideration of documented job-related factors.

## Project Purpose

Developed as a technical assessment prototype for the Yotta AI Round 3 compensation equity audit problem statement.