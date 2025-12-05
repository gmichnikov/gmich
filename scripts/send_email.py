#!/usr/bin/env python3
"""
Command-line script to send an email using Mailgun API.
Requires environment variables:
- MAILGUN_API_KEY: Your Mailgun API key
- MAILGUN_SANDBOX_DOMAIN: Your Mailgun sandbox domain
- CUSTOM_DOMAIN: Your custom domain
- SENDER_EMAIL: Your sender email address
- ADMIN_EMAIL: Recipient email address
"""

import os
import sys
import requests
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
# Look for .env file in the project root (parent directory of scripts/)
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()  # Fallback to default behavior


def send_simple_message():
    """Send an email using Mailgun API."""
    api_key = os.getenv('MAILGUN_API_KEY', '').strip()
    domain = os.getenv('MAILGUN_SANDBOX_DOMAIN', '').strip()
    admin_email = os.getenv('ADMIN_EMAIL', '').strip()
    custom_domain = os.getenv('CUSTOM_DOMAIN', '').strip()
    sender_email = os.getenv('SENDER_EMAIL', '').strip()

    
    if not api_key:
        print("Error: MAILGUN_API_KEY environment variable is not set", file=sys.stderr)
        sys.exit(1)
    
    if not domain:
        print("Error: MAILGUN_SANDBOX_DOMAIN environment variable is not set", file=sys.stderr)
        sys.exit(1)
    
    if not admin_email:
        print("Error: ADMIN_EMAIL environment variable is not set", file=sys.stderr)
        sys.exit(1)

    if not custom_domain:
        print("Error: CUSTOM_DOMAIN environment variable is not set", file=sys.stderr)
        sys.exit(1)

    if not sender_email:
        print("Error: SENDER_EMAIL environment variable is not set", file=sys.stderr)
        sys.exit(1)
    
    try:
        response = requests.post(
            f"https://api.mailgun.net/v3/{custom_domain}/messages",
            auth=("api", api_key),
            data={
                "from": f"Greg <{sender_email}>",
                "to": admin_email,
                "subject": "Hello from Custom Domain",
                "text": "Congratulations Again, you just sent an email with Mailgun using a custom domain! You are truly awesome!"
            }
        )
        
        response.raise_for_status()
        print("Email sent successfully using a custom domain!")
        return response
        
    except requests.exceptions.RequestException as e:
        print(f"Error sending email: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    send_simple_message()

