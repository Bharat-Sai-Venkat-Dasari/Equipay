
import argparse
import csv
import hashlib
import json
import random
from datetime import date
from pathlib import Path

from faker import Faker
from sqlalchemy import event

from app import create_app
from models import (
    db, Role, Level, Location, Employee,
    CompensationBand, SalaryRecord,
    PerformanceEvidence, Tenure, Promotion,
    FTEHistory, ExchangeRate, SyntheticIssue
)

SEED = 20261022
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data"

LOCATIONS = [
    ("HYD", "Hyderabad", "India", "INR", 1.0),
    ("BLR", "Bengaluru", "India", "INR", 1.15),
    ("NYC", "New York", "USA", "USD", 1.8),
]

ISSUE_TYPES = [
    "EXPIRED_BAND",
    "FTE_NOT_NORMALIZED",
    "CURRENCY_CONVERSION_MISSING",
    "UNAPPROVED_ADJUSTMENT",
    "INVALID_COMPARABLE_GROUP",
    "UNEXPLAINED_DISPARITY",
]

MODELS = [
    Role, Level, Location, Employee,
    CompensationBand, SalaryRecord,
    PerformanceEvidence, Tenure, Promotion,
    FTEHistory, ExchangeRate, SyntheticIssue
]


def create_master_data(rng):
    roles = []
    levels = []
    locations = []
    bands = []

    families = [
        "Engineering", "Analytics", "Product",
        "Operations", "Finance"
    ]

    for i in range(1, 21):
        role = Role(
            id=f"ROLE-{i:03d}",
            name=f"{families[(i - 1) % 5]} Specialist {i}",
            family=families[(i - 1) % 5]
        )
        roles.append(role)

    for i in range(1, 11):
        levels.append(Level(
            id=f"L{i}",
            name=f"Level {i}",
            rank=i
        ))

    for code, city, country, currency, factor in LOCATIONS:
        locations.append(Location(
            id=code,
            city=city,
            country=country,
            currency=currency
        ))

    db.session.add_all(roles + levels + locations)
    db.session.flush()

    for year in (2024, 2025, 2026):
        for role in roles:
            for level in levels:
                for loc in locations:
                    factor = next(
                        x[4] for x in LOCATIONS if x[0] == loc.id
                    )
                    # Values are in the location's local currency.
                    base = (
                        350000
                        + level.rank * 125000
                        + int(role.id[-3:]) * 8500
                    )
                    base *= factor
                    base *= 1.06 ** (year - 2024)

                    if loc.currency == "USD":
                        base /= 85.0

                    midpoint = round(base, 2)
                    bands.append(CompensationBand(
                        id=f"BAND-{role.id}-{level.id}-{loc.id}-{year}",
                        role_id=role.id,
                        level_id=level.id,
                        location_id=loc.id,
                        minimum=round(midpoint * 0.80, 2),
                        midpoint=midpoint,
                        maximum=round(midpoint * 1.20, 2),
                        effective_from=date(year, 1, 1),
                        effective_to=date(year, 12, 31)
                    ))

    db.session.add_all(bands)

    for year in (2024, 2025, 2026):
        for code, rate in (
            ("INR", 1.0),
            ("USD", 83.0 + (year - 2024))
        ):
            db.session.add(ExchangeRate(
                id=f"FX-{code}-INR-{year}",
                from_currency=code,
                to_currency="INR",
                rate=rate,
                effective_date=date(year, 1, 1)
            ))

    db.session.flush()

    band_map = {
        (b.role_id, b.level_id, b.location_id,
         b.effective_from.year): b
        for b in bands
    }

    return roles, levels, locations, band_map


