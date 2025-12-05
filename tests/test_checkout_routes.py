import pytest
import json
from unittest.mock import patch, MagicMock
import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from checkout_routes import checkout_bp

@pytest.fixture
def app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.register_blueprint(checkout_bp)
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def mock_db():
    with patch('checkout_routes.get_db_connection') as mock:
        conn_mock = MagicMock()
        cur_mock = MagicMock()
        mock.return_value = (conn_mock, cur_mock)
        
        # Setup cursor return values for typical scenarios
        cur_mock.fetchone.return_value = {'id': 1, 'total_price': 99.99, 'name': 'Test User', 
                                         'email': 'test@example.com', 'phone': '1234567890',
                                         'street_address': '123 Test St', 'city': 'Test City', 
                                         'province_name': 'Test Province'}
        cur_mock.fetchall.return_value = [
            {'product_id': 1, 'quantity': 2, 'price': 25.00, 'name': 'Test Product 1'},
            {'product_id': 2, 'quantity': 1, 'price': 49.99, 'name': 'Test Product 2'}
        ]
        
        yield conn_mock, cur_mock

@pytest.fixture
def mock_email_functions():
    with patch('checkout_routes.validate_email_config') as mock_validate:
        with patch('checkout_routes.send_order_confirmation_email') as mock_customer:
            with patch('checkout_routes.send_admin_order_notification') as mock_admin:
                mock_validate.return_value = True
                mock_customer.return_value = True
                mock_admin.return_value = True
                yield mock_validate, mock_customer, mock_admin

@pytest.fixture  
def mock_verify_token():
    with patch('auth.token_validator.verify_token') as mock:
        mock.return_value = {
            'sub': 'auth-user-123',
            'email': 'authuser@example.com',
            'name': 'Auth User',
            'phone_number': '9876543210'
        }
        yield mock

@pytest.fixture
def mock_require_auth():
    with patch('checkout_routes.require_auth') as mock_auth:
        def auth_decorator(f):
            def wrapper(*args, **kwargs):
                # Mock request.user for authenticated endpoints
                from flask import g
                g.user = {'sub': 'auth-user-123'}
                return f(*args, **kwargs)
            return wrapper
        mock_auth.side_effect = auth_decorator
        yield mock_auth

