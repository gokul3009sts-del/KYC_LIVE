# NBAWORLD.IN Partner API — Documentation

**Base URL:** `http://localhost:5000`  
**Content-Type:** `application/json`  
**Authentication:** `Authorization: Bearer <access_token>`

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and fill environment variables
cp .env.example .env

# 3. Run MySQL migration
psql -U nbaworld -d nbaworld_db -f nbaworld_db_postgres.sql

# 4. Start the server
python run.py
# → API at http://localhost:5000
# → Swagger UI at http://localhost:5000/apidocs
```

---

## Standard Response Envelope

Every response follows this structure:

```json
{
  "success": true | false,
  "message": "Human-readable message",
  "data": { ... }       // present on success
}
```

Error responses include `"errors": [...]` for field-level validation failures.

---

## Authentication Flow

```
POST /api/register          →  create account (returns user_id)
POST /api/login             →  get access_token + refresh_token
POST /api/send-otp/email    →  (requires Bearer token)
POST /api/send-otp/phone    →  (requires Bearer token)
POST /api/verify-otp        →  channel: "email" | "phone"
POST /api/verify-otp        →  (second channel)
POST /api/kyc/submit        →  (both channels verified)
```

---

## User Management

### `POST /api/register`

Register a new agency/user account.

**Request:**
```json
{
  "agency_name":       "Sunrise Travel Agency",
  "owner_first_name":  "Ravi",
  "owner_last_name":   "Kumar",
  "email":             "ravi@sunrise.in",
  "phone":             "9876543210",
  "password":          "Secure@1234"
}
```

**Password policy:** Min 8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special character.

**Response `201`:**
```json
{
  "success": true,
  "message": "Registration successful. Please verify your email and phone.",
  "data": {
    "user_id":  "uuid",
    "email":    "ra****@sunrise.in",
    "phone":    "******3210"
  }
}
```

**Errors:** `400` validation, `409` duplicate email/phone.

---

### `POST /api/login`

**Request:**
```json
{ "email": "ravi@sunrise.in", "password": "Secure@1234" }
```

**Response `200`:**
```json
{
  "success": true,
  "data": {
    "access_token":  "eyJ...",
    "refresh_token": "eyJ...",
    "user": { "id": "...", "status": "pending", ... }
  }
}
```

**Errors:** `401` invalid credentials, `403` suspended account.

---

### `GET /api/users/{id}` 🔒

Get user profile. Users can only access their own; admins can access any.

**Response `200`:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "agency_name": "Sunrise Travel Agency",
    "email": "ravi@sunrise.in",
    "email_verified": true,
    "phone_verified": false,
    "status": "pending",
    "role": "user",
    "created_at": "2025-01-01T10:00:00"
  }
}
```

---

### `GET /api/users` 🔒👑 (Admin)

List all users with optional filters.

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| `status` | string | `pending`, `verified`, `kyc_submitted`, `active`, `suspended` |
| `search` | string | Searches email, agency name, phone |
| `page` | int | Default: 1 |
| `per_page` | int | Default: 20, max: 100 |

---

## OTP Workflow

### `POST /api/send-otp/email` 🔒

**Request:**
```json
{ "email": "ravi@sunrise.in" }
```

**Response `200`:**
```json
{
  "success": true,
  "message": "OTP sent to your email address.",
  "data": {
    "record_id":           "uuid",
    "channel":             "email",
    "masked_destination":  "ra****@sunrise.in",
    "expires_at":          "2025-01-01T10:05:00",
    "expiry_seconds":       300
  }
}
```

---

### `POST /api/send-otp/phone` 🔒

**Request:**
```json
{ "phone": "9876543210" }
```

---

### `POST /api/verify-otp` 🔒

**Request:**
```json
{
  "channel": "email",
  "otp":     "123456"
}
```

**Response `200`:**
```json
{
  "success": true,
  "message": "Email verified successfully.",
  "data": { "channel": "email", "verified": true }
}
```

**OTP Error codes:**

| Code | Meaning |
|------|---------|
| `NOT_FOUND` | No pending OTP exists |
| `EXPIRED` | OTP has passed its 5-minute window |
| `EXHAUSTED` | 5 wrong attempts — request a new OTP |
| `WRONG_OTP` | Incorrect code — N attempts remaining |

---

### `POST /api/resend-otp` 🔒

**Request:**
```json
{
  "channel": "phone",
  "phone":   "9876543210"
}
```

Enforces a 30-second cooldown between resends. Returns `429` if called too soon.

---

## Security

### `POST /api/auth/refresh-token` 🔒 (refresh token)

Send the **refresh token** (not the access token) in the `Authorization` header.

**Response `200`:** `{ "data": { "access_token": "eyJ..." } }`

---

### `POST /api/auth/logout` 🔒

Adds the current access token JTI to the blocklist.

---

## KYC

### `POST /api/kyc/submit` 🔒

Requires both email and phone to be verified first (`403` otherwise).

