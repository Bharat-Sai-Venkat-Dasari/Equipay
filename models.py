
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    family = db.Column(db.String(100), nullable=False)


class Level(db.Model):
    __tablename__ = "levels"

    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    rank = db.Column(db.Integer, nullable=False)


class Location(db.Model):
    __tablename__ = "locations"

    id = db.Column(db.String(20), primary_key=True)
    city = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    currency = db.Column(db.String(3), nullable=False)


class Employee(db.Model):
    __tablename__ = "employees"

    id = db.Column(db.String(20), primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    email = db.Column(
        db.String(150), unique=True, nullable=False
    )

    role_id = db.Column(
        db.String(20),
        db.ForeignKey("roles.id"),
        nullable=False
    )

    level_id = db.Column(
        db.String(20),
        db.ForeignKey("levels.id"),
        nullable=False
    )

    location_id = db.Column(
        db.String(20),
        db.ForeignKey("locations.id"),
        nullable=False
    )

    hire_date = db.Column(db.Date, nullable=False)

    fte = db.Column(db.Float, default=1.0)

    role = db.relationship("Role")
    level = db.relationship("Level")
    location = db.relationship("Location")


class CompensationBand(db.Model):
    __tablename__ = "compensation_bands"

    id = db.Column(db.String(100), primary_key=True)

    role_id = db.Column(
        db.String(20),
        db.ForeignKey("roles.id"),
        nullable=False
    )

    level_id = db.Column(
        db.String(20),
        db.ForeignKey("levels.id"),
        nullable=False
    )

    location_id = db.Column(
        db.String(20),
        db.ForeignKey("locations.id"),
        nullable=False
    )

    minimum = db.Column(db.Float, nullable=False)
    midpoint = db.Column(db.Float, nullable=False)
    maximum = db.Column(db.Float, nullable=False)

    effective_from = db.Column(db.Date, nullable=False)
    effective_to = db.Column(db.Date)

    __table_args__ = (
        db.CheckConstraint(
            "minimum < midpoint AND midpoint < maximum",
            name="valid_band_values"
        ),
    )

class SalaryRecord(db.Model):
    __tablename__ = "salary_records"

    id = db.Column(db.String(100), primary_key=True)
    employee_id = db.Column(
        db.String(20),
        db.ForeignKey("employees.id"),
        nullable=False
    )
    effective_date = db.Column(db.Date, nullable=False)
    salary_amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    fte = db.Column(db.Float, nullable=False)
    change_reason = db.Column(db.String(50), nullable=False)

    __table_args__ = (
        db.CheckConstraint("salary_amount >= 0"),
        db.CheckConstraint("fte > 0 AND fte <= 1"),
    )


class PerformanceEvidence(db.Model):
    __tablename__ = "performance_evidence"

    id = db.Column(db.String(50), primary_key=True)
    employee_id = db.Column(
        db.String(20),
        db.ForeignKey("employees.id"),
        nullable=False
    )
    review_year = db.Column(db.Integer, nullable=False)
    rating = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)

    __table_args__ = (
        db.CheckConstraint("rating >= 1 AND rating <= 5"),
    )


class Tenure(db.Model):
    __tablename__ = "tenure"

    id = db.Column(db.String(50), primary_key=True)
    employee_id = db.Column(
        db.String(20),
        db.ForeignKey("employees.id"),
        nullable=False
    )
    as_of_date = db.Column(db.Date, nullable=False)
    months = db.Column(db.Integer, nullable=False)


class Promotion(db.Model):
    __tablename__ = "promotions"

    id = db.Column(db.String(50), primary_key=True)
    employee_id = db.Column(
        db.String(20),
        db.ForeignKey("employees.id"),
        nullable=False
    )
    previous_level_id = db.Column(
        db.String(20), db.ForeignKey("levels.id"),
        nullable=False
    )
    new_level_id = db.Column(
        db.String(20), db.ForeignKey("levels.id"),
        nullable=False
    )
    effective_date = db.Column(db.Date, nullable=False)


class FTEHistory(db.Model):
    __tablename__ = "fte_history"

    id = db.Column(db.String(50), primary_key=True)
    employee_id = db.Column(
        db.String(20),
        db.ForeignKey("employees.id"),
        nullable=False
    )
    effective_date = db.Column(db.Date, nullable=False)
    fte = db.Column(db.Float, nullable=False)


class ExchangeRate(db.Model):
    __tablename__ = "exchange_rates"

    id = db.Column(db.String(50), primary_key=True)
    from_currency = db.Column(db.String(3), nullable=False)
    to_currency = db.Column(db.String(3), nullable=False)
    rate = db.Column(db.Float, nullable=False)
    effective_date = db.Column(db.Date, nullable=False)

    __table_args__ = (
        db.CheckConstraint("rate > 0"),
    )


class SyntheticIssue(db.Model):
    __tablename__ = "synthetic_issues"

    id = db.Column(db.String(50), primary_key=True)
    employee_id = db.Column(
        db.String(20),
        db.ForeignKey("employees.id"),
        nullable=False
    )
    salary_id = db.Column(
        db.String(100),
        db.ForeignKey("salary_records.id"),
        nullable=False
    )
    issue_type = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=False)
    expected_decision = db.Column(db.String(50), nullable=False)


class AdjustmentProposal(db.Model):
    __tablename__ = "adjustment_proposals"

    id = db.Column(db.String(50), primary_key=True)

    employee_id = db.Column(
        db.String(20),
        db.ForeignKey("employees.id"),
        nullable=False
    )

    proposed_salary = db.Column(
        db.Float, nullable=False
    )

    currency = db.Column(
        db.String(3), nullable=False
    )

    justification = db.Column(
        db.Text, nullable=False
    )

    evidence_json = db.Column(
        db.Text, nullable=False
    )

    created_by = db.Column(
        db.String(100), nullable=False
    )

    created_at = db.Column(
        db.DateTime, nullable=False
    )

    __table_args__ = (
        db.CheckConstraint(
            "proposed_salary > 0",
            name="positive_proposed_salary"
        ),
    )


class ProposalApproval(db.Model):
    __tablename__ = "proposal_approvals"

    id = db.Column(db.String(50), primary_key=True)

    proposal_id = db.Column(
        db.String(50),
        db.ForeignKey("adjustment_proposals.id"),
        nullable=False
    )

    reviewer_role = db.Column(
        db.String(30), nullable=False
    )

    reviewer_name = db.Column(
        db.String(100), nullable=False
    )

    decision = db.Column(
        db.String(30), nullable=False
    )

    reason = db.Column(
        db.Text, nullable=False
    )

    decided_at = db.Column(
        db.DateTime, nullable=False
    )

    __table_args__ = (
        db.CheckConstraint(
            "decision IN ('APPROVED', 'REJECTED')",
            name="valid_approval_decision"
        ),
        db.CheckConstraint(
            "reviewer_role IN ('MANAGER', 'HR')",
            name="valid_reviewer_role"
        ),
    )


class AuditEvent(db.Model):
    __tablename__ = "audit_events"

    id = db.Column(db.String(50), primary_key=True)

    proposal_id = db.Column(
        db.String(50),
        db.ForeignKey("adjustment_proposals.id"),
        nullable=False
    )

    event_type = db.Column(
        db.String(50), nullable=False
    )

    actor = db.Column(
        db.String(100), nullable=False
    )

    details_json = db.Column(
        db.Text, nullable=False
    )

    created_at = db.Column(
        db.DateTime, nullable=False
    )