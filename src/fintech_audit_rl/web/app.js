const $ = (id) => document.getElementById(id);
let state = null;
let activeTab = "ledger";

const actionLabel = (action) => {
  const raw = action?.action || action?.type || "unknown";
  return raw.replaceAll("_", " ");
};

function fmt(value) {
  return JSON.stringify(value, null, 2);
}

function renderMetrics(score) {
  $("m-f1").textContent = score.f1;
  $("m-reward").textContent = score.reward;
  $("m-steps").textContent = score.steps;
  $("m-counts").textContent = `${score.tp} / ${score.fp} / ${score.fn}`;
}

function selectStep(index) {
  const event = state.trajectory[index];
  document.querySelectorAll(".timeline-item").forEach((item, i) => item.classList.toggle("active", i === index));
  $("step-title").textContent = `Шаг ${event.step}: ${actionLabel(event.action)}`;
  $("step-state").textContent = event.terminated ? "TERMINATED" : event.truncated ? "TRUNCATED" : "PUBLIC";
  $("step-content").textContent = fmt({ action: event.action, observation: event.observation, visible_reward: event.reward, terminated: event.terminated, truncated: event.truncated });
}

function renderTimeline(events) {
  const root = $("timeline"); root.innerHTML = "";
  events.forEach((event, index) => {
    const item = document.createElement("button"); item.className = "timeline-item";
    item.innerHTML = `<span class="step-number">${event.step}</span><span><span class="action-name">${actionLabel(event.action)}</span><span class="action-meta">${event.terminated ? "Финальный ответ отправлен" : "Публичное действие worker"}</span></span><span class="step-result">${event.terminated ? "DONE" : "OK"}</span>`;
    item.addEventListener("click", () => selectStep(index)); root.appendChild(item);
  });
  if (events.length) selectStep(events.length - 1);
}

function table(records, columns) {
  if (!records.length) return `<p class="json-view">Нет записей.</p>`;
  const head = columns.map((c) => `<th>${c}</th>`).join("");
  const body = records.map((row) => `<tr>${columns.map((c) => `<td>${row[c] ?? "—"}</td>`).join("")}</tr>`).join("");
  return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

function renderData() {
  const root = $("data-view");
  if (activeTab === "ledger") root.innerHTML = table(state.ledger, ["row_id","timestamp","account","debit_minor","credit_minor","currency","role","invoice_id","payment_id"]);
  if (activeTab === "invoices") root.innerHTML = table(state.documents.invoices, ["invoice_id","entity_id","issued_at","due_at","currency","total_minor"]);
  if (activeTab === "payments") root.innerHTML = table(state.documents.payments, ["payment_id","timestamp","currency","amount_minor","kind"]);
  if (activeTab === "manifest") root.innerHTML = `<pre class="json-view">${fmt(state.manifest)}</pre>`;
}

document.querySelectorAll("[data-tab]").forEach((button) => button.addEventListener("click", () => {
  activeTab = button.dataset.tab;
  document.querySelectorAll("[data-tab]").forEach((item) => item.classList.toggle("active", item === button));
  renderData();
}));

$("run").addEventListener("click", async () => {
  const button = $("run"); button.disabled = true; button.textContent = "Выполняется…";
  $("empty").classList.add("hidden"); $("results").classList.add("hidden"); $("loading").classList.remove("hidden");
  try {
    const response = await fetch("/api/run", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({scenario: $("scenario").value, policy: $("policy").value, seed: Number($("seed").value), policy_seed: 0}) });
    const payload = await response.json(); if (!response.ok) throw new Error(payload.error || "Run failed");
    state = payload; renderMetrics(state.score); renderTimeline(state.trajectory); renderData();
    $("episode-badge").textContent = `${state.scenario.toUpperCase()} · ${state.policy}`;
    $("results").classList.remove("hidden");
  } catch (error) {
    $("empty").classList.remove("hidden"); $("empty").querySelector("h2").textContent = "Запуск не выполнен";
    $("empty").querySelector("p").textContent = error.message; $("empty").querySelector("p").classList.add("error");
  } finally {
    $("loading").classList.add("hidden"); button.disabled = false; button.textContent = "Запустить расследование";
  }
});