def generate_employees(count, rng, fake, roles, levels,
                       locations, band_map):
    employees = []
    salaries = []
    performances = []
    tenures = []
    promotions = []
    fte_events = []

    for number in range(1, count + 1):
        emp_id = f"EMP-{number:06d}"

        role = rng.choice(roles)
        loc = rng.choice(locations)
        initial_rank = rng.randint(1, 9)

        # All generated employees have salary records
        # covering 2024, 2025 and 2026.
        hire_year = rng.randint(2015, 2023)
        hire_date = date(hire_year, rng.randint(1, 12), 1)

        promoted = rng.random() < 0.16
        promotion_year = rng.choice([2025, 2026]) if promoted else None

        initial_fte = rng.choices(
            [1.0, 0.8, 0.5],
            weights=[85, 10, 5]
        )[0]

        changed_fte = rng.random() < 0.08
        new_fte = (
            rng.choice([0.5, 0.8, 1.0])
            if changed_fte else initial_fte
        )

        current_rank = initial_rank + (
            1 if promoted else 0
        )

        employee = Employee(
            id=emp_id,
            name=fake.name(),
            email=f"employee{number:06d}@example.test",
            role_id=role.id,
            level_id=f"L{current_rank}",
            location_id=loc.id,
            hire_date=hire_date,
            fte=new_fte
        )
        employees.append(employee)

        if promoted:
            promotions.append(Promotion(
                id=f"PROM-{number:06d}",
                employee_id=emp_id,
                previous_level_id=f"L{initial_rank}",
                new_level_id=f"L{initial_rank + 1}",
                effective_date=date(promotion_year, 1, 1)
            ))

        fte_events.append(FTEHistory(
            id=f"FTE-{number:06d}-2024",
            employee_id=emp_id,
            effective_date=date(2024, 1, 1),
            fte=initial_fte
        ))

        if changed_fte:
            fte_events.append(FTEHistory(
                id=f"FTE-{number:06d}-2026",
                employee_id=emp_id,
                effective_date=date(2026, 1, 1),
                fte=new_fte
            ))

        for year in (2024, 2025, 2026):
            rank = initial_rank + (
                1 if promotion_year and year >= promotion_year
                else 0
            )
            level_id = f"L{rank}"
            fte = new_fte if changed_fte and year == 2026 else initial_fte

            band = band_map[
                (role.id, level_id, loc.id, year)
            ]

            rating = rng.choices(
                [2.0, 3.0, 4.0, 5.0],
                weights=[10, 50, 30, 10]
            )[0]

            salary_factor = (
                0.92
                + 0.035 * (rating - 3)
                + rng.uniform(-0.07, 0.07)
            )

            annual_fte_salary = round(
                band.midpoint * salary_factor, 2
            )

            actual_salary = round(
                annual_fte_salary * fte, 2
            )

            salaries.append(SalaryRecord(
                id=f"SAL-{emp_id}-{year}-01",
                employee_id=emp_id,
                effective_date=date(year, 1, 1),
                salary_amount=actual_salary,
                currency=loc.currency,
                fte=fte,
                change_reason=(
                    "PROMOTION"
                    if promotion_year == year
                    else "ANNUAL_REVIEW"
                )
            ))

            performances.append(PerformanceEvidence(
                id=f"PERF-{number:06d}-{year}",
                employee_id=emp_id,
                review_year=year,
                rating=rating,
                description="Synthetic annual performance review"
            ))

        months = (
            (2026 - hire_date.year) * 12
            + (10 - hire_date.month)
        )
        tenures.append(Tenure(
            id=f"TEN-{number:06d}",
            employee_id=emp_id,
            as_of_date=date(2026, 10, 1),
            months=max(0, months)
        ))

    db.session.add_all(employees)
    db.session.flush()
    db.session.add_all(
        salaries + performances + tenures
        + promotions + fte_events
    )
    db.session.flush()

    return employees, salaries


