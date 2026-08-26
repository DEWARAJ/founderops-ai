# FounderOps AI

An auditable, human-in-the-loop candidate operations system built for high-ownership startup teams. It turns resume text into structured, evidence-backed signals, applies a versioned role rubric, and blocks outreach until a named reviewer makes the decision.

> This is decision-support software—not an automated hiring decision system. It does not score protected attributes, auto-reject candidates, or send messages without review.

![FounderOps AI dashboard](docs/dashboard.png)

<details>
<summary>View the privacy-aware candidate intake</summary>

![Candidate intake with synthetic data](docs/candidate-intake.png)

</details>

## Why this project exists

Fast-growing teams need more than an LLM wrapper. They need reliable workflows: privacy boundaries, explicit state transitions, idempotency, human approvals, provider fallbacks, and an audit record. FounderOps AI demonstrates that complete operating surface.

## What is implemented

- Resume PII redaction before extraction and scoring
- Deterministic offline extractor for a zero-cost, reproducible demo
- Optional OpenAI Responses API adapter with strict JSON Schema output
- Versioned, evidence-based role rubric with per-dimension explanations
- Mandatory named human approval before outreach drafting
- SQLite persistence, idempotent ingestion, and immutable audit events
- Responsive operations dashboard and documented FastAPI endpoints
- Tests covering safety gates, workflow transitions, privacy, and idempotency

## System flow

```mermaid
flowchart LR
    A[Resume intake] --> B[PII redaction]
    B --> C[Structured extraction]
    C --> D[Versioned evidence rubric]
    D --> E{Human review}
    E -->|Approve| F[Personalized draft]
    E -->|Reject| G[Close workflow]
    F --> H[Delivery adapter — disabled in demo]
    B -. no protected traits .-> D
    A --> I[(Audit log)]
    D --> I
    E --> I
    F --> I
```

## Run locally

```bash
uv sync --extra dev
uv run founderops
```

Open `http://127.0.0.1:8000`. Click **New candidate** to load the synthetic demo resume, then inspect the scorecard, approve it, and draft outreach. API documentation is at `http://127.0.0.1:8000/docs`.

The default `deterministic` provider requires no account or API key. To use the optional OpenAI adapter:

```bash
set FOUNDEROPS_PROVIDER=openai
set OPENAI_API_KEY=your_key
set OPENAI_MODEL=your_structured_output_model
uv run founderops
```

The adapter uses the Responses API, disables response storage, and sends the redacted resume—not the original—to the provider. See the official [Responses API reference](https://developers.openai.com/api/reference/resources/responses/methods/create).

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/candidates` | Redact, extract, score, and queue for review |
| `GET` | `/api/candidates` | List the active pipeline |
| `POST` | `/api/candidates/{id}/review` | Record a named approve/reject decision |
| `POST` | `/api/candidates/{id}/outreach` | Draft outreach after approval only |
| `GET` | `/api/candidates/{id}/audit` | Inspect the workflow event trail |

Use an `Idempotency-Key` header on intake requests to make client retries safe.

## Engineering decisions

- **Mock-first provider boundary:** reviewers can run the entire workflow without credentials; the LLM adapter is replaceable.
- **Evidence before score:** every dimension exposes the matched evidence and missing signals. A score without support becomes `insufficient_evidence`.
- **Human gate in the domain layer:** the API and dashboard cannot bypass approval because the workflow state machine enforces it.
- **No fake performance claims:** the repository includes functional tests, but no invented accuracy or business-impact numbers.
- **SQLite for the portfolio demo:** the repository interface isolates persistence so PostgreSQL can replace it without changing the workflow.

## Development

```bash
uv run ruff check .
uv run pytest
```

## Responsible-use boundary

FounderOps AI is designed for candidate prioritization and review assistance. Before any real deployment, add organization-specific access control, retention/deletion policy, consent and notice flows, bias evaluation with qualified counsel, encrypted secret storage, and validated integrations. A human remains accountable for every employment decision.

## License

MIT
