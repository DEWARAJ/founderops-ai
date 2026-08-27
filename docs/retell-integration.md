# Retell voice intake

FounderOps accepts Retell `call_analyzed` events at:

```text
POST /api/integrations/retell/webhook
```

The integration follows Retell's official [webhook event](https://docs.retellai.com/features/webhook-overview), [signature verification](https://docs.retellai.com/features/secure-webhook), and [call transcript](https://docs.retellai.com/api-references/get-call) contracts.

## Security and evidence boundaries

1. The endpoint reads at most 1 MB and verifies `X-Retell-Signature` against the untouched request body.
2. Signatures outside Retell's five-minute window are rejected to reduce replay risk.
3. Only `call_analyzed` creates candidate evidence; other events receive a successful acknowledgement.
4. `call_id` and event type form an idempotency key, so Retell retries cannot create duplicates.
5. Only transcript turns whose role is `user` are scored. Agent prompts are excluded to prevent scripted keywords from contaminating evidence.
6. Candidate speech is PII-redacted before extraction. Raw transcripts and recording URLs are never persisted.
7. The result always enters `pending_review`; the voice integration cannot approve, reject, or send outreach.

## Configure Retell

Set the server secret to the API key designated for webhook verification:

```bash
export RETELL_WEBHOOK_API_KEY="your_retell_webhook_api_key"
uv run founderops
```

On Windows PowerShell:

```powershell
$env:RETELL_WEBHOOK_API_KEY = "your_retell_webhook_api_key"
uv run founderops
```

In the Retell dashboard, register the public HTTPS endpoint and select `call_analyzed`. Include these optional values in call metadata or dynamic variables:

```json
{
  "candidate_name": "Maya Patel",
  "target_role": "Founders Initiatives — AI Agents"
}
```

If no candidate name is supplied, FounderOps creates a non-identifying label from the final six characters of the call ID. It never falls back to the caller's phone number.

## Run the signed local fixture

With the app running and the same local secret configured:

```bash
python scripts/send_retell_fixture.py
```

The script signs `examples/retell_call_analyzed.json` exactly as Retell does. Run it twice to see the first request create one pending candidate and the second return `duplicate` with the same candidate ID.

## Production boundary

The portfolio implementation performs the default deterministic extraction within Retell's webhook response window. At higher volume—or when using a remote model—persist a minimized encrypted job and acknowledge the verified webhook before asynchronous processing. Add organization-specific consent, access controls, retention/deletion workflows, and legal review before handling real candidate calls.
