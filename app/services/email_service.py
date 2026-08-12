"""
services/email_service.py — Send OTP emails via SMTP.
"""
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.config import config

logger = logging.getLogger(__name__)


def send_otp_email(to_email: str, otp: str, agency_name: str = "") -> bool:
    """
    Send an OTP verification email.
    Returns True on success, False on failure.

    In development (FLASK_ENV=development) with no SMTP credentials
    configured, the OTP is printed to the terminal so local testing needs
    no live mail account.

    In production, missing credentials are a configuration error, not a
    fallback path — the OTP is never printed anywhere, and this returns
    False so the caller can rely on the WhatsApp channel instead.
    """
    if not config.SMTP_USER or not config.SMTP_PASSWORD:
        if config.DEBUG:
            print(f"\n{'='*45}")
            print(f"  EMAIL OTP  →  {to_email}")
            print(f"  CODE       →  {otp}")
            print(f"{'='*45}\n")
            return True
        logger.error(
            "Email OTP not sent to %s — SMTP_USER/SMTP_PASSWORD are not "
            "configured. Set FLASK_ENV=production only once SMTP is set up.",
            to_email,
        )
        return False

    subject = "Your NBAWORLD.IN Verification Code"
    html_body = _build_otp_email_html(otp, agency_name)
    plain_body = f"Your NBAWORLD.IN verification code is: {otp}\nValid for 5 minutes."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.EMAIL_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(config.SMTP_USER, to_email, msg.as_string())
        logger.info("OTP email sent to %s", to_email)
        return True
    except Exception as exc:
        logger.error("Failed to send OTP email to %s: %s", to_email, exc)
        return False


def _build_otp_email_html(otp: str, agency_name: str) -> str:
    greeting = f"Hello, {agency_name}!" if agency_name else "Hello!"
    digits = "".join(
        f'<span style="display:inline-block;width:40px;height:48px;line-height:48px;'
        f'text-align:center;border:2px solid #1B4FD8;border-radius:8px;'
        f'font-size:24px;font-weight:800;color:#0D1F3C;margin:0 4px;">{d}</span>'
        for d in otp
    )
    return f"""
<!DOCTYPE html><html><head><meta charset="UTF-8"/></head>
<body style="font-family:Inter,Arial,sans-serif;background:#F4F6FB;margin:0;padding:32px">
  <div style="max-width:520px;margin:0 auto;background:#fff;border-radius:16px;
              overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)">
    <div style="background:linear-gradient(135deg,#0D1F3C,#1B4FD8);padding:24px 32px;
                color:#fff;font-size:22px;font-weight:700">
      NBAWORLD.IN Partner Portal
    </div>
    <div style="padding:32px">
      <p style="font-size:16px;color:#1A2540;margin-bottom:8px">{greeting}</p>
      <p style="color:#5C6A85;margin-bottom:24px">
        Use the code below to verify your email address.
        This code expires in <strong>5 minutes</strong>.
      </p>
      <div style="text-align:center;margin:28px 0">{digits}</div>
      <p style="color:#5C6A85;font-size:13px;margin-top:24px">
        If you did not request this, please ignore this email.
      </p>
    </div>
    <div style="background:#F4F6FB;padding:16px 32px;text-align:center;
                color:#8A94B0;font-size:12px">
      © 2025 NBAWORLD.IN · B2B Travel Partner Portal
    </div>
  </div>
</body></html>
"""


def send_kyc_confirmation_email(to_email: str, agency_name: str, first_name: str) -> bool:
    """Send KYC submission confirmation email to the agency."""
    subject = "KYC Submitted Successfully — NBAWORLD.IN"

    html_body = f"""
<!DOCTYPE html><html><head><meta charset="UTF-8"/></head>
<body style="font-family:Inter,Arial,sans-serif;background:#F4F6FB;margin:0;padding:32px">
  <div style="max-width:540px;margin:0 auto;background:#fff;border-radius:16px;
              overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)">
    <div style="background:linear-gradient(135deg,#0D1F3C,#1B4FD8);padding:24px 32px;
                color:#fff;font-size:22px;font-weight:700">
      NBAWORLD.IN Partner Portal
    </div>
    <div style="padding:32px">
      <p style="font-size:16px;color:#1A2540;margin-bottom:8px">Dear {first_name},</p>
      <p style="color:#5C6A85;margin-bottom:20px">
        Thank you! Your KYC documents for <strong>{agency_name}</strong> have been
        successfully submitted to NBAWORLD.IN.
      </p>
      <div style="background:#F0FDF4;border:1px solid #86EFAC;border-radius:10px;
                  padding:16px 20px;margin-bottom:20px">
        <div style="color:#166534;font-weight:700;font-size:15px">✅ Submission Confirmed</div>
        <div style="color:#15803D;font-size:13px;margin-top:4px">
          Our team will review your documents within 2–3 business days.
          You will receive another email once your account is approved.
        </div>
      </div>
      <p style="color:#5C6A85;font-size:13px">
        If you have any questions, contact us at
        <a href="mailto:agents@nbaworld.in" style="color:#1B4FD8">agents@nbaworld.in</a>
      </p>
    </div>
    <div style="background:#F4F6FB;padding:16px 32px;text-align:center;
                color:#8A94B0;font-size:12px">
      © 2025 NBAWORLD.IN · B2B Travel Partner Portal
    </div>
  </div>
</body></html>"""

    plain_body = (
        f"Dear {first_name},\n\n"
        f"Your KYC documents for {agency_name} have been successfully submitted.\n"
        f"Our team will review within 2-3 business days.\n\n"
        f"Questions? Email agents@nbaworld.in\n\n— NBAWORLD.IN"
    )

    if not config.SMTP_USER or not config.SMTP_PASSWORD:
        if config.DEBUG:
            print(f"\n{'='*45}")
            print(f"  KYC CONFIRMATION EMAIL  →  {to_email}")
            print(f"  Agency: {agency_name}")
            print(f"{'='*45}\n")
            return True
        logger.error(
            "KYC confirmation email not sent to %s — SMTP not configured.",
            to_email,
        )
        return False

    try:
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        import smtplib
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = config.EMAIL_FROM
        msg["To"]      = to_email
        msg.attach(MIMEText(plain_body, "plain"))
        msg.attach(MIMEText(html_body,  "html"))
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as s:
            s.ehlo(); s.starttls()
            s.login(config.SMTP_USER, config.SMTP_PASSWORD)
            s.sendmail(config.SMTP_USER, to_email, msg.as_string())
        logger.info("KYC confirmation email sent to %s", to_email)
        return True
    except Exception as exc:
        logger.error("Failed to send KYC confirmation email to %s: %s", to_email, exc)
        return False