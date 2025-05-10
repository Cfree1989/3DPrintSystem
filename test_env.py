import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve email-related environment variables
email_address = os.getenv('EMAIL_ADDRESS')
email_password = os.getenv('EMAIL_PASSWORD')
smtp_server = os.getenv('SMTP_SERVER')
smtp_port = os.getenv('SMTP_PORT')
secret_key = os.getenv('SECRET_KEY')

print("--- Environment Variable Test ---")
print(f"SECRET_KEY: {secret_key}")
print(f"EMAIL_ADDRESS: {email_address}")
print(f"EMAIL_PASSWORD: {'********' if email_password else None}") # Mask password for security
print(f"SMTP_SERVER: {smtp_server}")
print(f"SMTP_PORT: {smtp_port}")

if all([email_address, email_password, smtp_server, smtp_port, secret_key]):
    print("\nAll required environment variables seem to be loaded.")
else:
    print("\nOne or more environment variables are missing. Please check your .env file.")

print("---------------------------------") 