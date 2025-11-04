# PayFast Integration — Frontend Guide

This document explains how the frontend should integrate with the backend PayFast endpoints in this project.

Summary
- Backend endpoints:
  - POST /payfast/initiate — create a PayFast payment URL (backend generates signature and returns payment_url)
  - POST /payfast/callback — PayFast will POST to this endpoint (ITN). Frontend does not call this.
- Recommended flow: frontend creates order -> backend returns payment_url -> frontend redirects user to PayFast -> PayFast redirects back to frontend return_url -> backend receives ITN and updates order.payment_status.

Required environment (backend)
- PAYFAST_MERCHANT_ID (or default testing id is present)
- PAYFAST_MERCHANT_KEY (secret — never expose on frontend)
- PAYFAST_USE_SANDBOX=true (for development) or PAYFAST_URL set to sandbox/live endpoint
- PAYFAST_PASSPHRASE (optional if you set one in PayFast settings)
- DB_* env vars (backend stores m_payment_id / payment payloads and updates orders)

Key concepts
- m_payment_id: unique payment identifier. Recommended: use your backend order id (stringified). Backend will attempt to link m_payment_id to an order (orders.id or orders.m_payment_id).
- ITN (Instant Transaction Notification): PayFast sends a server-to-server POST to /payfast/callback. The backend validates the signature and updates orders.payment_status and stores the full notification.
- Sandbox: Use PayFast sandbox URL: `https://sandbox.payfast.co.za/eng/process` for testing (no real money).

Frontend responsibilities (step-by-step)
1. Create an order in your backend (recommended) and get the order id (e.g., 123).
   - Save order with status `pending`.
   - Use that id as `m_payment_id`.
2. Call backend to initiate a PayFast payment:
   - POST /payfast/initiate
   - JSON body (example):
     {
       "amount": 199.99,
       "item_name": "Order #123",
       "m_payment_id": "123",            // strongly recommended
       "email_address": "buyer@example.com",
       "return_url": "https://your-frontend.com/payment-success",
       "cancel_url": "https://your-frontend.com/payment-cancel"
     }
   - Backend returns: { "success": true, "payment_url": "https://sandbox.payfast.co.za/eng/process?..." }
3. Redirect the user to the returned payment_url.
4. After payment, PayFast will redirect the user to your provided return_url or cancel_url.
   - Note: the redirect is user-facing; the backend relies on ITN (server-to-server) for authoritative status.
5. Show a pending/processing page and either:
   - Poll the backend order status endpoint until order.payment_status == true
   - Or let the backend push a notification (not implemented by default) when it receives ITN

Important: do not rely only on the return redirect for payment confirmation — always rely on backend ITN updates.

ITN / Callback details (what PayFast will POST)
- Typical fields include: `m_payment_id`, `payment_status` (e.g., COMPLETE), `amount`, `signature`, and other PayFast fields.
- The backend validates the signature using merchant_key and optional passphrase, then:
  - Persists the raw notification in `payment_notifications` (DB)
  - Updates `orders.payment_payload`, `orders.payment_provider`, `orders.m_payment_id`
  - Sets `orders.payment_status = TRUE` on successful payments

Sandbox testing
- Set PAYFAST_USE_SANDBOX=true on backend or set PAYFAST_URL to sandbox URL.
- Use PayFast sandbox test cards and Instant EFTs (see PayFast docs).
- Verify:
  - Frontend redirect works
  - Backend receives callback at /payfast/callback (ensure the server is reachable from the public internet or use a tunnel like ngrok)
  - orders.payment_status becomes true after successful ITN
  - payment_notifications table contains the payload

Security notes
- Never expose PAYFAST_MERCHANT_KEY or passphrase to the frontend.
- Always call /payfast/initiate on the backend — it creates the signature and payment URL.
- Use HTTPS for all frontend/backend endpoints.
- Ensure your backend is reachable by PayFast (public endpoint) for ITN; sandbox will POST to the callback URL you register.

Example frontend flow (pseudo-code)
1. createOrder() -> returns orderId
2. resp = POST /payfast/initiate { amount, item_name, m_payment_id: orderId, email_address, return_url, cancel_url }
3. window.location.href = resp.payment_url
4. On return_url page show "Payment processing..." and poll GET /orders/<orderId> for status

Common pitfalls
- Using different m_payment_id values for initiate and local order — must match so backend can link ITN to the order.
- Running backend on localhost without exposing it to PayFast for ITN — use a public URL or ngrok for testing.
- Assuming redirect == payment success — always use ITN confirmation.

Helpful links
- PayFast docs / sandbox: https://developers.payfast.co.za/documentation/
- PayFast sandbox payment page: https://sandbox.payfast.co.za/eng/process

If you want, I can add a small "order status" endpoint example the frontend can poll, or a sample frontend snippet (React/JS) that implements the above flow.
