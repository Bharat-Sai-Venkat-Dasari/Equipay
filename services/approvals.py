
import json
from datetime import date, datetime, timezone

from sqlalchemy import func

from models import (
    db, Employee, SalaryRecord,
    AdjustmentProposal, ProposalApproval, AuditEvent
)
from services.compensation import analyze_employee


def now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def next_id(model, prefix):
    """
    Local demo ID generator.
    IDs are assigned sequentially from persisted records.
    """
    count = db.session.query(func.count()).select_from(model).scalar()
    return f"{prefix}-{count + 1:06d}"


def add_event(proposal_id, event_type, actor, details):
    event = AuditEvent(
        id=next_id(AuditEvent, "AUD"),
        proposal_id=proposal_id,
        event_type=event_type,
        actor=actor,
        details_json=json.dumps(details, sort_keys=True),
        created_at=now_utc()
    )
    db.session.add(event)
    db.session.flush()
    return event


def decisions_for(proposal_id):
    return (
        ProposalApproval.query
        .filter_by(proposal_id=proposal_id)
        .order_by(
            ProposalApproval.decided_at,
            ProposalApproval.id
        )
        .all()
    )


def events_for(proposal_id):
    return (
        AuditEvent.query
        .filter_by(proposal_id=proposal_id)
        .order_by(
            AuditEvent.created_at,
            AuditEvent.id
        )
        .all()
    )


def proposal_status(proposal_id):
    decisions = decisions_for(proposal_id)

    if any(d.decision == "REJECTED" for d in decisions):
        return "REJECTED"

    approved_roles = {
        d.reviewer_role
        for d in decisions
        if d.decision == "APPROVED"
    }

    if {"MANAGER", "HR"}.issubset(approved_roles):
        applied = any(
            e.event_type == "ADJUSTMENT_APPLIED"
            for e in events_for(proposal_id)
        )
        return "APPLIED" if applied else "APPROVED"

    if "MANAGER" in approved_roles:
        return "PENDING_HR"

    return "PENDING_MANAGER"


def serialize_proposal(proposal):
    decisions = decisions_for(proposal.id)
    events = events_for(proposal.id)

    return {
        "id": proposal.id,
        "employee_id": proposal.employee_id,
        "proposed_salary": proposal.proposed_salary,
        "currency": proposal.currency,
        "justification": proposal.justification,
        "evidence": json.loads(proposal.evidence_json),
        "created_by": proposal.created_by,
        "created_at": proposal.created_at.isoformat(),
        "status": proposal_status(proposal.id),
        "approvals": [
            {
                "id": d.id,
                "reviewer_role": d.reviewer_role,
                "reviewer_name": d.reviewer_name,
                "decision": d.decision,
                "reason": d.reason,
                "decided_at": d.decided_at.isoformat()
            }
            for d in decisions
        ],
        "audit_events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "actor": e.actor,
                "details": json.loads(e.details_json),
                "created_at": e.created_at.isoformat()
            }
            for e in events
        ]
    }


def create_proposal(employee_id, proposed_salary,
                    justification, created_by):
    employee = db.session.get(Employee, employee_id)

    if employee is None:
        raise ValueError("Employee not found")

    if proposed_salary <= 0:
        raise ValueError("Proposed salary must be positive")

    if not justification.strip():
        raise ValueError("Justification is required")

    if not created_by.strip():
        raise ValueError("Creator name is required")

    analysis = analyze_employee(employee_id)

    latest = (
        SalaryRecord.query
        .filter_by(employee_id=employee_id)
        .order_by(
            SalaryRecord.effective_date.desc(),
            SalaryRecord.id.desc()
        )
        .first()
    )

    if latest is None:
        raise ValueError("Employee has no salary history")

    if proposed_salary <= float(latest.salary_amount):
        raise ValueError(
            "Proposed salary must exceed the current salary"
        )

    # Avoid multiple simultaneously active proposals.
    existing = AdjustmentProposal.query.filter_by(
        employee_id=employee_id
    ).all()

    for proposal in existing:
        if proposal_status(proposal.id) not in (
            "REJECTED", "APPLIED"
        ):
            raise ValueError(
                "Employee already has an active proposal"
            )

    proposal = AdjustmentProposal(
        id=next_id(AdjustmentProposal, "ADJ"),
        employee_id=employee_id,
        proposed_salary=round(proposed_salary, 2),
        currency=latest.currency,
        justification=justification.strip(),
        evidence_json=json.dumps(
            {
                "source_salary_id": latest.id,
                "current_salary": latest.salary_amount,
                "compa_ratio": analysis["compa_ratio"],
                "band_position": analysis["band_position"],
                "band_id": analysis["band_id"],
                "analysis_date": analysis["salary_date"]
            },
            sort_keys=True
        ),
        created_by=created_by.strip(),
        created_at=now_utc()
    )

    db.session.add(proposal)
    db.session.flush()

    add_event(
        proposal.id,
        "PROPOSAL_CREATED",
        created_by.strip(),
        {
            "employee_id": employee_id,
            "proposed_salary": proposal.proposed_salary,
            "currency": proposal.currency,
            "justification": proposal.justification
        }
    )

    db.session.commit()
    return serialize_proposal(proposal)


