-- ============================================================
-- Migration 002 — Make password_hash nullable (no-password flow)
-- OTP is now 4 digits
-- ============================================================
USE nbaworld_db;

-- Allow password_hash to be NULL (passwordless OTP-only registration)
ALTER TABLE users
  MODIFY COLUMN password_hash VARCHAR(255) NULL DEFAULT NULL;

-- Add otp_token column to users for quick lookup of current valid OTP session
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS otp_verified TINYINT(1) NOT NULL DEFAULT 0
  AFTER phone_verified;

SELECT 'Migration 002 applied.' AS result;
