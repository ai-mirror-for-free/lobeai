import requests
import random
import string
import secrets
import os
from dotenv import load_dotenv

# Configuration - adjust to your Open WebUI instance URL
load_dotenv()
SIGNUP_URL = f"{os.getenv("BASE_URL")}/api/v1/auths/signup"

def generate_random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def register_random_user():
    name = f"user_{generate_random_string()}"
    email = f"{name}@gmail.com"
    # Using a secure random password
    password = secrets.token_urlsafe(16)

    print(f"Attempting to register user: {name} ({email})")

    payload = {
        "name": name,
        "email": email,
        "password": password
    }

    try:
        response = requests.post(SIGNUP_URL, json=payload)

        if response.status_code in [200, 201, 202]:
            print(f"Successfully registered user: {name}")
            print(f"Email: {email}")
            print(f"Password: {password}")
        else:
            print(f"Failed to register user. Status code: {response.status_code}")
            print(f"Response: {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # WARNING: To run this script, ensure the `requests` library is installed:
    # pip install requests
    register_random_user()
