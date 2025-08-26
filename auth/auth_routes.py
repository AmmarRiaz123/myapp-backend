from flask import Blueprint, request, jsonify
from .cognito_config import CognitoClient
from .token_validator import require_auth
from auth.utils import get_secret_hash
from jose import jwt


auth_bp = Blueprint('auth', __name__)
cognito = CognitoClient()


def error_response(message, status=400):
    return jsonify({'success': False, 'message': message}), status


def get_user_friendly_error(error_msg):
    if "InvalidParameterException" in error_msg and "Invalid phone number format" in error_msg:
        return 'Phone number format is invalid. Please use international format, e.g. +1234567890'
    if "UsernameExistsException" in error_msg:
        return 'An account with this username/email already exists.'
    if "CodeMismatchException" in error_msg:
        return 'Invalid verification code. Please check and try again.'
    if "ExpiredCodeException" in error_msg:
        return 'Verification code has expired. Please request a new one.'
    if "NotAuthorizedException" in error_msg and "Incorrect username or password" in error_msg:
        return 'Incorrect username or password.'
    if "UserNotFoundException" in error_msg:
        return 'No account found with the provided information.'
    if "LimitExceededException" in error_msg:
        return 'Attempt limit exceeded, please try again later.'
    if "InvalidPasswordException" in error_msg:
        return 'Password does not meet requirements.'
    # Add more mappings as needed
    return error_msg


@auth_bp.route('/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        username = data.get('username')
        phone_number = data.get('phone_number')
        address = data.get('address')
        name = data.get('name')

        # Require all fields
        if not all([email, password, username, phone_number, address, name]):
            return error_response('Missing required fields')

        # ✅ Call Cognito with all fields
        result = cognito.sign_up(
            email=email,
            password=password,
            username=username,
            phone_number=phone_number,
            address=address,
            name=name
        )

        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Please check your email for verification code'
            }), 201

        error_msg = get_user_friendly_error(result['error'])
        return error_response(error_msg)

    except Exception as e:
        return error_response(str(e), 500)


@auth_bp.route('/verify', methods=['POST'])
def verify():
    try:
        data = request.get_json()
        email = data.get('username')
        code = data.get('code')

        if not all([email, code]):
            return error_response('Missing required fields')

        result = cognito.confirm_sign_up(email, code)
        if result['success']:
            return jsonify({'success': True, 'message': 'Email verified successfully'})
        error_msg = get_user_friendly_error(result['error'])
        return error_response(error_msg)

    except Exception as e:
        return error_response(str(e), 500)


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    identifier = data.get('email') or data.get('username')
    password = data.get('password')

    result = cognito.initiate_auth(identifier, password)
    if result['success']:
        auth_result = result['data']['AuthenticationResult']

        # ✅ Decode ID token to extract username/email
        id_token = auth_result.get('IdToken')
        claims = jwt.get_unverified_claims(id_token)
        username = claims.get("cognito:username") or claims.get("email")

        print("Cognito username (from IdToken):", username)

        return jsonify({
            'success': True,
            'tokens': {
                'access_token': auth_result['AccessToken'],
                'refresh_token': auth_result.get('RefreshToken'),
                'id_token': id_token,
                'username': username  # ✅ always return a valid username
            }
        })

    return error_response(result['error'], 401)
    
@auth_bp.route('/refresh', methods=['OPTIONS'])
def refresh_options():
    # Let Flask-CORS attach headers
    return ('', 204)


@auth_bp.route('/refresh', methods=['POST'])
def refresh_token_route():
    try:
        data = request.get_json()
        refresh_token = data.get('refresh_token')
        username = data.get('username')

        if not refresh_token or not username:
            return error_response('Missing refresh token or username')

        result = cognito.refresh_token(refresh_token, username)

        if result['success']:
            auth_result = result['data']['AuthenticationResult']
            print("Received refresh request for username:", username)
            print("Returning new AccessToken:", auth_result['AccessToken'][:20] + "...")
            return jsonify({
                'success': True,
                'tokens': {
                    'access_token': auth_result['AccessToken'],
                    'id_token': auth_result.get('IdToken')
                }
            })

        error_msg = get_user_friendly_error(result['error'])
        return error_response(error_msg, 401)

    except Exception as e:
        return error_response(str(e), 500)





@auth_bp.route('/logout', methods=['POST'])
@require_auth
def logout():
    try:
        data = request.get_json()
        access_token = data.get('access_token')

        if not access_token:
            return error_response('Missing access token')

        result = cognito.global_sign_out(access_token)
        if result['success']:
            return jsonify({'success': True, 'message': 'Logged out successfully'})
        error_msg = get_user_friendly_error(result['error'])
        return error_response(error_msg, 401)

    except Exception as e:
        return error_response(str(e), 500)


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    try:
        data = request.get_json()
        email = data.get('email')

        if not email:
            return error_response('Missing email')

        result = cognito.forgot_password(email)
        if result['success']:
            return jsonify({'success': True, 'message': 'Password reset code sent to email'})
        error_msg = get_user_friendly_error(result['error'])
        return error_response(error_msg)

    except Exception as e:
        return error_response(str(e), 500)


@auth_bp.route('/confirm-forgot-password', methods=['POST'])
def confirm_forgot_password():
    try:
        data = request.get_json()
        email = data.get('email')
        code = data.get('code')
        new_password = data.get('new_password')

        if not all([email, code, new_password]):
            return error_response('Missing required fields')

        result = cognito.confirm_forgot_password(email, code, new_password)
        if result['success']:
            return jsonify({'success': True, 'message': 'Password has been reset'})
        error_msg = get_user_friendly_error(result['error'])
        return error_response(error_msg)

    except Exception as e:
        return error_response(str(e), 500)


@auth_bp.route('/resend', methods=['POST'])
def resend_confirmation():
    try:
        data = request.get_json()
        username = data.get('username')

        if not username:
            return error_response('Username is required')

        result = cognito.resend_confirmation_code(username)
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Confirmation code resent successfully',
                'delivery': result['data'].get('CodeDeliveryDetails', {})
            })
        error_msg = get_user_friendly_error(result['error'])
        return error_response(error_msg)

    except Exception as e:
        return error_response(str(e), 500)

