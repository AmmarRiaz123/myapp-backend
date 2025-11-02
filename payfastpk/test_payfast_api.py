import pytest
from flask import Flask
import urllib.parse

# Import from the payfast module under payfastpk package
from payfastpk.payfast_api import payfast_bp, generate_signature, load_payfast_config

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
    # ensure sandbox/use default URL so predictable URL used
    monkeypatch.setenv('PAYFAST_USE_SANDBOX', 'true')

    resp = client.post('/payfast/initiate', json={
        'amount': 100,
        'item_name': 'Test Item'
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert 'payment_url' in data
    # payment_url should include merchant_id
    parsed = urllib.parse.urlparse(data['payment_url'])
    qs = urllib.parse.parse_qs(parsed.query)
    assert qs.get('merchant_id', [None])[0] == 'test_id'
    assert qs.get('amount', [None])[0] == '100.00'

def test_initiate_payment_missing_amount(client):
    resp = client.post('/payfast/initiate', json={
        'item_name': 'Test Item'
    })
    assert resp.status_code == 400
    data = resp.get_json()
    assert data['success'] is False
    assert 'Amount is required' in data['message']

def test_initiate_payment_invalid_amount(client):
    resp = client.post('/payfast/initiate', json={
        'amount': 0,
        'item_name': 'Test Item'
    })
    assert resp.status_code == 400
    data = resp.get_json()
    assert data['success'] is False
    assert 'greater than zero' in data['message']

def test_initiate_payment_links_order_when_resolved(client, monkeypatch):
    # Provide predictable m_payment_id and monkeypatch find_order_by_m_payment_id + db_connect
    from payfastpk import payfast_api

    # monkeypatch find_order_by_m_payment_id to return an order id (simulate resolved order)
    monkeypatch.setattr(payfast_api, 'find_order_by_m_payment_id', lambda mpid: 123)

    executed = []

    class DummyCursor:
        def execute(self, query, params=None):
            executed.append((query.strip(), params))
        def fetchone(self):
            return (1,)
        def close(self): pass

    class DummyConn:
        def __init__(self):
            self.cur = DummyCursor()
        def cursor(self):
            return self.cur
        def commit(self):
            pass
        def close(self):
            pass

    # monkeypatch db_connect to return dummy
    monkeypatch.setattr(payfast_api, 'db_connect', lambda: (DummyConn(), DummyConn().cursor()))

    # use explicit m_payment_id so linking logic is exercised
    resp = client.post('/payfast/initiate', json={
        'amount': 10.5,
        'item_name': 'Linked Item',
        'm_payment_id': '123'
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert any('UPDATE orders' in q[0] for q in executed), "Expected an UPDATE orders call when linking m_payment_id"

def test_callback_invalid_signature(client):
    # simple callback with wrong signature
    resp = client.post('/payfast/callback', data={
        'amount': '100.00',
        'signature': 'invalid'
    })
    assert resp.status_code == 400
    data = resp.get_json()
    assert data['success'] is False
    assert 'Invalid signature' in data['message'] or 'Payment verification failed' in data['message']

def test_callback_success_persists_and_updates_order(client, monkeypatch):
    from payfastpk import payfast_api

    # Prepare a payload that mimics PayFast (m_payment_id maps to existing order)
    payload = {
        'amount': '50.00',
        'm_payment_id': '123',
        'payment_status': 'COMPLETE'
    }
    # compute server-valid signature using the module's function (no passphrase by default)
    sig = generate_signature(payload, load_payfast_config()['passphrase'])
    payload_with_sig = dict(payload)
    payload_with_sig['signature'] = sig

    # prepare dummy DB to capture persisted notification and updates
    executed = []
    inserted_notifications = []
    updated_orders = []

    class DummyCursor:
        def execute(self, query, params=None):
            executed.append((query.strip(), params))
            # crude detection of which statement; record intent
            ql = query.strip().upper()
            if ql.startswith("INSERT INTO PAYMENT_NOTIFICATIONS"):
                inserted_notifications.append(params)
            if ql.startswith("UPDATE ORDERS") or ql.startswith("UPDATE ORDERS SET PAYMENT_STATUS"):
                updated_orders.append((query.strip(), params))
        def fetchone(self):
            return (1,)
        def close(self): pass

    class DummyConn:
        def __init__(self):
            self.cur = DummyCursor()
        def cursor(self):
            return self.cur
        def commit(self):
            pass
        def close(self):
            pass

    # monkeypatch find_order_by_m_payment_id to return order id 123
    monkeypatch.setattr(payfast_api, 'find_order_by_m_payment_id', lambda mpid: 123)
    # monkeypatch db_connect to return dummy connection + cursor
    def fake_db_connect():
        conn = DummyConn()
        return conn, conn.cursor()
    monkeypatch.setattr(payfast_api, 'db_connect', fake_db_connect)

    resp = client.post('/payfast/callback', data=payload_with_sig)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    # ensure we attempted to persist a notification and update orders
    assert any('payment_notifications' in q[0].lower() for q in executed), "Expected insert into payment_notifications"
    assert any('update orders' in q[0].lower() for q in executed), "Expected update to orders table"
