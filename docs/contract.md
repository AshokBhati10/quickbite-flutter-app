# QuickBite API contract

Base path: `/api/v1`. Health probes: `GET /health/live`, `GET /health/ready`.

## Money

All money fields are integer minor units with a currency code.
Example: `total_amount_minor: 2900, currency: INR` means INR 29.00.
Totals are always computed server-side from the current menu; client
prices, customer IDs, and totals are ignored.

## State machine

```
PENDING -> PAID -> CONFIRMED -> DRIVER_ASSIGNED
PENDING -> PAYMENT_FAILED
PAID -> FAILED
CONFIRMED -> FAILED
```

`DRIVER_ASSIGNED` is successful completion. `PAYMENT_FAILED` and `FAILED`
are terminal. No backward transitions. Transitions apply under a row lock
with a version check; stale versions are rejected.

Checkout limits: at most 20 distinct items, quantity 1..20 per line,
address 8..500 chars, one restaurant per order, active items only.

## Pagination

Query `page` (≥1) and `page_size` (1..100, default 20). List shape:

```json
{"items": [], "page": 1, "page_size": 20, "total": 0}
```

## Errors

Envelope `{code, message, details, request_id}`, including validation
errors (`code: validation_error`, 422). Status codes: 401 unauthenticated
(missing/expired token), 403 wrong role, 404 unknown id or another
customer's order, 409 idempotency-key reuse with a different payload,
422 invalid input. Every response carries `X-Request-ID`.

## Idempotency

`POST /api/v1/orders` requires an `Idempotency-Key` header scoped to the
authenticated customer. The server stores a canonical request hash under a
unique `(user_id, key)` constraint together with the acceptance response.
Same key + same payload returns the stored 202 response and `Location`
with no new rows, even after processing advanced. Same key + different
payload returns 409. Concurrent identical submissions create exactly one
order. Records are retained for the assignment lifetime.

## OpenAPI

Exported from FastAPI; committed at `docs/openapi.json`. Regenerate with:

```sh
.venv/bin/python -c "
from app.api.app import app
import json
json.dump(app.openapi(), open('docs/openapi.json', 'w'), indent=2)
"
```

(run from `backend/` with `.env` configured).