class TestCheckoutRoutes:
    
    def test_guest_checkout_success(self, client, mock_db, mock_email_functions):
        """Test successful guest checkout with all required data."""
        conn_mock, cur_mock = mock_db
        mock_validate, mock_customer, mock_admin = mock_email_functions
        
        # Mock session for guest user
        with client.session_transaction() as sess:
            sess['guest_id'] = 'guest-123'
        
        checkout_data = {
            'customer_info': {
                'name': 'Guest User',
                'email': 'guest@example.com',
                'phone': '1234567890'
            },
            'shipping_address': {
                'province_id': 1,
                'city': 'Test City',
                'street_address': '123 Test St',
                'postal_code': '12345'
            }
        }
        
        response = client.post('/checkout', 
                             data=json.dumps(checkout_data),
                             content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'order_id' in data
        assert data['customer_type'] == 'guest'
        assert 'Confirmation email sent and admin notified' in data['message']

    def test_guest_checkout_email_failure(self, client, mock_db):
        """Test guest checkout when email sending fails."""
        conn_mock, cur_mock = mock_db
        
        with patch('checkout_routes.validate_email_config') as mock_validate:
            with patch('checkout_routes.send_order_confirmation_email') as mock_customer:
                with patch('checkout_routes.send_admin_order_notification') as mock_admin:
                    mock_validate.return_value = False  # Email config invalid
                    mock_customer.return_value = False
                    mock_admin.return_value = False
                    
                    # Mock session for guest user
                    with client.session_transaction() as sess:
                        sess['guest_id'] = 'guest-123'
                    
                    checkout_data = {
                        'customer_info': {
                            'name': 'Guest User',
                            'email': 'guest@example.com',
                            'phone': '1234567890'
                        },
                        'shipping_address': {
                            'province_id': 1,
                            'city': 'Test City',
                            'street_address': '123 Test St',
                            'postal_code': '12345'
                        }
                    }
                    
                    response = client.post('/checkout', 
                                         data=json.dumps(checkout_data),
                                         content_type='application/json')
                    
                    assert response.status_code == 200
                    data = json.loads(response.data)
                    assert data['success'] is True
                    assert 'failed to send any emails' in data['message']

    def test_authenticated_checkout_success(self, client, mock_db, mock_email_functions, mock_verify_token):
        """Test successful authenticated user checkout."""
        conn_mock, cur_mock = mock_db
        
        checkout_data = {
            'customer_info': {
                'name': 'Auth User Updated',
                'phone': '9999999999'
            },
            'shipping_address': {
                'province_id': 1,
                'city': 'Auth City',
                'street_address': '456 Auth St',
                'postal_code': '67890'
            }
        }
        
        headers = {'Authorization': 'Bearer valid-token-123'}
        response = client.post('/checkout', 
                             data=json.dumps(checkout_data),
                             content_type='application/json',
                             headers=headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['customer_type'] == 'authenticated'

    def test_checkout_empty_cart(self, client, mock_db):
        """Test checkout with empty cart."""
        conn_mock, cur_mock = mock_db
        cur_mock.fetchall.return_value = []  # Empty cart
        
        with client.session_transaction() as sess:
            sess['guest_id'] = 'guest-123'
        
        checkout_data = {
            'customer_info': {
                'name': 'Guest User',
                'email': 'guest@example.com', 
                'phone': '1234567890'
            },
            'shipping_address': {
                'province_id': 1,
                'city': 'Test City',
                'street_address': '123 Test St'
            }
        }
        
        response = client.post('/checkout',
                             data=json.dumps(checkout_data),
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'Cart is empty' in data['message']

    def test_guest_checkout_missing_info(self, client, mock_db):
        """Test guest checkout with missing customer info."""
        conn_mock, cur_mock = mock_db
        
        with client.session_transaction() as sess:
            sess['guest_id'] = 'guest-123'
        
        checkout_data = {
            'customer_info': {
                'name': 'Guest User',
                # Missing email and phone
            },
            'shipping_address': {
                'province_id': 1,
                'city': 'Test City',
                'street_address': '123 Test St'
            }
        }
        
        response = client.post('/checkout',
                             data=json.dumps(checkout_data),
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'Guest customer info missing' in data['message']

    def test_complete_checkout_success(self, client, mock_db, mock_email_functions):
        """Test successful checkout completion."""
        conn_mock, cur_mock = mock_db
        
        with client.session_transaction() as sess:
            sess['guest_id'] = 'guest-123'
        
        complete_data = {
            'order_id': 1,
            'payment_method': 'payfast'
        }
        
        response = client.post('/checkout/complete',
                             data=json.dumps(complete_data),
                             content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['order_id'] == 1

    def test_complete_checkout_missing_order_id(self, client):
        """Test checkout completion with missing order ID."""
        complete_data = {
            'payment_method': 'payfast'
        }
        
        response = client.post('/checkout/complete',
                             data=json.dumps(complete_data),
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'Order ID required' in data['message']

    def test_complete_checkout_order_not_found(self, client, mock_db):
        """Test checkout completion with non-existent order."""
        conn_mock, cur_mock = mock_db
        cur_mock.fetchone.return_value = None  # Order not found
        
        complete_data = {
            'order_id': 999,
            'payment_method': 'payfast'
        }
        
        response = client.post('/checkout/complete',
                             data=json.dumps(complete_data),
                             content_type='application/json')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'Order not found' in data['message']

    def test_merge_guest_cart_no_auth(self, client):
        """Test cart merge without authentication returns 401."""
        merge_data = {'guest_id': 'guest-123'}
        
        headers = {'Authorization': 'Bearer invalid-token'}
        response = client.post('/checkout/cart-merge',
                             data=json.dumps(merge_data),
                             content_type='application/json',
                             headers=headers)
        
        # Should return 401 since auth will fail
        assert response.status_code == 401

    def test_convert_guest_to_auth_no_auth(self, client):
        """Test guest to auth conversion without authentication returns 401."""
        conversion_data = {'guest_id': 'guest-123'}
        
        headers = {'Authorization': 'Bearer invalid-token'}
        response = client.post('/checkout/guest-to-auth',
                             data=json.dumps(conversion_data),
                             content_type='application/json',
                             headers=headers)
        
        # Should return 401 since auth will fail
        assert response.status_code == 401

    def test_checkout_handles_database_error_gracefully(self, client):
        """Test checkout handles database errors gracefully."""
        with patch('checkout_routes.get_db_connection') as mock_db:
            # Make the connection succeed but cursor operations fail
            conn_mock = MagicMock()
            cur_mock = MagicMock()
            mock_db.return_value = (conn_mock, cur_mock)
            
            # Make the first query (getting cart) fail
            cur_mock.fetchall.side_effect = Exception("Database query failed")
            
            with client.session_transaction() as sess:
                sess['guest_id'] = 'guest-123'
            
            checkout_data = {
                'customer_info': {
                    'name': 'Guest User',
                    'email': 'guest@example.com',
                    'phone': '1234567890'
                },
                'shipping_address': {
                    'province_id': 1,
                    'city': 'Test City',
                    'street_address': '123 Test St'
                }
            }
            
            response = client.post('/checkout',
                                 data=json.dumps(checkout_data),
                                 content_type='application/json')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert data['success'] is False

if __name__ == '__main__':
    pytest.main([__file__])
