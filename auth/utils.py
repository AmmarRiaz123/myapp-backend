import hmac
import hashlib
import base64
import os

def get_secret_hash(username: str) -> str:
    client_id = os.getenv("COGNITO_CLIENT_ID")
    client_secret = os.getenv("COGNITO_CLIENT_SECRET")

    message = username + client_id
    dig = hmac.new(
        str(client_secret).encode("utf-8"),
        msg=message.encode("utf-8"),
        digestmod=hashlib.sha256
    ).digest()

    return base64.b64encode(dig).decode()