def inject_issues(employees, salaries, rng):
    """
    Inject one salary outlier and record the remaining
    negative scenarios as labeled evaluation cases.

    The other five scenarios will receive executable
    evaluation context in Part 3.
    """
    salary_map = {
        (s.employee_id, s.effective_date.year): s
        for s in salaries
    }

    selected = rng.sample(
        employees,
        min(len(employees), 60)
    )

    cases = []

    for index, employee in enumerate(selected):
        issue_type = ISSUE_TYPES[index % len(ISSUE_TYPES)]
        salary = salary_map[(employee.id, 2026)]

        if issue_type == "UNEXPLAINED_DISPARITY":
            salary.salary_amount = round(
                salary.salary_amount * 0.55, 2
            )

        cases.append({
            "case_id": f"CASE-{index + 1:06d}",
            "employee_id": employee.id,
            "salary_id": salary.id,
            "issue_type": issue_type,
            "expected_label": 1,
            "expected_decision": "FLAG_FOR_REVIEW",
            "rule_id": f"RULE-{issue_type}",
            "explanation": (
                "Injected synthetic evaluation case: "
                + issue_type
            )
        })

        db.session.add(SyntheticIssue(
            id=f"CASE-{index + 1:06d}",
            employee_id=employee.id,
            salary_id=salary.id,
            issue_type=issue_type,
            description=cases[-1]["explanation"],
            expected_decision="FLAG_FOR_REVIEW"
        ))

    return cases


def export_data(ground_truth):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {}

    for model in MODELS:
        table = model.__table__
        columns = [c.name for c in table.columns]

        rows = db.session.query(model).order_by(
            *table.primary_key.columns
        ).all()

        path = OUTPUT_DIR / f"{table.name}.csv"

        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            for row in rows:
                writer.writerow([
                    getattr(row, column)
                    for column in columns
                ])

        contents = path.read_bytes()
        manifest[path.name] = {
            "rows": len(rows),
            "sha256": hashlib.sha256(contents).hexdigest()
        }

    truth_path = OUTPUT_DIR / "ground_truth.json"
    truth_path.write_text(
        json.dumps(ground_truth, indent=2),
        encoding="utf-8"
    )

    with (OUTPUT_DIR / "ground_truth.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=list(ground_truth[0].keys())
        )
        writer.writeheader()
        writer.writerows(ground_truth)

    for filename in ("ground_truth.json", "ground_truth.csv"):
        contents = (OUTPUT_DIR / filename).read_bytes()
        manifest[filename] = {
            "rows": len(ground_truth),
            "sha256": hashlib.sha256(contents).hexdigest()
        }

    (OUTPUT_DIR / "source_manifest.json").write_text(
        json.dumps({
            "seed": SEED,
            "provenance": "Fully synthetic data",
            "files": manifest
        }, indent=2),
        encoding="utf-8"
    )

    return manifest


def run(count, seed):
    global SEED
    SEED = seed

    rng = random.Random(seed)
    fake = Faker("en_IN")
    Faker.seed(seed)

    app = create_app()

    with app.app_context():
        # Local synthetic database reset only.
        # Never run against a production database.
        db.drop_all()
        db.create_all()

        roles, levels, locations, band_map = (
            create_master_data(rng)
        )

        employees, salaries = generate_employees(
            count, rng, fake,
            roles, levels, locations, band_map
        )

        ground_truth = inject_issues(
            employees, salaries, rng
        )

        db.session.commit()

        manifest = export_data(ground_truth)

        print("\nDATA GENERATION COMPLETED")
        print("-------------------------")
        print("Employees:", Employee.query.count())
        print("Roles:", Role.query.count())
        print("Levels:", Level.query.count())
        print("Locations:", Location.query.count())
        print("Bands:", CompensationBand.query.count())
        print("Salary records:", SalaryRecord.query.count())
        print("Ground truth cases:", len(ground_truth))
        print("CSV files exported:", len(MODELS))
        print("Manifest entries:", len(manifest))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--employees", type=int, default=100
    )
    parser.add_argument(
        "--seed", type=int, default=20261022
    )
    args = parser.parse_args()

    if args.employees < 1:
        parser.error("--employees must be at least 1")

    run(args.employees, args.seed)