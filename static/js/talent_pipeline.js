document.addEventListener("DOMContentLoaded", () => {
    document
        .querySelectorAll(".kanban-card")
        .forEach(card => {
            card.addEventListener("click", () => {
                const url = card.dataset.url;

                if (url) {
                    window.location.href = url;
                }
            });
        });
});

// ---------------------------------------------------------
// Card click -> navigate (existing behavior)
// ---------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".kanban-card").forEach(card => {
        card.addEventListener("click", () => {
            // don't navigate if the click was part of a drag
            if (card.dataset.wasDragged === "true") {
                card.dataset.wasDragged = "false";
                return;
            }
            const url = card.dataset.url;
            if (url) {
                window.location.href = url;
            }
        });
    });

    setupDragAndDrop();
    setupScheduleFormSubmit();
});

// ---------------------------------------------------------
// Intercept the schedule form submit: POST via fetch, then
// reload the current Talent Pipeline page (instead of
// following the backend's redirect to hr_interviews).
// ---------------------------------------------------------
function setupScheduleFormSubmit() {
    const form = document.getElementById("scheduleForm");
    if (!form) return;

    form.addEventListener("submit", (e) => {
        e.preventDefault();

        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = "Scheduling...";
        }

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
                        alert("Couldn't schedule the interview. Please try again.");
                    });
                }
            })
            .catch((err) => {
                console.error(err);
                alert("Network error while scheduling the interview.");
            })
            .finally(() => {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = "Confirm & Schedule";
                }
            });
    });
}

// ---------------------------------------------------------
// Drag and drop between columns
// ---------------------------------------------------------
let draggedCard = null;
let sourceColumnTitle = null;

function setupDragAndDrop() {
    document.querySelectorAll(".kanban-card").forEach(card => {
        card.addEventListener("dragstart", (e) => {
            draggedCard = card;
            sourceColumnTitle = card.closest(".kanban-col-body")?.dataset.columnTitle || null;
            card.classList.add("dragging");
            e.dataTransfer.effectAllowed = "move";
        });

        card.addEventListener("dragend", () => {
            card.classList.remove("dragging");
        });
    });

    document.querySelectorAll(".kanban-col-body").forEach(colBody => {
        colBody.addEventListener("dragover", (e) => {
            e.preventDefault();
            colBody.classList.add("drop-target");
        });

        colBody.addEventListener("dragleave", () => {
            colBody.classList.remove("drop-target");
        });

        colBody.addEventListener("drop", (e) => {
            e.preventDefault();
            colBody.classList.remove("drop-target");

            if (!draggedCard) return;

            const targetColumnTitle = colBody.dataset.columnTitle;
            handleCardDrop(draggedCard, sourceColumnTitle, targetColumnTitle);

            draggedCard = null;
            sourceColumnTitle = null;
        });
    });
}

function handleCardDrop(card, sourceTitle, targetTitle) {
    // Only one transition is wired up right now: Hackathon Submitted -> Interview Scheduled
    if (sourceTitle === "Hackathon Submitted" && targetTitle === "Interview Scheduled") {
        const status = card.dataset.status;

        if (status !== "passed_stage4") {
            alert(
                "This candidate isn't eligible for interview scheduling yet. " +
                "They need at least 2 reviews with an average score above the cutoff."
            );
            return;
        }

        openScheduleModal(card);
        return;
    }
     // Telephonic (HR) -> Interview Scheduled (AI Interview flow skips hackathon entirely)
    if (sourceTitle === "Telephonic (HR)" && targetTitle === "Interview Scheduled") {
        const status = card.dataset.status;
        const flow = card.dataset.flow;
        
        if (flow !== "ai_interview_flow" || status !== "accepted") {
            alert(
                "Only accepted AI Interview flow candidates can be scheduled directly from here. " +
                "AI Hackathon flow candidates need to submit and pass hackathon review first."
            );
            return;
        }
        openScheduleModal(card);
        return;
    }
    // Everything else: not wired up yet, so block with a clear message.
    if (sourceTitle !== targetTitle) {
        alert("Dragging between these columns isn't supported yet. Please use the candidate detail page.");
    }
}

