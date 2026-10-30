
from collections import Counter

from models import SyntheticIssue
from services.anomalies import detect_employee_anomalies


def evaluate_detection():
    """
    Evaluate independent compensation findings against
    synthetic ground-truth labels.

    Only UNEXPLAINED_DISPARITY is independently evaluated.
    Other synthetic scenarios are excluded because their
    operational events are not fully modeled.
    """

    issues = SyntheticIssue.query.all()

    scenario_counts = Counter(
        issue.issue_type for issue in issues
    )

    evaluated_cases = []
    true_positives = 0
    false_negatives = 0

    for issue in issues:
        if issue.issue_type != "UNEXPLAINED_DISPARITY":
            continue

        findings = detect_employee_anomalies(
            issue.employee_id
        )

        matching_findings = [
            finding for finding in findings
            if finding["issue_type"] in (
                "BELOW_BAND",
                "POTENTIAL_PEER_DISPARITY"
            )
        ]

        detected = bool(matching_findings)

        if detected:
            true_positives += 1
        else:
            false_negatives += 1

        evaluated_cases.append({
            "case_id": issue.id,
            "employee_id": issue.employee_id,
            "ground_truth": "UNEXPLAINED_DISPARITY",
            "detected": detected,
            "findings": matching_findings
        })

    total_positive_cases = (
        true_positives + false_negatives
    )

    recall = (
        true_positives / total_positive_cases
        if total_positive_cases else None
    )

    return {
        "evaluation_name": "EquiPay Detection Evaluation",
        "total_ground_truth_cases": len(issues),
        "scenario_distribution": dict(scenario_counts),
        "independently_evaluated_cases": total_positive_cases,
        "scenario_label_only_cases": (
            len(issues) - total_positive_cases
        ),
        "true_positives": true_positives,
        "false_negatives": false_negatives,
        "recall": (
            round(recall, 4)
            if recall is not None else None
        ),
        "precision": None,
        "false_positive_rate": None,
        "accuracy": None,
        "metric_limitations": (
            "Recall is measured only for labeled "
            "UNEXPLAINED_DISPARITY cases. Precision, "
            "accuracy and false-positive rate are not "
            "reported because a verified negative "
            "evaluation set has not been established."
        ),
        "cases": evaluated_cases
    }
