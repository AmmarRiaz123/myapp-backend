import pytest
from flask import Flask, jsonify
from checkout_routes import checkout_bp
import json
from unittest.mock import Mock

@pytest.fixture
def app():
    app = Flask(__name__)
    app.secret_key = 'test-secret-key-for-sessions'
    app.register_blueprint(checkout_bp)
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def mock_db(monkeypatch):
    class MockCursor:
        def __init__(self):
            self.executed = []
            self._fetchall_response = []
            self._fetchone_response = None
            self._fetchone_responses = []
            self._call_count = 0

        def execute(self, query, params=None):
            self.executed.append((query.strip(), params))

        def fetchall(self):
            return self._fetchall_response

        def fetchone(self):
            if self._fetchone_responses and self._call_count < len(self._fetchone_responses):
                result = self._fetchone_responses[self._call_count]
                self._call_count += 1
                return result
            return self._fetchone_response

        def close(self):
            pass

    class MockConn:
        def __init__(self):
            self.cur = MockCursor()
            self.committed = False
            self.rolled_back = False

        def cursor(self, cursor_factory=None):
            return self.cur

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

        def close(self):
            pass

    mock_conn = MockConn()
    
    def mock_get_db(cursor_factory=None):
        return mock_conn, mock_conn.cur

    monkeypatch.setattr('checkout_routes.get_db_connection', mock_get_db)
    return mock_conn

def test_merge_guest_cart_success(client, mock_db, monkeypatch):
    # Mock the entire token validation process
    def mock_verify_token(token, expected_use=None):
        return {'sub': 'auth-user-123'}
    
    def mock_extract_token():
        return 'fake-token'
    
    # Mock both the validator functions and the decorator
    monkeypatch.setattr('auth.token_validator.verify_token', mock_verify_token)
    monkeypatch.setattr('auth.token_validator.extract_token', mock_extract_token)
    
    # Setup mock responses for cart merging
    mock_db.cur._fetchone_responses = [
        (1,),   # guest cart exists
        (2,),   # user cart exists
    ]
    
    response = client.post('/checkout/cart-merge', 
                          json={'guest_id': 'guest-123'},
                          headers={'Authorization': 'Bearer fake-token'})
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True

def test_initiate_checkout_guest_success(client, mock_db):
    # Setup mock cart items
    mock_db.cur._fetchall_response = [
        {'product_id': 1, 'quantity': 2, 'name': 'Test Product', 'price': 19.99}
    ]
    
    # Setup mock responses for order creation
    mock_db.cur._fetchone_responses = [
        {'id': 1},  # customer creation
        {'id': 1},  # shipping address creation
        {'id': 123}  # order creation
    ]
    
    response = client.post('/checkout/initiate', json={
        'customer_info': {
            'name': 'John Doe',
            'email': 'john@test.com', 
            'phone': '+123456789'
        },
        'shipping_address': {
            'province_id': 1,
            'city': 'Test City',
            'street_address': '123 Test St'
        }
    })
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['customer_type'] == 'guest'
    assert 'order_id' in data

def test_initiate_checkout_missing_customer_info(client, mock_db):
    # Setup mock cart items
    mock_db.cur._fetchall_response = [
        {'product_id': 1, 'quantity': 2, 'name': 'Test Product', 'price': 19.99}
    ]
    
    response = client.post('/checkout/initiate', json={
        'shipping_address': {
            'province_id': 1,
            'city': 'Test City',
            'street_address': '123 Test St'
        }
    })
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'Customer information required' in data['message']

def test_initiate_checkout_empty_cart(client, mock_db):
    # Setup empty cart
    mock_db.cur._fetchall_response = []
    
    response = client.post('/checkout/initiate', json={
        'customer_info': {
            'name': 'John Doe',
            'email': 'john@test.com',
            'phone': '+123456789'
        },
        'shipping_address': {
            'province_id': 1,
            'city': 'Test City', 
            'street_address': '123 Test St'
        }
    })
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'Cart is empty' in data['message']

def test_complete_checkout_success(client, mock_db):
    # Setup mock order verification
    mock_db.cur._fetchone_response = (123, 199.99)  # order exists
    
    response = client.post('/checkout/complete', json={
        'order_id': 123,
        'payment_method': 'payfast'
    })
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['order_id'] == 123

def test_complete_checkout_missing_order_id(client):
    response = client.post('/checkout/complete', json={
        'payment_method': 'payfast'
    })
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'Order ID required' in data['message']

def test_complete_checkout_order_not_found(client, mock_db):
    # Setup mock - order not found
    mock_db.cur._fetchone_response = None
    
    response = client.post('/checkout/complete', json={
        'order_id': 999,
        'payment_method': 'payfast'
    })
    
    assert response.status_code == 404
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'Order not found' in data['message']

def test_guest_to_auth_conversion(client, mock_db, monkeypatch):
    # Mock the entire token validation process
    def mock_verify_token(token, expected_use=None):
        return {'sub': 'auth-user-123'}
    
    def mock_extract_token():
        return 'fake-token'
    
    # Mock merge_guest_cart to return a proper Flask response
    def mock_merge_guest_cart_func():
        from flask import jsonify
        return jsonify({'success': True, 'message': 'Cart merged successfully'}), 200
    
    monkeypatch.setattr('auth.token_validator.verify_token', mock_verify_token)
    monkeypatch.setattr('auth.token_validator.extract_token', mock_extract_token)
    
    # Mock the function in checkout_routes module
    monkeypatch.setattr('checkout_routes.merge_guest_cart', mock_merge_guest_cart_func)
    
    response = client.post('/checkout/guest-to-auth',
                          json={'guest_id': 'guest-123'},
                          headers={'Authorization': 'Bearer fake-token'})
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'converted to authenticated checkout' in data['message']

def test_merge_guest_cart_missing_guest_id(client, monkeypatch):
    # Mock authentication
    def mock_verify_token(token, expected_use=None):
        return {'sub': 'auth-user-123'}
    
    def mock_extract_token():
        return 'fake-token'
    
    monkeypatch.setattr('auth.token_validator.verify_token', mock_verify_token)
    monkeypatch.setattr('auth.token_validator.extract_token', mock_extract_token)
    
    response = client.post('/checkout/cart-merge',
                          json={},  # Missing guest_id
                          headers={'Authorization': 'Bearer fake-token'})
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'Guest ID required' in data['message']

def test_initiate_checkout_missing_shipping_address(client, mock_db):
    # Setup mock cart items
    mock_db.cur._fetchall_response = [
        {'product_id': 1, 'quantity': 2, 'name': 'Test Product', 'price': 19.99}
    ]
    
    response = client.post('/checkout/initiate', json={
        'customer_info': {
            'name': 'John Doe',
            'email': 'john@test.com',
            'phone': '+123456789'
        }
        # Missing shipping_address
    })
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'Complete shipping address required' in data['message']
