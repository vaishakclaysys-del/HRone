// Read server-provided config if present
var __inboxConfigEl = document.getElementById('inboxConfig');
if (__inboxConfigEl) {
    window.AI_ML_DEPARTMENT = __inboxConfigEl.dataset.aiMlDepartment || 'AI / ML';
}

document.addEventListener("DOMContentLoaded", () => {
    // ensure default if not provided
    if (!window.AI_ML_DEPARTMENT) window.AI_ML_DEPARTMENT = 'AI / ML';
    setupDropzone();
    setupBulkUploadButton();
    setupUploadFormSubmit();
    setupTabs();
    setupSearchAndDeptFilter();
    setupRowSelection();
    setupRowActions();
    setupRouteModal();
    setupMergeModal();
});

/* ---------------------------------------------------------
   Dropzone
   --------------------------------------------------------- */
function setupDropzone() {
    const dropzone = document.getElementById("dropzone");
    const input = document.getElementById("resumeInput");
    const form = document.getElementById("uploadForm");
    if (!dropzone || !input || !form) return;

    dropzone.addEventListener("click", () => input.click());

    input.addEventListener("change", () => {
        if (input.files.length > 0) form.requestSubmit();
    });

    ["dragenter", "dragover"].forEach(evt => {
        dropzone.addEventListener(evt, (e) => {
            e.preventDefault();
            dropzone.classList.add("is-dragover");
        });
    });

    ["dragleave", "drop"].forEach(evt => {
        dropzone.addEventListener(evt, (e) => {
            e.preventDefault();
            dropzone.classList.remove("is-dragover");
        });
    });

    dropzone.addEventListener("drop", (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            input.files = files;
            form.requestSubmit();
        }
    });
}

function setupBulkUploadButton() {
    const btn = document.getElementById("bulkUploadBtn");
    const input = document.getElementById("resumeInput");
    if (btn && input) {
        btn.addEventListener("click", () => input.click());
    }
}

function showLoader(title) {
    const loader = document.getElementById("loader");
    const titleEl = document.getElementById("loaderTitle");
    if (titleEl) titleEl.textContent = title || "Uploading resumes...";
    if (loader) loader.classList.add("is-active");
}

function hideLoader() {
    const loader = document.getElementById("loader");
    if (loader) loader.classList.remove("is-active");
}

/* ---------------------------------------------------------
   Intercept the upload form submit: POST via fetch, then
   reload the current Resume Inbox page instead of following
   the backend's redirect to hr_candidates.
   --------------------------------------------------------- */
function setupUploadFormSubmit() {
    const form = document.getElementById("uploadForm");
    if (!form) return;

    form.addEventListener("submit", (e) => {
        e.preventDefault();
        showLoader();

        const formData = new FormData(form);

        fetch(form.action, {
            method: "POST",
            body: formData,
        })
            .then((response) => {
                if (response.ok || response.redirected) {
                    window.location.reload();
                } else {
                    return response.text().then((text) => {
                        console.error(text);
                        hideLoader();
                        alert("Couldn't upload the resumes. Please try again.");
                    });
                }
            })
            .catch((err) => {
                console.error(err);
                hideLoader();
                alert("Network error while uploading resumes.");
            });
    });
}

/* ---------------------------------------------------------
   Tabs / search / department filter
   --------------------------------------------------------- */
function setupTabs() {
    const tabs = document.querySelectorAll(".inbox-tab");
    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(t => t.classList.remove("is-active"));
            tab.classList.add("is-active");
            applyFilters();
        });
    });
}

function setupSearchAndDeptFilter() {
    const search = document.getElementById("candidateSearch");
    const dept = document.getElementById("departmentFilter");
    if (search) search.addEventListener("input", applyFilters);
    if (dept) dept.addEventListener("change", applyFilters);
}

function applyFilters() {
    const activeTab = document.querySelector(".inbox-tab.is-active");
    const filter = activeTab ? activeTab.dataset.filter : "all";
    const search = (document.getElementById("candidateSearch")?.value || "").toLowerCase().trim();
    const dept = document.getElementById("departmentFilter")?.value || "";

    document.querySelectorAll(".candidate-row").forEach(row => {
        const matchesTab = filter === "all" || row.dataset.status === filter;
        const matchesSearch =
            !search ||
            row.dataset.name.includes(search) ||
            row.dataset.role.includes(search);
        const matchesDept = !dept || row.dataset.department === dept;

        row.classList.toggle("is-hidden", !(matchesTab && matchesSearch && matchesDept));
    });
}

/* ---------------------------------------------------------
   Row click -> detail panel
   --------------------------------------------------------- */
function setupRowSelection() {
    document.querySelectorAll(".candidate-row").forEach(row => {
        row.addEventListener("click", (e) => {
            if (e.target.closest(".action-pill")) return;

            document.querySelectorAll(".candidate-row").forEach(r => r.classList.remove("is-selected"));
            row.classList.add("is-selected");

            renderDetailPanel(row.dataset);
        });
    });
}

