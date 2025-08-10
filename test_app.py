import os
import pytest
from flask import Flask
from contact_api import contact_bp, send_confirmation_email
from unittest.mock import patch, MagicMock
from app import app

@pytest.fixture
def app():
    app = Flask(__name__)
    app.register_blueprint(contact_bp)
    return app

@pytest.fixture
def client(app):
    return app.test_client()

# ---- PRODUCT ROUTES ----

@patch('psycopg2.connect')
def test_get_products(mock_connect, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchall.return_value = [
        {
            'id': 1,
            'product_code': 'P001',
            'name': 'Product 1',
            'type': 'aluminum_shape',
            'description': 'desc',
            'primary_image': 'img1.jpg'
        }
    ]
    resp = client.get('/products')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert isinstance(data['products'], list)
    print("Get products: PASSED")

@patch('psycopg2.connect')
def test_get_product_detail(mock_connect, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    # Setup fetchone and fetchall for product, type_details, images, inventory
    mock_cursor.fetchone.side_effect = [
        {
            'id': 1,
            'product_code': 'P001',
            'name': 'Product 1',
            'type': 'aluminum_shape',
            'description': 'desc'
        },
        {'diameter_mm': 100, 'height_mm': 50, 'volume_cm3': 200},
        {'quantity': 10}
    ]
    mock_cursor.fetchall.side_effect = [
        [{'id': 1, 'image_url': 'img1.jpg', 'is_primary': True}]
    ]

    resp = client.get('/product/1')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert data['product']['id'] == 1
    print("Get product detail: PASSED")

@patch('psycopg2.connect')
def test_get_product_by_code(mock_connect, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    # Setup fetchone for product_id and then for product detail
    mock_cursor.fetchone.side_effect = [
        {'id': 1},
        {
            'id': 1,
            'product_code': 'P001',
            'name': 'Product 1',
            'type': 'aluminum_shape',
            'description': 'desc'
        },
        {'diameter_mm': 100, 'height_mm': 50, 'volume_cm3': 200},
        {'quantity': 10}
    ]
    mock_cursor.fetchall.side_effect = [
        [{'id': 1, 'image_url': 'img1.jpg', 'is_primary': True}]
    ]

    resp = client.get('/product/code/P001')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert data['product']['product_code'] == 'P001'
    print("Get product by code: PASSED")

# ---- CONTACT ROUTE ----

@patch('psycopg2.connect')
def test_contact_form(mock_connect, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    # Test successful submission
    resp = client.post('/contact', json={
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "1234567890",
        "message": "Hello, I am interested in your products."
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['success'] is True
    print("Contact form submission: PASSED")

    # Test missing fields
    resp = client.post('/contact', json={
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "1234567890"
        # message missing
    })
    assert resp.status_code == 400
    data = resp.get_json()
    assert data['success'] is False
    print("Contact form missing fields: PASSED")

def test_contact_form_success(monkeypatch, client):
    # Mock send_confirmation_email to avoid sending real emails
    monkeypatch.setattr('contact_api.send_confirmation_email', lambda email, name: True)
    # Mock DB connection if needed (not shown here)

    payload = {
        "name": "Test User",
        "email": "testuser@example.com",
        "phone": "1234567890",
        "message": "Hello, this is a test."
    }
    response = client.post('/contact', json=payload)
    assert response.status_code == 201
    assert response.get_json()['success'] is True
    assert "Contact form submitted" in response.get_json()['message']


if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main(["-s", __file__]))
