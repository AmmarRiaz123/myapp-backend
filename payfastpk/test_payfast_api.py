import pytest
from flask import Flask
from payfast_api import payfast_bp

@pytest.fixture
def app():
    app = Flask(__name__)
    app.register_blueprint(payfast_bp)
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_initiate_payment_success(client, monkeypatch):
    monkeypatch.setenv('PAYFAST_MERCHANT_ID', 'test_id')
    monkeypatch.setenv('PAYFAST_MERCHANT_KEY', 'test_key')
    response = client.post('/payfast/initiate', json={
        'amount': 100,
        'item_name': 'Test Item'
    })
    data = response.get_json()
    assert response.status_code == 200
    assert data['success'] is True
    assert 'payment_url' in data

def test_initiate_payment_missing_amount(client):
    response = client.post('/payfast/initiate', json={
        'item_name': 'Test Item'
    })
    data = response.get_json()
    assert response.status_code == 400
    assert data['success'] is False
    assert 'Amount is required' in data['message']

def test_callback_invalid_signature(client):
    response = client.post('/payfast/callback', data={
        'amount': '100.00',
        'signature': 'invalid'
    })
    data = response.get_json()
    assert response.status_code == 400
    assert data['success'] is False
    assert 'Invalid signature' in data['message'] or 'Payment verification failed' in data['message']

def test_callback_no_data(client):
    response = client.post('/payfast/callback', data={})
    data = response.get_json()
    assert response.status_code == 400
    assert data['success'] is False
    assert 'No callback data' in data['message']
