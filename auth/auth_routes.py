from flask import Blueprint, request, jsonify
from .cognito_config import CognitoClient
from .token_validator import require_auth
from auth.utils import get_secret_hash


auth_bp = Blueprint('auth', __name__)
cognito = CognitoClient()


def error_response(message, status=400):
    return jsonify({'success': False, 'message': message}), status


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

        return error_response(result['error'])

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
        return error_response(result['error'])

    except Exception as e:
        return error_response(str(e), 500)


@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        # Accept username, email, or phone_number
        identifier = data.get('username') or data.get('email') or data.get('phone_number')
        password = data.get('password')

        if not identifier or not password:
            return error_response('Missing required fields')

        # Pass identifier and password to initiate_auth
        result = cognito.initiate_auth(identifier, password)
        if result['success']:
            auth_result = result['data']['AuthenticationResult']
            return jsonify({
                'success': True,
                'tokens': {
                    'access_token': auth_result['AccessToken'],
                    'refresh_token': auth_result.get('RefreshToken'),
                    'id_token': auth_result.get('IdToken')
                }
            })
        return error_response(result['error'], 401)

    except Exception as e:
        return error_response(str(e), 500)


@auth_bp.route('/refresh', methods=['POST'])
@require_auth
def refresh_token():
    try:
        data = request.get_json()
        refresh_token = data.get('refresh_token')

        if not refresh_token:
            return error_response('Missing refresh token')

        result = cognito.refresh_token(refresh_token)
        if result['success']:
            auth_result = result['data']['AuthenticationResult']
            return jsonify({
                'success': True,
                'tokens': {
                    'access_token': auth_result['AccessToken'],
                    'id_token': auth_result.get('IdToken')
                }
            })
        return error_response(result['error'], 401)

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
        return error_response(result['error'], 401)

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
        return error_response(result['error'])

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
        return error_response(result['error'])

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
        return error_response(result['error'])

    except Exception as e:
        return error_response(str(e), 500)