def review_proposal(proposal_id, reviewer_role,
                    reviewer_name, decision, reason):
    proposal = db.session.get(
        AdjustmentProposal, proposal_id
    )

    if proposal is None:
        raise ValueError("Proposal not found")

    reviewer_role = reviewer_role.upper().strip()
    decision = decision.upper().strip()

    if reviewer_role not in ("MANAGER", "HR"):
        raise ValueError("Reviewer must be MANAGER or HR")

    if decision not in ("APPROVED", "REJECTED"):
        raise ValueError("Decision must be APPROVED or REJECTED")

    if not reviewer_name.strip() or not reason.strip():
        raise ValueError(
            "Reviewer name and decision reason are required"
        )

    status = proposal_status(proposal_id)

    if reviewer_role == "MANAGER":
        if status != "PENDING_MANAGER":
            raise ValueError(
                "Proposal is not awaiting manager review"
            )

    if reviewer_role == "HR":
        if status != "PENDING_HR":
            raise ValueError(
                "Manager approval is required before HR review"
            )

    approval = ProposalApproval(
        id=next_id(ProposalApproval, "APR"),
        proposal_id=proposal_id,
        reviewer_role=reviewer_role,
        reviewer_name=reviewer_name.strip(),
        decision=decision,
        reason=reason.strip(),
        decided_at=now_utc()
    )

    db.session.add(approval)
    db.session.flush()

    add_event(
        proposal_id,
        "PROPOSAL_REVIEWED",
        reviewer_name.strip(),
        {
            "reviewer_role": reviewer_role,
            "decision": decision,
            "reason": reason.strip()
        }
    )

    db.session.commit()
    return serialize_proposal(proposal)


def apply_proposal(proposal_id, actor):
    proposal = db.session.get(
        AdjustmentProposal, proposal_id
    )

    if proposal is None:
        raise ValueError("Proposal not found")

    if proposal_status(proposal_id) != "APPROVED":
        raise ValueError(
            "Both manager and HR approval are required"
        )

    if not actor.strip():
        raise ValueError("Actor name is required")

    latest = (
        SalaryRecord.query
        .filter_by(employee_id=proposal.employee_id)
        .order_by(
            SalaryRecord.effective_date.desc(),
            SalaryRecord.id.desc()
        )
        .first()
    )

    evidence = json.loads(proposal.evidence_json)

    if latest.id != evidence["source_salary_id"]:
        raise ValueError(
            "Salary history changed after proposal creation; "
            "reassessment is required"
        )

    if latest.currency != proposal.currency:
        raise ValueError("Currency mismatch")

    # Append a new salary event; never modify the old salary.
    salary_id = f"SAL-ADJ-{proposal.id}"

    if db.session.get(SalaryRecord, salary_id):
        raise ValueError("Adjustment already applied")

    new_salary = SalaryRecord(
        id=salary_id,
        employee_id=proposal.employee_id,
        effective_date=date.today(),
        salary_amount=proposal.proposed_salary,
        currency=proposal.currency,
        fte=latest.fte,
        change_reason="APPROVED_ADJUSTMENT"
    )

    db.session.add(new_salary)
    db.session.flush()

    add_event(
        proposal_id,
        "ADJUSTMENT_APPLIED",
        actor.strip(),
        {
            "previous_salary_id": latest.id,
            "new_salary_id": salary_id,
            "previous_salary": latest.salary_amount,
            "new_salary": proposal.proposed_salary,
            "effective_date": date.today().isoformat()
        }
    )

    db.session.commit()
    return serialize_proposal(proposal)