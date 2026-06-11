import os
import smtplib
from dotenv import load_dotenv

load_dotenv()

email = os.getenv("GMAIL_SENDER")
password = os.getenv("GMAIL_APP_PASSWORD")

print("EMAIL:", email)
print("PASSWORD LENGTH:", len(password) if password else None)

s = smtplib.SMTP("smtp.gmail.com", 587)
s.starttls()
s.login(email, password)
print("LOGIN SUCCESS")
s.quit()