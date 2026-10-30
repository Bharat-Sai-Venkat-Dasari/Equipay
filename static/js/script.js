
const API = {
    summary: "/api/summary",
    employees: "/api/employees",
    compensation: id =>
        `/api/compensation/${encodeURIComponent(id)}`,
    comparable: id =>
        `/api/comparable/${encodeURIComponent(id)}`,
    anomalies: id =>
        `/api/anomalies/${encodeURIComponent(id)}`
};

let currentPage = 1;
let totalPages = 1;

const $ = id => document.getElementById(id);

function setText(id, value) {
    $(id).textContent = value ?? "—";
}

function formatNumber(value) {
    if (value === null || value === undefined) {
        return "—";
    }
    return Number(value).toLocaleString("en-IN", {
        maximumFractionDigits: 2
    });
}

function formatMoney(value, currency = "INR") {
    if (value === null || value === undefined) {
        return "—";
    }

    try {
        return new Intl.NumberFormat("en-IN", {
            style: "currency",
            currency,
            maximumFractionDigits: 2
        }).format(Number(value));
    } catch {
        return `${formatNumber(value)} ${currency}`;
    }
}

function showError(message) {
    const alert = $("appAlert");
    alert.textContent = message;
    alert.classList.remove("d-none");
}

function clearError() {
    $("appAlert").classList.add("d-none");
    $("appAlert").textContent = "";
}

async function fetchJSON(url) {
    const response = await fetch(url);

    let data;
    try {
        data = await response.json();
    } catch {
        throw new Error(`Server returned HTTP ${response.status}`);
    }

    if (!response.ok) {
        throw new Error(
            data.error || `Request failed: HTTP ${response.status}`
        );
    }

    return data;
}

async function loadSummary() {
    const data = await fetchJSON(API.summary);

    setText("employeeCount", formatNumber(data.employees));
    setText("bandCount", formatNumber(data.compensation_bands));
    setText("salaryCount", formatNumber(data.salary_records));
    setText("scenarioCount", formatNumber(data.synthetic_cases));
}

function createCell(value) {
    const td = document.createElement("td");
    td.textContent = value ?? "—";
    return td;
}

async function loadEmployees(page = 1) {
    const data = await fetchJSON(
        `${API.employees}?page=${page}&per_page=10`
    );

    currentPage = data.page;
    totalPages = data.pages;

    const tbody = $("employeeTable");
    tbody.replaceChildren();

    if (!data.employees.length) {
        const row = document.createElement("tr");
        const cell = createCell("No employees found");
        cell.colSpan = 6;
        cell.className = "text-center";
        row.appendChild(cell);
        tbody.appendChild(row);
    }

    data.employees.forEach(employee => {
        const row = document.createElement("tr");

        row.appendChild(createCell(employee.id));
        row.appendChild(createCell(employee.name));
        row.appendChild(createCell(employee.role_id));
        row.appendChild(createCell(employee.level_id));
        row.appendChild(createCell(employee.location_id));

        const actionCell = document.createElement("td");
        const button = document.createElement("button");

        button.className = "btn btn-outline-primary btn-sm";
        button.textContent = "Analyze";
        button.addEventListener("click", () => {
            $("employeeId").value = employee.id;
            document.getElementById("analysis").scrollIntoView({
                behavior: "smooth"
            });
            analyzeEmployee(employee.id);
        });

        actionCell.appendChild(button);
        row.appendChild(actionCell);
        tbody.appendChild(row);
    });

    setText(
        "pageInfo",
        `Page ${currentPage} of ${Math.max(totalPages, 1)}`
    );

    $("prevPage").disabled = currentPage <= 1;
    $("nextPage").disabled = currentPage >= totalPages;
}

function renderCompensation(data, peer) {
    $("analysisPlaceholder").classList.add("d-none");
    $("analysisResults").classList.remove("d-none");

    setText("selectedName", data.employee_name);
    setText(
        "selectedDetails",
        `${data.employee_id} • ${data.role_id} • ` +
        `${data.level_id} • ${data.location_id}`
    );

    setText("bandStatus", data.classification.replaceAll("_", " "));

    $("bandStatus").className =
        "status-pill" +
        (data.classification === "WITHIN_BAND" ? "" : " warning");

    setText("compaRatio", formatNumber(data.compa_ratio));
    setText("bandPosition", `${formatNumber(data.band_position)}%`);

    if (peer.status === "COMPARABLE") {
        setText(
            "peerGap",
            `${peer.gap_percentage > 0 ? "+" : ""}` +
            `${formatNumber(peer.gap_percentage)}%`
        );
        setText("peerCount", formatNumber(peer.peer_count));
    } else {
        setText("peerGap", "N/A");
        setText("peerCount", formatNumber(peer.peer_count));
    }

    setText(
        "actualSalary",
        formatMoney(data.actual_salary, data.currency)
    );
    setText("fteValue", data.fte);
    setText(
        "fullTimeSalary",
        formatMoney(data.full_time_salary, data.currency)
    );
    setText(
        "normalizedSalary",
        formatMoney(data.normalized_inr)
    );

    // Bands are denominated in the location's currency.
    setText(
        "bandMinimum",
        formatMoney(data.band_minimum, data.currency)
    );
    setText(
        "bandMidpoint",
        formatMoney(data.band_midpoint, data.currency)
    );
    setText(
        "bandMaximum",
        formatMoney(data.band_maximum, data.currency)
    );

    const progress = $("bandProgress");
    const width = Math.max(
        0, Math.min(100, Number(data.band_position))
    );

    progress.style.width = `${width}%`;
    progress.setAttribute("aria-valuenow", width);
    progress.className =
        "progress-bar " +
        (data.classification === "WITHIN_BAND"
            ? "bg-primary"
            : "bg-warning");
}

