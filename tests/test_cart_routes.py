import pytest
from flask import Flask
from cart_routes import cart_bp
import json

@pytest.fixture
def app():
    app = Flask(__name__)
    app.register_blueprint(cart_bp)
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def mock_db(monkeypatch):
    class MockCursor:
        def __init__(self):
            self.executed = []
            self._fetchone_responses = []  # Changed: list to handle multiple calls
            self._fetchall_response = []
            self._call_count = 0

        def execute(self, query, params=None):
            self.executed.append((query.strip(), params))

        def fetchone(self):
            if self._call_count < len(self._fetchone_responses):
                result = self._fetchone_responses[self._call_count]
                self._call_count += 1
                return result
            return None

        def fetchall(self):
            return self._fetchall_response

        def close(self):
            pass

    class MockConn:
        def __init__(self):
            self.cur = MockCursor()
            self.committed = False
            self.rolled_back = False

        def cursor(self):
            return self.cur

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

        def close(self):
            pass

    mock_conn = MockConn()
    
    def mock_get_db():
        return mock_conn, mock_conn.cur

    monkeypatch.setattr('cart_routes.get_db_connection', mock_get_db)
    return mock_conn

def test_add_to_cart_success_new_user(client, mock_db):
    # Setup: no existing cart first, then return cart_id when creating new cart
    mock_db.cur._fetchone_responses = [
        None,  # No existing cart
        (1,),  # New cart created with id=1
        None   # No existing cart item
    ]
    
    response = client.post('/cart/add', json={
        'product_id': 1,
        'quantity': 2,
        'user_id': 'test-user-123'
    })
    
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'Item added to cart' in data['message']
    assert mock_db.committed is True

def test_add_to_cart_missing_product_id(client):
    response = client.post('/cart/add', json={
        'quantity': 2,
        'user_id': 'test-user-123'
    })
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'Product ID is required' in data['message']

def test_add_to_cart_missing_user_id(client):
    response = client.post('/cart/add', json={
        'product_id': 1,
        'quantity': 2
    })
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'User ID is required' in data['message']

def test_get_cart_success(client, mock_db):
    # Setup mock cart items
    mock_db.cur._fetchall_response = [
        (1, 'Test Product', 'TEST001', 2, 1),
        (2, 'Another Product', 'TEST002', 1, 2)
    ]
    
    response = client.get('/cart?user_id=test-user-123')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert len(data['items']) == 2
    assert data['items'][0]['name'] == 'Test Product'
    assert data['items'][0]['quantity'] == 2

def test_get_cart_missing_user_id(client):
    response = client.get('/cart')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'User ID is required' in data['message']

def test_get_cart_empty(client, mock_db):
    # Setup empty cart
    mock_db.cur._fetchall_response = []
    
    response = client.get('/cart?user_id=test-user-123')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert len(data['items']) == 0
