"""Service d'envoi email via SMTP (Gmail App Password).

Si `smtp_password` est vide, on log le HTML au lieu d'envoyer (mode test).
"""
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, html_body: str, text_body: str | None = None) -> dict:
    """Envoie un email HTML via SMTP STARTTLS.

    Retourne : {"status": "sent"|"logged"|"error", "message": str}.
    Mode test si smtp_password est vide → log du HTML.
    """
    s = get_settings()

    if not s.smtp_password:
        logger.warning(
            f"📧 [MODE TEST] SMTP_PASSWORD non configuré. Email non envoyé.\n"
            f"  To: {to}\n  Subject: {subject}\n"
            f"  HTML body ({len(html_body)} chars) :\n{html_body[:2000]}"
            f"{'...' if len(html_body) > 2000 else ''}"
        )
        return {"status": "logged", "message": "Mode test : HTML logué, pas d'envoi réel."}

    if not (s.smtp_user and s.smtp_host and s.smtp_port):
        logger.error("SMTP config incomplète (host/port/user manquants)")
        return {"status": "error", "message": "Configuration SMTP incomplète"}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((s.newsletter_from_name, s.smtp_user))
    msg["To"] = to

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(s.smtp_user, s.smtp_password)
            server.sendmail(s.smtp_user, [to], msg.as_string())
        logger.info(f"📧 Email envoyé à {to} ({subject})")
        return {"status": "sent", "message": f"Envoyé à {to}"}
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP auth failed : {e}. Vérifiez que SMTP_PASSWORD est un App Password Gmail.")
        return {"status": "error", "message": "Échec authentification SMTP (App Password invalide)"}
    except Exception as e:
        logger.error(f"SMTP send error : {type(e).__name__}: {e}")
        return {"status": "error", "message": f"{type(e).__name__}: {e}"}
