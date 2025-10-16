import smtplib
from email.message import EmailMessage
from decouple import config

msg = EmailMessage()
msg["From"] = "sys@seatraders.com"
msg["To"] = "skliros@quantsuite.io"
msg["Subject"] = "Test Email"
msg.set_content("This is a test.")

SMTP_HOST="93.174.121.86"
SMTP_PORT=25
SMTP_USER=config("SMTP_USER")
SMTP_PASS=config("SMTP_PASS")

with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
    smtp.ehlo()
    smtp.starttls()
    smtp.ehlo()
    smtp.login(SMTP_USER, SMTP_PASS)
    smtp.send_message(msg)

print("OK: Email sent successfully!")