**Request:**
```json
{
  "business_type": "pvt_ltd",
  "authorised_person": {
    "first_name": "Sunita",
    "last_name":  "Kumar",
    "designation": "Director"
  },
  "address": {
    "office_address": "123 MG Road",
    "city": "Mumbai",
    "state": "Maharashtra",
    "postal": "400001"
  },
  "iata_status": "Non-IATA Travel Agent",
  "documents_submitted": ["aadhaar", "pan", "gst"]
}
```

---

## Admin Dashboard

All admin routes require `role: admin` in JWT claims.

### `GET /api/admin/users` 🔒👑

Extended user list with all filters:

| Param | Type | Example |
|-------|------|---------|
| `status` | string | `pending` |
| `email_verified` | bool | `true` |
| `phone_verified` | bool | `false` |
| `search` | string | `sunrise` |
| `page` / `per_page` | int | `1` / `20` |

---

### `GET /api/admin/logs` 🔒👑

Audit log with filters:

| Param | Values |
|-------|--------|
| `event` | `register`, `login`, `otp_sent`, `otp_verified`, `otp_failed`, `kyc_submitted`, … |
| `channel` | `email`, `phone` |
| `user_id` | UUID |

---

### `GET /api/admin/stats` 🔒👑

**Response `200`:**
```json
{
  "success": true,
  "data": {
    "users": {
      "total": 142,
      "email_verified": 98,
      "phone_verified": 91,
      "both_verified": 87,
      "by_status": { "pending": 55, "verified": 87 }
    },
    "otp": {
      "total_sent": 423,
      "verified": 310,
      "failed_attempts": 24,
      "expired": 89,
      "success_rate_pct": 73.3
    },
    "registrations_last_7_days": [
      { "date": "2025-01-01", "count": 12 },
      { "date": "2025-01-02", "count": 9 }
    ]
  }
}
```

---

### `GET /api/admin/users/{id}/otp-records` 🔒👑

Returns last 50 OTP records for a specific user.

---

## Health Check

### `GET /health`

No authentication required.

```json
{ "status": "ok", "database": "connected" }
```

Returns `503` if the database is unreachable.

---

## Legend

- 🔒 Requires `Authorization: Bearer <access_token>`
- 👑 Requires admin role

---

## Front-End Integration Guide

### 1. Registration + OTP Flow

```javascript
// Step 1: Register
const reg = await fetch('/api/register', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ agency_name, owner_first_name, ... })
});
const { data: { user_id } } = await reg.json();

// Step 2: Login to get tokens
const auth = await fetch('/api/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, password })
});
const { data: { access_token, refresh_token } } = await auth.json();

// Store tokens
localStorage.setItem('access_token', access_token);

// Step 3: Send OTPs
const headers = {
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${access_token}`
};
await fetch('/api/send-otp/email', { method: 'POST', headers, body: JSON.stringify({ email }) });
await fetch('/api/send-otp/phone', { method: 'POST', headers, body: JSON.stringify({ phone }) });

// Step 4: Verify OTPs
await fetch('/api/verify-otp', {
  method: 'POST', headers,
  body: JSON.stringify({ channel: 'email', otp: emailOtpInput })
});
await fetch('/api/verify-otp', {
  method: 'POST', headers,
  body: JSON.stringify({ channel: 'phone', otp: phoneOtpInput })
});

// Step 5: Submit KYC
await fetch('/api/kyc/submit', {
  method: 'POST', headers,
  body: JSON.stringify({ business_type, authorised_person, address, ... })
});
```

### 2. Token Refresh Pattern

```javascript
async function apiFetch(url, options = {}) {
  let token = localStorage.getItem('access_token');
  const resp = await fetch(url, {
    ...options,
    headers: { ...options.headers, 'Authorization': `Bearer ${token}` }
  });

  if (resp.status === 401) {
    // Try to refresh
    const refresh = await fetch('/api/auth/refresh-token', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${localStorage.getItem('refresh_token')}` }
    });
    if (refresh.ok) {
      const { data } = await refresh.json();
      localStorage.setItem('access_token', data.access_token);
      // Retry original request
      return fetch(url, {
        ...options,
        headers: { ...options.headers, 'Authorization': `Bearer ${data.access_token}` }
      });
    } else {
      // Force re-login
      window.location.href = '/login';
    }
  }
  return resp;
}
```

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | ✅ | Flask secret key |
| `JWT_SECRET_KEY` | ✅ | JWT signing secret |
| `DB_HOST/PORT/NAME/USER/PASSWORD` | ✅ | MySQL credentials |
| `SMTP_HOST/PORT/USER/PASSWORD` | For email OTP | Gmail / SMTP relay |
| `TWILIO_ACCOUNT_SID/AUTH_TOKEN/PHONE_NUMBER` | For SMS OTP | Twilio credentials |
| `OTP_EXPIRY_SECONDS` | No | Default: 300 |
| `OTP_MAX_ATTEMPTS` | No | Default: 5 |
| `OTP_RESEND_COOLDOWN_SECONDS` | No | Default: 30 |