function renderFindings(data) {
    const container = $("findingsList");
    container.replaceChildren();
    container.className = "";

    if (!data.findings.length) {
        container.className = "empty-state";
        container.textContent =
            "No rule-based findings for this employee.";
        return;
    }

    data.findings.forEach(finding => {
        const item = document.createElement("div");
        item.className = "finding-item";

        const title = document.createElement("h4");
        title.textContent =
            `${finding.issue_type.replaceAll("_", " ")} ` +
            `(${finding.severity})`;

        const description = document.createElement("p");
        description.textContent =
            `${finding.evidence} • Rule: ${finding.rule_id}`;

        item.append(title, description);
        container.appendChild(item);
    });
}

async function analyzeEmployee(id) {
    clearError();

    const employeeId = id.trim().toUpperCase();

    if (!/^EMP-\d{6}$/.test(employeeId)) {
        showError("Enter a valid ID, for example EMP-000001.");
        return;
    }

    $("analysisPlaceholder").classList.remove("d-none");
    $("analysisPlaceholder").textContent = "Analyzing employee...";
    $("analysisResults").classList.add("d-none");

    $("findingsList").className = "empty-state";
    $("findingsList").textContent = "Loading findings...";

    try {
        const [compensation, comparable, anomalies] =
            await Promise.all([
                fetchJSON(API.compensation(employeeId)),
                fetchJSON(API.comparable(employeeId)),
                fetchJSON(API.anomalies(employeeId))
            ]);

        renderCompensation(compensation, comparable);
        renderFindings(anomalies);
    } catch (error) {
        $("analysisPlaceholder").textContent =
            "Unable to load employee analysis.";
        $("findingsList").textContent =
            "No findings available.";
        showError(error.message);
    }
}

document.addEventListener("DOMContentLoaded", async () => {
    $("analysisForm").addEventListener("submit", event => {
        event.preventDefault();
        analyzeEmployee($("employeeId").value);
    });

    $("prevPage").addEventListener("click", async () => {
        if (currentPage > 1) {
            try {
                clearError();
                await loadEmployees(currentPage - 1);
            } catch (error) {
                showError(error.message);
            }
        }
    });

    $("nextPage").addEventListener("click", async () => {
        if (currentPage < totalPages) {
            try {
                clearError();
                await loadEmployees(currentPage + 1);
            } catch (error) {
                showError(error.message);
            }
        }
    });

    $("refreshBtn").addEventListener("click", async () => {
        try {
            clearError();
            await Promise.all([
                loadSummary(),
                loadEmployees(currentPage)
            ]);
        } catch (error) {
            showError(error.message);
        }
    });

    try {
        await Promise.all([
            loadSummary(),
            loadEmployees()
        ]);
    } catch (error) {
        showError(error.message);
    }
});

let selectedProposalId = null;

async function sendJSON(url, payload) {
    const response = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(
            data.error || `HTTP ${response.status}`
        );
    }

    return data;
}

async function loadProposals() {
    const data = await fetchJSON("/api/proposals");
    const tbody = $("proposalTable");

    tbody.replaceChildren();

    if (!data.proposals.length) {
        const row = document.createElement("tr");
        const cell = createCell("No proposals created yet");
        cell.colSpan = 5;
        row.appendChild(cell);
        tbody.appendChild(row);
        return;
    }

    data.proposals.forEach(proposal => {
        const row = document.createElement("tr");

        row.appendChild(createCell(proposal.id));
        row.appendChild(createCell(proposal.employee_id));
        row.appendChild(
            createCell(
                formatMoney(
                    proposal.proposed_salary,
                    proposal.currency
                )
            )
        );
        row.appendChild(createCell(proposal.status));

        const actionCell = document.createElement("td");
        const button = document.createElement("button");

        button.className = "btn btn-outline-primary btn-sm";
        button.textContent = "View";
        button.addEventListener("click", () => {
            viewProposal(proposal.id);
        });

        actionCell.appendChild(button);
        row.appendChild(actionCell);
        tbody.appendChild(row);
    });
}

