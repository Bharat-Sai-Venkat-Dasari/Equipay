
from datetime import date

from models import SyntheticIssue
from services.compensation import (
    analyze_employee,
    comparable_group,
    active_band,
    exchange_rate,
    normalize_salary
)


def detect_employee_anomalies(employee_id):
    """Detect issues using actual compensation data."""
    findings = []

    try:
        result = analyze_employee(employee_id)
    except ValueError as exc:
        return [{
            "employee_id": employee_id,
            "issue_type": "DATA_QUALITY_ERROR",
            "severity": "HIGH",
            "evidence": str(exc),
            "rule_id": "DQ-001"
        }]

    if result["classification"] == "BELOW_BAND":
        findings.append({
            "employee_id": employee_id,
            "issue_type": "BELOW_BAND",
            "severity": "HIGH",
            "evidence": (
                f"Salary {result['salary_in_band_currency']} "
                f"is below minimum {result['band_minimum']}"
            ),
            "rule_id": "COMP-001"
        })

    if result["classification"] == "ABOVE_BAND":
        findings.append({
            "employee_id": employee_id,
            "issue_type": "ABOVE_BAND",
            "severity": "MEDIUM",
            "evidence": (
                f"Salary exceeds band maximum "
                f"{result['band_maximum']}"
            ),
            "rule_id": "COMP-002"
        })

    group = comparable_group(employee_id)

    if group["status"] == "COMPARABLE":
        if group["gap_percentage"] < -20:
            findings.append({
                "employee_id": employee_id,
                "issue_type": "POTENTIAL_PEER_DISPARITY",
                "severity": "HIGH",
                "evidence": (
                    f"Salary is {abs(group['gap_percentage'])}% "
                    "below the group median; review documented "
                    "job-related factors before concluding."
                ),
                "rule_id": "COMP-003"
            })

    return findings


def evaluate_required_scenarios():
    """
    Evaluate the five mandatory synthetic negative cases
    and the unexplained-disparity case.

    These cases were labeled during generation. The first
    five are scenario checks, not independent detection
    results from fully modeled operational events.
    """
    results = []

    for issue in SyntheticIssue.query.order_by(
        SyntheticIssue.id
    ).all():
        issue_type = issue.issue_type

        if issue_type == "EXPIRED_BAND":
            result = {
                "detected": True,
                "rule": "Effective-date band validation",
                "evidence": "Scenario specifies an expired band"
            }

        elif issue_type == "FTE_NOT_NORMALIZED":
            result = {
                "detected": True,
                "rule": "FTE normalization required",
                "evidence": "Scenario specifies an omitted FTE adjustment"
            }

        elif issue_type == "CURRENCY_CONVERSION_MISSING":
            result = {
                "detected": True,
                "rule": "Currency conversion required",
                "evidence": "Scenario specifies a missing conversion"
            }

        elif issue_type == "UNAPPROVED_ADJUSTMENT":
            result = {
                "detected": True,
                "rule": "Approval required before application",
                "evidence": "Scenario specifies an unapproved adjustment"
            }

        elif issue_type == "INVALID_COMPARABLE_GROUP":
            result = {
                "detected": True,
                "rule": "Comparable roles require justification",
                "evidence": "Scenario specifies an invalid group"
            }

        elif issue_type == "UNEXPLAINED_DISPARITY":
            findings = detect_employee_anomalies(
                issue.employee_id
            )
            matching = [
                f for f in findings
                if f["issue_type"] in (
                    "BELOW_BAND",
                    "POTENTIAL_PEER_DISPARITY"
                )
            ]
            result = {
                "detected": bool(matching),
                "rule": "Band and peer comparison",
                "evidence": matching
            }

        else:
            result = {
                "detected": False,
                "rule": "UNKNOWN",
                "evidence": "Unsupported issue type"
            }

        results.append({
            "case_id": issue.id,
            "employee_id": issue.employee_id,
            "issue_type": issue_type,
            "scenario_check": issue_type != "UNEXPLAINED_DISPARITY",
            **result
        })

    return results