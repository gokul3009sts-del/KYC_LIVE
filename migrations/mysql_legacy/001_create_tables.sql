-- ============================================================
-- NBAWORLD.IN — Initial Database Migration
-- Run against MySQL 8.0+ as a privileged user
-- ============================================================

CREATE DATABASE IF NOT EXISTS nbaworld_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'nbaworld_user'@'localhost'
  IDENTIFIED BY 'CHANGE_THIS_PASSWORD';

GRANT ALL PRIVILEGES ON nbaworld_db.* TO 'nbaworld_user'@'localhost';
FLUSH PRIVILEGES;

USE nbaworld_db;

-- ── Users ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
  id                VARCHAR(36)   NOT NULL,
  agency_name       VARCHAR(255)  NOT NULL,
  owner_first_name  VARCHAR(100)  NOT NULL,
  owner_last_name   VARCHAR(100)  NOT NULL,
  email             VARCHAR(255)  NOT NULL,
  phone             VARCHAR(15)   NOT NULL,
  password_hash     VARCHAR(255)  NOT NULL,
  email_verified    TINYINT(1)    NOT NULL DEFAULT 0,
  phone_verified    TINYINT(1)    NOT NULL DEFAULT 0,
  role              ENUM('user','admin')
                    NOT NULL DEFAULT 'user',
  status            ENUM('pending','verified','kyc_submitted','active','suspended')
                    NOT NULL DEFAULT 'pending',
  kyc_data          LONGTEXT,
  created_at        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
  last_login_at     DATETIME,
  PRIMARY KEY (id),
  UNIQUE KEY uq_email (email),
  UNIQUE KEY uq_phone (phone),
  KEY idx_status (status),
  KEY idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── OTP Records ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS otp_records (
  id              VARCHAR(36)   NOT NULL,
  user_id         VARCHAR(36)   NOT NULL,
  channel         ENUM('email','phone') NOT NULL,
  destination     VARCHAR(255)  NOT NULL,
  otp_hash        VARCHAR(255)  NOT NULL,
  status          ENUM('pending','verified','expired','exhausted')
                  NOT NULL DEFAULT 'pending',
  attempts        INT           NOT NULL DEFAULT 0,
  max_attempts    INT           NOT NULL DEFAULT 5,
  expires_at      DATETIME      NOT NULL,
  verified_at     DATETIME,
  resend_count    INT           NOT NULL DEFAULT 0,
  last_resent_at  DATETIME,
  created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_user_channel (user_id, channel),
  KEY idx_status       (status),
  KEY idx_expires      (expires_at),
  CONSTRAINT fk_otp_user FOREIGN KEY (user_id)
    REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Verification Logs ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS verification_logs (
  id          VARCHAR(36)   NOT NULL,
  user_id     VARCHAR(36),
  event       ENUM(
    'register','login','logout',
    'otp_sent','otp_verified','otp_failed','otp_resent','otp_expired',
    'kyc_submitted','token_refreshed','admin_action','password_changed'
  ) NOT NULL,
  channel     VARCHAR(10),
  ip_address  VARCHAR(45),
  user_agent  VARCHAR(512),
  detail      TEXT,
  created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_user_id  (user_id),
  KEY idx_event    (event),
  KEY idx_created  (created_at),
  CONSTRAINT fk_log_user FOREIGN KEY (user_id)
    REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- Verify
-- ============================================================
SELECT 'Migration 001 applied successfully.' AS result;
SHOW TABLES;

-- ── Patch for otp_verified column (added in v2 schema) ──────
-- Run this if 001 was already applied without it:
-- ALTER TABLE users ADD COLUMN IF NOT EXISTS otp_verified TINYINT(1) NOT NULL DEFAULT 0 AFTER phone_verified;
