import os
import boto3
from botocore.exceptions import ClientError

class CognitoClient:
    def __init__(self):
        self.client = boto3.client('cognito-idp',
            region_name=os.environ.get('AWS_REGION'),
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
        )
        self.user_pool_id = os.environ.get('COGNITO_USER_POOL_ID')
        self.client_id = os.environ.get('COGNITO_CLIENT_ID')

    def sign_up(self, email, password, name):
        try:
            response = self.client.sign_up(
                ClientId=self.client_id,
                Username=email,
                Password=password,
                UserAttributes=[
                    {'Name': 'name', 'Value': name},
                    {'Name': 'email', 'Value': email}
                ]
            )
            return {'success': True, 'data': response}
        except ClientError as e:
            return {'success': False, 'error': str(e)}

    def confirm_sign_up(self, email, code):
        try:
            response = self.client.confirm_sign_up(
                ClientId=self.client_id,
                Username=email,
                ConfirmationCode=code
            )
            return {'success': True, 'data': response}
        except ClientError as e:
            return {'success': False, 'error': str(e)}

    def initiate_auth(self, email, password):
        try:
            response = self.client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': email,
                    'PASSWORD': password
                }
            )
            return {'success': True, 'data': response}
        except ClientError as e:
            return {'success': False, 'error': str(e)}

    def refresh_token(self, refresh_token):
        try:
            response = self.client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='REFRESH_TOKEN_AUTH',
                AuthParameters={
                    'REFRESH_TOKEN': refresh_token
                }
            )
            return {'success': True, 'data': response}
        except ClientError as e:
            return {'success': False, 'error': str(e)}

    def global_sign_out(self, access_token):
        try:
            response = self.client.global_sign_out(
                AccessToken=access_token
            )
            return {'success': True, 'data': response}
        except ClientError as e:
            return {'success': False, 'error': str(e)}

    def forgot_password(self, email):
        try:
            response = self.client.forgot_password(
                ClientId=self.client_id,
                Username=email
            )
            return {'success': True, 'data': response}
        except ClientError as e:
            return {'success': False, 'error': str(e)}

    def confirm_forgot_password(self, email, code, new_password):
        try:
            response = self.client.confirm_forgot_password(
                ClientId=self.client_id,
                Username=email,
                ConfirmationCode=code,
                Password=new_password
            )
            return {'success': True, 'data': response}
        except ClientError as e:
            return {'success': False, 'error': str(e)}