function renderDetailPanel(data) {
    document.getElementById("detailEmpty").style.display = "none";
    const content = document.getElementById("detailContent");
    content.style.display = "block";

    document.getElementById("detailAvatar").textContent = (data.name || "??").slice(0, 2).toUpperCase();
    document.getElementById("detailName").textContent = data.name || "—";
    document.getElementById("detailEmail").textContent = data.email || "—";

    const statusBadge = document.getElementById("detailStatusBadge");
    statusBadge.textContent = (data.status || "new").toUpperCase();
    statusBadge.className = "badge mt-2 " + statusBadgeClass(data.status);

    document.getElementById("detailMatch").textContent = data.match ? `${data.match}%` : "—";
    document.getElementById("detailExperience").textContent = data.experience ? `${data.experience} yrs` : "—";
    document.getElementById("detailRole").textContent = data.roleFull || "—";

    const skillsEl = document.getElementById("detailSkills");
    skillsEl.innerHTML = "";
    (data.skills || "")
        .split(",")
        .map(s => s.trim())
        .filter(Boolean)
        .forEach(skill => {
            const span = document.createElement("span");
            span.className = "badge badge-muted";
            span.textContent = skill;
            skillsEl.appendChild(span);
        });
}

function statusBadgeClass(status) {
    switch (status) {
        case "routed": return "badge-success";
        case "rejected": return "badge-danger";
        default: return "badge-info";
    }
}

/* ---------------------------------------------------------
   Shortlist -> open route modal
   Reject -> confirm, then submit directly to hr_decision
   --------------------------------------------------------- */
function setupRowActions() {
    document.querySelectorAll(".action-pill").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const action = btn.dataset.action;
            const row = btn.closest(".candidate-row");
            const decisionUrl = row.dataset.decisionUrl;

            if (action === "shortlist") {
                openRouteModal({
                    candidateId: btn.dataset.candidateId,
                    candidateName: btn.dataset.candidateName,
                    department: btn.dataset.department,
                    decisionUrl,
                });
                return;
            }

            if (action === "reject") {
                if (!confirm(`Reject ${btn.dataset.candidateName}?`)) return;
                submitDecision(decisionUrl, { decision: "reject", notes: "Rejected via Resume Inbox" });
            }
        });
    });
}

/* ---------------------------------------------------------
   Submit an hr_decision POST via fetch and reload the current
   page — never a real form submit, since hr_decision redirects
   to the candidate detail page and we don't want to navigate
   away from the Resume Inbox.
   --------------------------------------------------------- */
function submitDecision(url, fields) {
    const formData = new FormData();
    Object.entries(fields).forEach(([key, value]) => formData.append(key, value));
    submitDecisionFormData(url, formData, "Saving decision...");
}

function submitDecisionFormData(url, formData, loadingMessage) {
    showLoader(loadingMessage);

    fetch(url, {
        method: "POST",
        body: formData,
    })
        .then((response) => {
            if (response.ok || response.redirected) {
                window.location.reload();
            } else {
                return response.text().then((text) => {
                    console.error(text);
                    hideLoader();
                    alert("Couldn't save this decision. Please try again.");
                });
            }
        })
        .catch((err) => {
            console.error(err);
            hideLoader();
            alert("Network error while saving the decision.");
        });
}

/* ---------------------------------------------------------
   Route selection modal (Shortlist -> pick flow)
   AI/ML department: choice of Hackathon or Interview flow.
   All other departments: Interview flow only, no choice shown.
   --------------------------------------------------------- */
function setupRouteModal() {
    const cancelBtn = document.getElementById("cancelRoute");
    const modal = document.getElementById("routeModal");
    const form = document.getElementById("routeForm");

    if (cancelBtn && modal) {
        cancelBtn.addEventListener("click", () => modal.setAttribute("hidden", ""));
    }

    if (form) {
        form.addEventListener("submit", (e) => {
            e.preventDefault();
            const formData = new FormData(form);
            const url = form.action;
            modal.setAttribute("hidden", "");
            submitDecisionFormData(url, formData, "Routing candidate...");
        });
    }
}

function openRouteModal({ candidateId, candidateName, department, decisionUrl }) {
    const modal = document.getElementById("routeModal");
    const form = document.getElementById("routeForm");
    const optionsWrap = document.getElementById("routeOptions");
    const nameEl = document.getElementById("routeCandidateName");

    nameEl.textContent = candidateName;
    form.action = decisionUrl;

    const isAiMl = department === window.AI_ML_DEPARTMENT;

    optionsWrap.innerHTML = "";

    if (isAiMl) {
        optionsWrap.innerHTML = `
            <label style="display:flex; align-items:center; gap:8px;">
                <input type="radio" name="flow" value="ai_hackathon_flow" checked required />
                AI Hackathon Flow
            </label>
            <label style="display:flex; align-items:center; gap:8px;">
                <input type="radio" name="flow" value="ai_interview_flow" required />
                AI Interview Flow
            </label>
        `;
    } else {
        optionsWrap.innerHTML = `
            <p class="muted" style="margin:0;">
                This department only routes through the <b>AI Interview Flow</b>.
            </p>
            <input type="hidden" name="flow" value="ai_interview_flow" />
        `;
    }

    modal.removeAttribute("hidden");
}

/* ---------------------------------------------------------
   Merge Excel modal
   --------------------------------------------------------- */
function setupMergeModal() {
    const openLink = document.getElementById("openMergeExcel");
    const closeBtn = document.getElementById("closeMergeModal");
    const modal = document.getElementById("mergeModal");
    if (!modal) return;

    if (openLink) openLink.addEventListener("click", () => modal.removeAttribute("hidden"));
    if (closeBtn) closeBtn.addEventListener("click", () => modal.setAttribute("hidden", ""));
    modal.addEventListener("click", (e) => {
        if (e.target === modal) modal.setAttribute("hidden", "");
    });
}