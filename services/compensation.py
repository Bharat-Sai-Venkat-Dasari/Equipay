
from datetime import date
from statistics import median

from models import (
    Employee, SalaryRecord, CompensationBand,
    ExchangeRate, PerformanceEvidence, Promotion
)


def latest_salary(employee_id, as_of=date(2026, 12, 31)):
    return (
        SalaryRecord.query
        .filter(
            SalaryRecord.employee_id == employee_id,
            SalaryRecord.effective_date <= as_of
        )
        .order_by(
            SalaryRecord.effective_date.desc(),
            SalaryRecord.id.desc()
        )
        .first()
    )


def active_band(role_id, level_id, location_id, as_of):
    """Select a band valid on the specified salary date."""
    return (
        CompensationBand.query
        .filter(
            CompensationBand.role_id == role_id,
            CompensationBand.level_id == level_id,
            CompensationBand.location_id == location_id,
            CompensationBand.effective_from <= as_of,
            (
                CompensationBand.effective_to.is_(None)
                | (CompensationBand.effective_to >= as_of)
            )
        )
        .order_by(CompensationBand.effective_from.desc())
        .first()
    )


def exchange_rate(from_currency, to_currency, as_of):
    if from_currency == to_currency:
        return 1.0

    record = (
        ExchangeRate.query
        .filter(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.effective_date <= as_of
        )
        .order_by(ExchangeRate.effective_date.desc())
        .first()
    )

    if record is None:
        raise ValueError(
            f"Missing exchange rate: {from_currency} "
            f"to {to_currency} on {as_of}"
        )

    return float(record.rate)


def normalize_salary(amount, fte, currency, as_of):
    if fte is None or not (0 < float(fte) <= 1):
        raise ValueError("FTE must be greater than 0 and at most 1")

    full_time_salary = float(amount) / float(fte)

    rate = exchange_rate(currency, "INR", as_of)

    return {
        "full_time_salary": round(full_time_salary, 2),
        "normalized_inr": round(full_time_salary * rate, 2),
        "exchange_rate": rate
    }


def compa_ratio(salary, midpoint):
    if midpoint <= 0:
        raise ValueError("Band midpoint must be positive")
    return round(salary / midpoint, 4)


def band_position(salary, minimum, maximum):
    if maximum <= minimum:
        raise ValueError("Invalid band range")

    return round(
        ((salary - minimum) / (maximum - minimum)) * 100,
        2
    )


def employee_level_at(employee, as_of):
    """
    Reconstruct historical level from promotion events.
    Part 2 stores the employee's current level.
    """
    promotions = (
        Promotion.query
        .filter(
            Promotion.employee_id == employee.id
        )
        .order_by(Promotion.effective_date.asc())
        .all()
    )

    level_id = (
        promotions[0].previous_level_id
        if promotions else employee.level_id
    )

    for promotion in promotions:
        if promotion.effective_date <= as_of:
            level_id = promotion.new_level_id

    return level_id


def analyze_employee(employee_id, as_of=date(2026, 12, 31)):
    employee = Employee.query.filter_by(id=employee_id).first()

    if employee is None:
        raise ValueError("Employee not found")

    salary = latest_salary(employee_id, as_of)

    if salary is None:
        raise ValueError("No salary record available")

    level_id = employee_level_at(
        employee, salary.effective_date
    )

    band = active_band(
        employee.role_id,
        level_id,
        employee.location_id,
        salary.effective_date
    )

    if band is None:
        raise ValueError("No effective compensation band found")

    normalized = normalize_salary(
        salary.salary_amount,
        salary.fte,
        salary.currency,
        salary.effective_date
    )

    # Convert salary into the band's currency before
    # comparing it with band minimum/midpoint/maximum.
    if salary.currency == band.effective_currency if hasattr(
        band, "effective_currency"
    ) else False:
        pass

    # In Part 2 the location determines band currency.
    location_currency = employee.location.currency

    salary_in_band_currency = (
        normalized["normalized_inr"]
        / exchange_rate(
            location_currency, "INR", salary.effective_date
        )
    )

    midpoint = float(band.midpoint)
    minimum = float(band.minimum)
    maximum = float(band.maximum)

    ratio = compa_ratio(salary_in_band_currency, midpoint)
    position = band_position(
        salary_in_band_currency, minimum, maximum
    )

    if salary_in_band_currency < minimum:
        classification = "BELOW_BAND"
    elif salary_in_band_currency > maximum:
        classification = "ABOVE_BAND"
    else:
        classification = "WITHIN_BAND"

    return {
        "employee_id": employee.id,
        "employee_name": employee.name,
        "role_id": employee.role_id,
        "level_id": level_id,
        "location_id": employee.location_id,
        "salary_id": salary.id,
        "salary_date": salary.effective_date.isoformat(),
        "actual_salary": round(float(salary.salary_amount), 2),
        "currency": salary.currency,
        "fte": salary.fte,
        "full_time_salary": normalized["full_time_salary"],
        "normalized_inr": normalized["normalized_inr"],
        "band_id": band.id,
        "band_minimum": minimum,
        "band_midpoint": midpoint,
        "band_maximum": maximum,
        "salary_in_band_currency": round(
            salary_in_band_currency, 2
        ),
        "compa_ratio": ratio,
        "band_position": position,
        "classification": classification
    }


def comparable_group(employee_id, as_of=date(2026, 12, 31)):
    target = analyze_employee(employee_id, as_of)

    peers = Employee.query.filter_by(
        role_id=target["role_id"],
        location_id=target["location_id"]
    ).all()

    values = []
    peer_ids = []

    for peer in peers:
        if peer.id == employee_id:
            continue
        try:
            result = analyze_employee(peer.id, as_of)
        except ValueError:
            continue

        if result["level_id"] != target["level_id"]:
            continue

        values.append(result["normalized_inr"])
        peer_ids.append(peer.id)

    if len(values) < 5:
        return {
            "employee_id": employee_id,
            "status": "INSUFFICIENT_PEERS",
            "peer_count": len(values)
        }

    peer_median = median(values)
    employee_salary = target["normalized_inr"]

    gap_percentage = (
        (employee_salary - peer_median)
        / peer_median * 100
    )

    return {
        "employee_id": employee_id,
        "status": "COMPARABLE",
        "peer_count": len(values),
        "peer_median_inr": round(peer_median, 2),
        "employee_salary_inr": employee_salary,
        "gap_percentage": round(gap_percentage, 2),
        "group_rule": "Same role, historical level and location",
        "peer_ids": peer_ids
    }