// ---------------------------------------------------------
// Schedule Interview modal
// ---------------------------------------------------------
function openScheduleModal(card) {
    const modal = document.getElementById("scheduleModal");
    document.getElementById("modalCandidateId").value = card.dataset.candidateId;
    document.getElementById("modalCandidateName").textContent = card.dataset.candidateName;

    // reset form state
    const form = document.getElementById("scheduleForm");
    form.reset();
    document.querySelectorAll('#scheduleForm input[name="interviewer_username[]"]').forEach(cb => cb.checked = false);
    const label = form.querySelector(".multi-select-label");
    if (label) label.textContent = "Select interviewer";

    modal.hidden = false;
}

function closeScheduleModal() {
    document.getElementById("scheduleModal").hidden = true;
}

// ---------------------------------------------------------
// Multi-select interviewer dropdown (same behavior as hr_interviews.html)
// ---------------------------------------------------------
function toggleDropdown(trigger) {
    const dropdown = trigger.nextElementSibling;
    dropdown.classList.toggle("open");
    document.addEventListener("click", function close(e) {
        if (!trigger.parentElement.contains(e.target)) {
            dropdown.classList.remove("open");
            document.removeEventListener("click", close);
        }
    });
}

function closeMultiSelectDropdown(wrapper) {
    const dropdown = wrapper.querySelector(".multi-select-dropdown");
    if (dropdown) {
        dropdown.classList.remove("open");
    }
}

function updateLabel(wrapper) {
    const checked = wrapper.querySelectorAll('input[name="interviewer_username[]"]:checked');
    const autoBox = wrapper.querySelector('input[value=""]');
    const label = wrapper.querySelector(".multi-select-label");
    if (autoBox && autoBox.checked) {
        label.textContent = "Auto-suggest interviewer";
    } else if (checked.length === 0) {
        label.textContent = "Select interviewer";
    } else if (checked.length === 1) {
        label.textContent = checked[0].closest("label").textContent.trim();
    } else {
        label.textContent = `${checked.length} interviewers selected`;
    }
}

function handleAutoSuggest(checkbox) {
    if (checkbox.checked) {
        const namedBoxes = checkbox.closest(".multi-select-dropdown")
            .querySelectorAll('input[name="interviewer_username[]"]');
        namedBoxes.forEach(cb => cb.checked = false);
        checkbox.checked = false;
        findMatchingInterviewer();
    }
    updateLabel(checkbox.closest(".multi-select-wrapper"));
}

function findMatchingInterviewer() {
    const candidateId = document.getElementById("modalCandidateId").value;

    fetch(`/hrone/ai-interview/hr/suggest-interviewers/${candidateId}`)
        .then(res => res.json())
        .then(data => showMatchModal(data.matches))
        .catch(() => showMatchModal([]));
}

function showMatchModal(matches) {
    const list = document.getElementById("matchList");
    if (matches.length === 0) {
        list.innerHTML = '<p style="color:#888;">No matching senior found based on skills. Please select manually from the dropdown.</p>';
    } else {
        list.innerHTML = matches.map((m) => `
            <div style="border:1px solid #ddd;border-radius:4px;padding:12px;margin-bottom:10px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <strong>${m.full_name}</strong>
                    <span style="background:#e8f4e8;color:#2d6a2d;padding:2px 8px;border-radius:10px;font-size:0.82rem;">
                        ${m.pct}% match
                    </span>
                </div>
                <div style="margin-top:6px;font-size:0.82rem;color:#555;">
                    Matched skills: ${m.matched.join(", ")}
                </div>
                <button type="button" onclick="selectInterviewer('${m.username}')"
                    style="margin-top:8px;background:#1f2937;color:#fff;border:none;padding:6px 14px;
                    border-radius:4px;cursor:pointer;font-size:0.82rem;">
                    Select
                </button>
            </div>`).join("");
    }
    document.getElementById("matchModal").hidden = false;
}

function selectInterviewer(username) {
    document.querySelectorAll('#scheduleForm input[name="interviewer_username[]"]').forEach(cb => cb.checked = false);
    const target = document.querySelector(`#scheduleForm input[value="${username}"]`);
    if (target) {
        target.checked = true;
        updateLabel(target.closest(".multi-select-wrapper"));
    }
    document.getElementById("matchModal").hidden = true;
}