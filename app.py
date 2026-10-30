
from flask import Flask, jsonify, request, render_template

from config import Config
from services.evaluation import evaluate_detection
from models import (
    db,
    Employee,
    Role,
    Level,
    Location,
    CompensationBand,
    SalaryRecord,
    SyntheticIssue,
    AdjustmentProposal
)

from services.compensation import (
    analyze_employee,
    comparable_group
)

from services.anomalies import (
    detect_employee_anomalies,
    evaluate_required_scenarios
)

from services.approvals import (
    create_proposal,
    review_proposal,
    apply_proposal,
    serialize_proposal
)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    # Create missing database tables
    with app.app_context():
        db.create_all()

    # ==========================================
    # DASHBOARD
    # ==========================================

    @app.get("/")
    def home():
        return render_template("index.html")

    # ==========================================
    # HEALTH CHECK
    # ==========================================

    @app.get("/api/health")
    def health():
        return jsonify({
            "application": "EquiPay",
            "status": "running",
            "message": "Compensation Equity Audit API is working"
        })

    # ==========================================
    # DASHBOARD SUMMARY
    # ==========================================

    @app.get("/api/summary")
    def summary():
        return jsonify({
            "employees": Employee.query.count(),
            "roles": Role.query.count(),
            "levels": Level.query.count(),
            "locations": Location.query.count(),
            "compensation_bands": CompensationBand.query.count(),
            "salary_records": SalaryRecord.query.count(),
            "synthetic_cases": SyntheticIssue.query.count(),
            "adjustment_proposals": AdjustmentProposal.query.count()
        })

    # ==========================================
    # EMPLOYEE DIRECTORY
    # ==========================================

    @app.get("/api/employees")
    def employees():
        page = max(
            request.args.get("page", 1, type=int),
            1
        )

        per_page = min(
            max(
                request.args.get("per_page", 20, type=int),
                1
            ),
            100
        )

        pagination = (
            Employee.query
            .order_by(Employee.id)
            .paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
        )

        return jsonify({
            "total": pagination.total,
            "page": page,
            "pages": pagination.pages,
            "employees": [
                {
                    "id": emp.id,
                    "name": emp.name,
                    "email": emp.email,
                    "role_id": emp.role_id,
                    "level_id": emp.level_id,
                    "location_id": emp.location_id,
                    "fte": emp.fte
                }
                for emp in pagination.items
            ]
        })

    # ==========================================
    # EMPLOYEE COMPENSATION ANALYSIS
    # ==========================================

    @app.get("/api/compensation/<employee_id>")
    def compensation(employee_id):
        try:
            result = analyze_employee(employee_id)
            return jsonify(result)

        except ValueError as exc:
            return jsonify({
                "error": str(exc)
            }), 400

    # ==========================================
    # COMPARABLE EMPLOYEE GROUP
    # ==========================================

    @app.get("/api/comparable/<employee_id>")
    def comparable(employee_id):
        try:
            result = comparable_group(employee_id)
            return jsonify(result)

        except ValueError as exc:
            return jsonify({
                "error": str(exc)
            }), 400

    # ==========================================
    # EMPLOYEE ANOMALIES
    # ==========================================

    @app.get("/api/anomalies/<employee_id>")
    def employee_anomalies(employee_id):

        if db.session.get(Employee, employee_id) is None:
            return jsonify({
                "error": "Employee not found"
            }), 404

        findings = detect_employee_anomalies(employee_id)

        return jsonify({
            "employee_id": employee_id,
            "findings": findings,
            "total_findings": len(findings)
        })

    # ==========================================
    # SYNTHETIC NEGATIVE SCENARIOS
    # ==========================================

    @app.get("/api/scenarios")
    def scenarios():
        results = evaluate_required_scenarios()

        return jsonify({
            "total_cases": len(results),
            "scenario_checks_only": True,
            "results": results
        })

    # ==========================================
    # LIST ALL ADJUSTMENT PROPOSALS
    # ==========================================

    @app.get("/api/proposals")
    def list_proposals():

        proposals = (
            AdjustmentProposal.query
            .order_by(
                AdjustmentProposal.created_at.desc(),
                AdjustmentProposal.id.desc()
            )
            .limit(100)
            .all()
        )

        return jsonify({
            "total": len(proposals),
            "proposals": [
                serialize_proposal(proposal)
                for proposal in proposals
            ]
        })

    # ==========================================
    # CREATE ADJUSTMENT PROPOSAL
    # ==========================================

    @app.post("/api/proposals")
    def submit_proposal():

        data = request.get_json(silent=True) or {}

        try:
            proposed_salary = float(
                data.get("proposed_salary", 0)
            )

            result = create_proposal(
                employee_id=str(
                    data.get("employee_id", "")
                ).strip().upper(),

                proposed_salary=proposed_salary,

                justification=str(
                    data.get("justification", "")
                ),

                created_by=str(
                    data.get("created_by", "")
                )
            )

            return jsonify(result), 201

        except (ValueError, TypeError) as exc:
            db.session.rollback()

            return jsonify({
                "error": str(exc)
            }), 400

    # ==========================================
    # GET SINGLE PROPOSAL DETAILS
    # ==========================================

    @app.get("/api/proposals/<proposal_id>")
    def proposal_details(proposal_id):

        proposal = db.session.get(
            AdjustmentProposal,
            proposal_id
        )

        if proposal is None:
            return jsonify({
                "error": "Proposal not found"
            }), 404

        return jsonify(
            serialize_proposal(proposal)
        )

    # ==========================================
    # MANAGER / HR APPROVAL OR REJECTION
    # ==========================================

    @app.post("/api/proposals/<proposal_id>/review")
    def submit_review(proposal_id):

        data = request.get_json(silent=True) or {}

        try:
            result = review_proposal(
                proposal_id=proposal_id,

                reviewer_role=str(
                    data.get("reviewer_role", "")
                ),

                reviewer_name=str(
                    data.get("reviewer_name", "")
                ),

                decision=str(
                    data.get("decision", "")
                ),

                reason=str(
                    data.get("reason", "")
                )
            )

            return jsonify(result)

        except ValueError as exc:
            db.session.rollback()

            return jsonify({
                "error": str(exc)
            }), 400

    # ==========================================
    # APPLY FULLY APPROVED ADJUSTMENT
    # ==========================================

    @app.post("/api/proposals/<proposal_id>/apply")
    def submit_application(proposal_id):

        data = request.get_json(silent=True) or {}

        try:
            result = apply_proposal(
                proposal_id=proposal_id,

                actor=str(
                    data.get("actor", "")
                )
            )

            return jsonify(result)

        except ValueError as exc:
            db.session.rollback()

            return jsonify({
                "error": str(exc)
            }), 400

    # ==========================================
    # ERROR HANDLERS
    # ==========================================

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith("/api/"):
            return jsonify({
                "error": "API endpoint not found"
            }), 404

        return error

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()

        if request.path.startswith("/api/"):
            return jsonify({
                "error": "Internal server error. Check Flask terminal."
            }), 500

        return error

    @app.get("/api/evaluation")
    def evaluation():
        return jsonify(evaluate_detection())

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)