from functools import wraps
from flask import request, jsonify
import jwt
import os
import requests
from jwt.algorithms import RSAAlgorithm

# Cache keys to avoid hitting AWS for every request
_COGNITO_KEYS_CACHE = None

def get_cognito_public_keys():
    """Fetch and cache Cognito's JWKS keys."""
    global _COGNITO_KEYS_CACHE
    if _COGNITO_KEYS_CACHE:
        return _COGNITO_KEYS_CACHE

    region = os.environ.get('AWS_REGION')
    pool_id = os.environ.get('COGNITO_USER_POOL_ID')
    if not region or not pool_id:
        raise RuntimeError("AWS_REGION and COGNITO_USER_POOL_ID must be set")

    url = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json"
    response = requests.get(url)
    response.raise_for_status()
    _COGNITO_KEYS_CACHE = response.json()['keys']
    return _COGNITO_KEYS_CACHE

def verify_token(token):
    """Verify and decode a JWT token from Cognito."""
    keys = get_cognito_public_keys()
    header = jwt.get_unverified_header(token)

    try:
        key = next(k for k in keys if k['kid'] == header['kid'])
    except StopIteration:
        raise ValueError("Invalid token: key not found")

    public_key = RSAAlgorithm.from_jwk(key)

    return jwt.decode(
        token,
        public_key,
        algorithms=['RS256'],
        audience=os.environ.get('COGNITO_CLIENT_ID')
    )

def extract_token():
    """Extract Bearer token from Authorization header."""
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith("Bearer "):
        return auth_header.replace("Bearer ", "")
    return None

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = extract_token()
        if not token:
            return jsonify({'success': False, 'message': 'Token is missing'}), 401

        try:
            decoded = verify_token(token)
            request.user = decoded
            return f(*args, **kwargs)
        except Exception:
            return jsonify({'success': False, 'message': 'Invalid token'}), 401
    return decorated

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = extract_token()
        if not token:
            return jsonify({'success': False, 'message': 'Token is missing'}), 401

        try:
            decoded = verify_token(token)
            groups = decoded.get('cognito:groups', [])
            if 'admin' not in groups:
                return jsonify({'success': False, 'message': 'Admin access required'}), 403
            request.user = decoded
            return f(*args, **kwargs)
        except Exception:
            return jsonify({'success': False, 'message': 'Invalid token'}), 401
    return decorated
