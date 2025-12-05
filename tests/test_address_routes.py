import pytest
from flask import Flask
from routes.address_routes import address_bp
import json

@pytest.fixture
def app():
    app = Flask(__name__)
    app.register_blueprint(address_bp)
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def mock_db(monkeypatch):
    class MockCursor:
        def __init__(self):
            self.executed = []
            self._fetchall_response = None
            self._fetchone_response = None

        def execute(self, query, params=None):
            self.executed.append((query.strip(), params))

        def fetchall(self):
            return self._fetchall_response or []

        def fetchone(self):
            return self._fetchone_response

        def close(self):
            pass

    class MockConn:
        def __init__(self):
            self.cur = MockCursor()
            self.committed = False
            self.closed = False

        def cursor(self, cursor_factory=None):
            return self.cur

        def commit(self):
            self.committed = True

        def close(self):
            self.closed = True

    mock_conn = MockConn()
    
    def mock_get_db(*args, **kwargs):
        return mock_conn, mock_conn.cur

    monkeypatch.setattr('routes.address_routes.get_db_connection', mock_get_db)
    return mock_conn

def test_get_provinces_success(client, mock_db):
    # Setup mock response
    mock_db.cur._fetchall_response = [
        {'id': 1, 'name': 'Punjab'},
        {'id': 2, 'name': 'Sindh'}
    ]

    response = client.get('/provinces')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert len(data['provinces']) == 2
    assert data['provinces'][0]['name'] == 'Punjab'

def test_create_shipping_address_success(client, mock_db):
    # Setup mock to simulate valid province check
    mock_db.cur._fetchone_response = (1,)  # province exists
    
    response = client.post('/shipping-address', json={
        'province_id': 1,
        'city': 'Lahore',
        'street_address': '123 Test Street',
        'postal_code': '54000'
    })
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'address_id' in data
    assert mock_db.committed is True  # verify transaction was committed

def test_create_shipping_address_invalid_province(client, mock_db):
    # Setup mock to simulate invalid province
    mock_db.cur._fetchone_response = None  # province doesn't exist
    
    response = client.post('/shipping-address', json={
        'province_id': 999,
        'city': 'Invalid City',
        'street_address': '123 Test Street',
        'postal_code': '54000'
    })
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'Invalid province' in data['message']

def test_create_shipping_address_missing_fields(client):
    response = client.post('/shipping-address', json={
        'city': 'Lahore',  # missing province_id and street_address
        'postal_code': '54000'
    })
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'Missing required fields' in data['message']

def test_create_shipping_address_invalid_json(client):
    response = client.post('/shipping-address', data='invalid json')

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'Invalid or missing JSON body' in data['message']
