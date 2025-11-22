import pytest
from flask import Flask
from contact_api import contact_bp
import json

@pytest.fixture
def app():
    app = Flask(__name__)
    app.register_blueprint(contact_bp)
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def mock_db(monkeypatch):
    class MockCursor:
        def __init__(self):
            self.executed = []

        def execute(self, query, params=None):
            self.executed.append((query.strip(), params))

        def close(self):
            pass

    class MockConn:
        def __init__(self):
            self.cur = MockCursor()
            self.committed = False

        def cursor(self):
            return self.cur

        def commit(self):
            self.committed = True

        def close(self):
            pass

    mock_conn = MockConn()
    
    def mock_get_db():
        return mock_conn

    monkeypatch.setattr('contact_api.get_db_connection', mock_get_db)
    return mock_conn

def test_contact_form_success(client, mock_db, monkeypatch):
    # Mock email functions to return success
    monkeypatch.setattr('contact_api.send_confirmation_email', lambda email, name: True)
    monkeypatch.setattr('contact_api.send_admin_notification', lambda email, name, phone, message: True)
    
    response = client.post('/contact', json={
        'name': 'John Doe',
        'email': 'john@example.com',
        'phone': '+923001234567',
        'message': 'Test message'
    })
    
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'Form submitted successfully' in data['message']
    assert mock_db.committed is True

def test_contact_form_missing_fields(client):
    response = client.post('/contact', json={
        'name': 'John Doe',
        'email': 'john@example.com'
        # missing phone and message
    })
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'All fields are required' in data['message']

def test_contact_form_invalid_json(client):
    response = client.post('/contact', data='invalid json')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'Invalid JSON data' in data['message']

def test_contact_form_options(client):
    response = client.options('/contact')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
