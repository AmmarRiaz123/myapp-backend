import os
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from auth.utils import get_secret_hash  # <-- import your helper

load_dotenv() 

class CognitoClient:
    def __init__(self):
        self.client = boto3.client(
            'cognito-idp',
            region_name=os.environ.get('AWS_REGION'),
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
        )
        self.user_pool_id = os.environ.get('COGNITO_USER_POOL_ID')
        self.client_id = os.environ.get('COGNITO_CLIENT_ID')

    def sign_up(self, email, password, username, phone_number, address, name):
        try:
            response = self.client.sign_up(
                ClientId=self.client_id,
                SecretHash=get_secret_hash(username),  # ✅ must match Username
                Username=username,  # ✅ must NOT be email
                Password=password,
                UserAttributes=[
                    {'Name': 'email', 'Value': email},
                    {'Name': 'phone_number', 'Value': phone_number},
                    {'Name': 'address', 'Value': address},
                    {'Name': 'name', 'Value': name}
                ]
            )
            return {'success': True, 'data': response}
        except ClientError as e:
            return {'success': False, 'error': str(e)}

    def confirm_sign_up(self, username, code):
        try:
            response = self.client.confirm_sign_up(
                ClientId=self.client_id,
                SecretHash=get_secret_hash(username),  # ✅ required
                Username=username,
                ConfirmationCode=code
            )
            return {'success': True, 'data': response}
        except ClientError as e:
            return {'success': False, 'error': str(e)}

    def initiate_auth(self, username, password):
        try:
            response = self.client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': username,
                    'PASSWORD': password,
                    'SECRET_HASH': get_secret_hash(username)  # ✅ required
                }
            )
            return {'success': True, 'data': response}
        except ClientError as e:
            return {'success': False, 'error': str(e)}

    def refresh_token(self, refresh_token, username):
        try:
            response = self.client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='REFRESH_TOKEN_AUTH',
                AuthParameters={
                    'REFRESH_TOKEN': refresh_token,
                    'SECRET_HASH': get_secret_hash(username)  # ✅ required
                }
            )
            return {'success': True, 'data': response}
        except ClientError as e:
            return {'success': False, 'error': str(e)}

    def forgot_password(self, email):
        try:
            response = self.client.forgot_password(
                ClientId=self.client_id,
                SecretHash=get_secret_hash(email),  # ✅ required
                Username=email
            )
            return {'success': True, 'data': response}
        except ClientError as e:
            return {'success': False, 'error': str(e)}

    def confirm_forgot_password(self, email, code, new_password):
        try:
            response = self.client.confirm_forgot_password(
                ClientId=self.client_id,
                SecretHash=get_secret_hash(email),  # ✅ required
                Username=email,
                ConfirmationCode=code,
                Password=new_password
            )
            return {'success': True, 'data': response}
        except ClientError as e:
            return {'success': False, 'error': str(e)}
        
    def resend_confirmation_code(self, username):
        try:
            response = self.client.resend_confirmation_code(
                ClientId=self.client_id,
                SecretHash=get_secret_hash(username),  # ✅ required
                Username=username
            )
            return {'success': True, 'data': response}
        except ClientError as e:
            return {'success': False, 'error': str(e)}

