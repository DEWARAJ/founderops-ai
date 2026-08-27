"""Send the signed synthetic Retell event to a local FounderOps server."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "retell_call_analyzed.json"


def main() -> None:
    api_key = os.environ["RETELL_WEBHOOK_API_KEY"]
    url = os.getenv(
        "RETELL_WEBHOOK_URL",
        "http://127.0.0.1:8000/api/integrations/retell/webhook",
    )
    body = FIXTURE.read_bytes()
    timestamp = str(int(time.time() * 1000))
    digest = hmac.new(
        api_key.encode("utf-8"),
        body + timestamp.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Retell-Signature": f"v={timestamp},d={digest}",
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        print(response.read().decode("utf-8"))


if __name__ == "__main__":
    main()
