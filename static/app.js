const list = document.querySelector("#candidateList");
const detail = document.querySelector("#detailPanel");
const dialog = document.querySelector("#candidateDialog");
const form = document.querySelector("#candidateForm");
const toast = document.querySelector("#toast");
let candidates = [];
let selectedId = null;

function notify(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 2600);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) }
  });
  if (!response.ok) {
    const payload = await response.json();
    const detail = Array.isArray(payload.detail)
      ? payload.detail.map(item => item.msg).join(", ")
      : payload.detail;
    throw new Error(detail || "Request failed");
  }
  return response.json();
}

function escapeHtml(value) {
  const node = document.createElement("div");
  node.textContent = value;
  return node.innerHTML;
}

function updateMetrics() {
  document.querySelector("#metricQueue").textContent = candidates.filter(c => c.status === "pending_review").length;
  document.querySelector("#metricReviewed").textContent = candidates.filter(c => ["approved", "rejected", "outreach_drafted"].includes(c.status)).length;
  document.querySelector("#metricOutreach").textContent = candidates.filter(c => c.status === "outreach_drafted").length;
}

function renderList() {
  if (!candidates.length) {
    list.innerHTML = '<div class="empty-state"><div><h3>Queue is clear</h3><p>Add the synthetic demo candidate to begin.</p></div></div>';
    return;
  }
  list.innerHTML = candidates.map(candidate => `
    <button class="candidate-row ${candidate.id === selectedId ? "active" : ""}" data-id="${candidate.id}">
      <h3>${escapeHtml(candidate.name)}</h3><span class="score">${candidate.scorecard.overall}</span>
      <p>${escapeHtml(candidate.role)}</p><span class="status">${candidate.status.replaceAll("_", " ")}</span>
    </button>`).join("");
  list.querySelectorAll("button").forEach(button => button.addEventListener("click", () => selectCandidate(button.dataset.id)));
}

function renderDetail(candidate) {
  const dimensions = candidate.scorecard.dimensions.map(item => `
    <div class="dimension">
      <div class="dimension-head"><span>${escapeHtml(item.name.replaceAll("_", " "))}</span><span>${item.score}</span></div>
      <div class="bar"><i style="width:${item.score}%"></i></div>
      <p>${escapeHtml(item.rationale)}${item.evidence.length ? ` Evidence: “${escapeHtml(item.evidence[0])}”` : ""}</p>
    </div>`).join("");
  const pendingActions = candidate.status === "pending_review" ? `
    <div class="actions"><button class="primary-button" id="approve">Approve for outreach</button><button class="reject-button" id="reject">Reject</button></div>` : "";
  const approvedAction = candidate.status === "approved" ? '<div class="actions"><button class="primary-button" id="draft">Draft personalized outreach →</button></div>' : "";
  const outreach = candidate.outreach ? `<div class="outreach"><strong>${escapeHtml(candidate.outreach.subject)}</strong>${escapeHtml(candidate.outreach.body)}</div>` : "";
  detail.innerHTML = `
    <div class="detail-header"><div><p class="eyebrow">EVIDENCE REVIEW</p><h2>${escapeHtml(candidate.name)}</h2><p class="meta">${escapeHtml(candidate.role)} · ${escapeHtml(candidate.source)}</p></div><div class="large-score">${candidate.scorecard.overall}</div></div>
    <div class="notice"><b>Decision support, not decision automation.</b> The score uses job-relevant resume evidence only. A named reviewer must approve or reject every candidate.</div>
    <div class="dimensions">${dimensions}</div>${pendingActions}${approvedAction}${outreach}`;
  document.querySelector("#approve")?.addEventListener("click", () => review("approve"));
  document.querySelector("#reject")?.addEventListener("click", () => review("reject"));
  document.querySelector("#draft")?.addEventListener("click", draftOutreach);
}

async function loadCandidates() {
  candidates = await api("/api/candidates");
  updateMetrics();
  renderList();
  if (selectedId) {
    const selected = candidates.find(candidate => candidate.id === selectedId);
    if (selected) renderDetail(selected);
  }
}

async function selectCandidate(id) {
  selectedId = id;
  renderList();
  renderDetail(await api(`/api/candidates/${id}`));
}

async function review(decision) {
  const candidate = await api(`/api/candidates/${selectedId}/review`, {
    method: "POST",
    body: JSON.stringify({ decision, reviewer: "Portfolio Reviewer", notes: "Reviewed resume evidence and score rationale." })
  });
  notify(`Human decision recorded: ${decision}`);
  await loadCandidates();
  renderDetail(candidate);
}

async function draftOutreach() {
  const candidate = await api(`/api/candidates/${selectedId}/outreach`, { method: "POST" });
  notify("Outreach drafted — not sent");
  await loadCandidates();
  renderDetail(candidate);
}

document.querySelector("#newCandidate").addEventListener("click", () => dialog.showModal());
document.querySelector("#closeDialog").addEventListener("click", () => dialog.close());
document.querySelector("#refresh").addEventListener("click", loadCandidates);
form.addEventListener("submit", async event => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(form));
  try {
    const candidate = await api("/api/candidates", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify(payload)
    });
    dialog.close();
    notify("Resume redacted, extracted, and scored");
    await loadCandidates();
    await selectCandidate(candidate.id);
  } catch (error) { notify(error.message); }
});

loadCandidates().catch(error => notify(error.message));