function addDetailLine(container, label, value) {
    const row = document.createElement("div");
    row.className = "proposal-detail-row";

    const key = document.createElement("span");
    key.textContent = label;

    const val = document.createElement("strong");
    val.textContent = String(value ?? "—");

    row.append(key, val);
    container.appendChild(row);
}

function renderAuditTimeline(events) {
    const timeline = $("auditTimeline");
    timeline.replaceChildren();

    if (!events.length) {
        timeline.textContent = "No events recorded.";
        return;
    }

    events.forEach(event => {
        const item = document.createElement("div");
        item.className = "audit-event";

        const heading = document.createElement("strong");
        heading.textContent =
            event.event_type.replaceAll("_", " ");

        const meta = document.createElement("small");
        meta.textContent =
            `${event.actor} • ${event.created_at}`;

        const description = document.createElement("pre");
        description.textContent = JSON.stringify(
            event.details, null, 2
        );

        item.append(heading, meta, description);
        timeline.appendChild(item);
    });
}

async function viewProposal(proposalId) {
    clearError();

    try {
        const proposal = await fetchJSON(
            `/api/proposals/${encodeURIComponent(proposalId)}`
        );

        selectedProposalId = proposal.id;

        const details = $("proposalDetails");
        details.className = "proposal-details";
        details.replaceChildren();

        addDetailLine(details, "Proposal ID", proposal.id);
        addDetailLine(
            details, "Employee", proposal.employee_id
        );
        addDetailLine(
            details,
            "Proposed Salary",
            formatMoney(
                proposal.proposed_salary,
                proposal.currency
            )
        );
        addDetailLine(details, "Status", proposal.status);
        addDetailLine(
            details, "Created By", proposal.created_by
        );
        addDetailLine(
            details, "Justification", proposal.justification
        );

        renderAuditTimeline(proposal.audit_events);

        $("proposalActions").classList.remove("d-none");

        const managerPending =
            proposal.status === "PENDING_MANAGER";

        const hrPending =
            proposal.status === "PENDING_HR";

        $("managerApprove").disabled = !managerPending;
        $("managerReject").disabled = !managerPending;

        $("hrApprove").disabled = !hrPending;
        $("hrReject").disabled = !hrPending;

        $("applyAdjustment").disabled =
            proposal.status !== "APPROVED";

    } catch (error) {
        showError(error.message);
    }
}

async function reviewSelected(role, decision) {
    if (!selectedProposalId) {
        showError("Select a proposal first.");
        return;
    }

    const reviewerName = $("reviewerName").value.trim();
    const reason = $("reviewReason").value.trim();

    if (!reviewerName || !reason) {
        showError("Reviewer name and reason are required.");
        return;
    }

    try {
        clearError();

        await sendJSON(
            `/api/proposals/${encodeURIComponent(
                selectedProposalId
            )}/review`,
            {
                reviewer_role: role,
                reviewer_name: reviewerName,
                decision,
                reason
            }
        );

        await loadProposals();
        await viewProposal(selectedProposalId);

    } catch (error) {
        showError(error.message);
    }
}

async function applySelected() {
    if (!selectedProposalId) {
        showError("Select a proposal first.");
        return;
    }

    try {
        clearError();

        await sendJSON(
            `/api/proposals/${encodeURIComponent(
                selectedProposalId
            )}/apply`,
            { actor: "HR Operations Demo" }
        );

        await loadProposals();
        await viewProposal(selectedProposalId);

        await loadSummary();

    } catch (error) {
        showError(error.message);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    $("proposalForm").addEventListener(
        "submit",
        async event => {
            event.preventDefault();

            const employeeId =
                $("proposalEmployee").value.trim().toUpperCase();

            const proposedSalary =
                Number($("proposedSalary").value);

            const justification =
                $("proposalReason").value.trim();

            const createdBy =
                $("proposalCreator").value.trim();

            try {
                clearError();

                const proposal = await sendJSON(
                    "/api/proposals",
                    {
                        employee_id: employeeId,
                        proposed_salary: proposedSalary,
                        justification,
                        created_by: createdBy
                    }
                );

                await loadProposals();
                await viewProposal(proposal.id);

                $("proposalReason").value = "";

            } catch (error) {
                showError(error.message);
            }
        }
    );

    $("refreshProposals").addEventListener(
        "click",
        async () => {
            try {
                clearError();
                await loadProposals();
            } catch (error) {
                showError(error.message);
            }
        }
    );

    $("managerApprove").addEventListener(
        "click",
        () => reviewSelected("MANAGER", "APPROVED")
    );

    $("managerReject").addEventListener(
        "click",
        () => reviewSelected("MANAGER", "REJECTED")
    );

    $("hrApprove").addEventListener(
        "click",
        () => reviewSelected("HR", "APPROVED")
    );

    $("hrReject").addEventListener(
        "click",
        () => reviewSelected("HR", "REJECTED")
    );

    $("applyAdjustment").addEventListener(
        "click",
        applySelected
    );

    loadProposals().catch(error => {
        showError(error.message);
    });
});
