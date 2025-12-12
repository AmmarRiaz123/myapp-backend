from flask import Blueprint, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
import requests
from time import sleep

load_dotenv()

address_bp = Blueprint('address', __name__)

# ------------------------- DB CONNECTION -------------------------

def get_db_connection(cursor_factory=None):
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432),
        sslmode=os.getenv('DB_SSLMODE', 'require')
    )
    cur = conn.cursor(cursor_factory=cursor_factory)
    return conn, cur

# ------------------------- EMAIL HELPERS -------------------------

def validate_email_config():
    return bool(os.getenv('RESEND_API_KEY'))

def send_email_with_retry(to_email, subject, html_content, max_retries=3):
    api_key = os.getenv('RESEND_API_KEY')
    if not api_key:
        return False

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    data = {
        'from': 'Peky PK <noreply@pekypk.com>',
        'to': [to_email],
        'subject': subject,
        'html': html_content
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(
                'https://api.resend.com/emails',
                headers=headers,
                json=data
            )
            response.raise_for_status()
            return True
        except Exception:
            if attempt < max_retries - 1:
                sleep(1)

    return False

def send_admin_cod_notification(data):
    """Send Cash on Delivery details to admin."""
    admin_email = os.getenv('ADMIN_EMAIL', 'admin@pekypk.com')
    if not validate_email_config():
        return False

    html = f"""
    <h2>New Cash on Delivery Order</h2>

    <h3>Customer Details</h3>
    <p><strong>Name:</strong> {data['full_name']}</p>
    <p><strong>Email:</strong> {data['email']}</p>
    <p><strong>Phone:</strong> {data['phone']}</p>
    <p><strong>Price:</strong> PKR {data['price']}</p>

    <h3>Shipping Address</h3>
    <p><strong>Province ID:</strong> {data['province_id']}</p>
    <p><strong>City:</strong> {data['city']}</p>
    <p><strong>Street Address:</strong> {data['street_address']}</p>
    <p><strong>Postal Code:</strong> {data.get('postal_code', 'N/A')}</p>
    """

    return send_email_with_retry(
        admin_email,
        "New Cash on Delivery Order",
        html
    )

# ------------------------- EXISTING ROUTES -------------------------

@address_bp.route('/provinces', methods=['GET'])
def get_provinces():
    conn, cur = get_db_connection(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT id, name FROM provinces ORDER BY name")
        provinces = cur.fetchall()
        return jsonify({'success': True, 'provinces': provinces})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@address_bp.route('/shipping-address', methods=['POST'])
def create_shipping_address():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'Invalid JSON'}), 400

        required = ['province_id', 'city', 'street_address']
        if not all(data.get(field) for field in required):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400

        conn, cur = get_db_connection()

        try:
            cur.execute("SELECT id FROM provinces WHERE id = %s", (data['province_id'],))
            if not cur.fetchone():
                return jsonify({'success': False, 'message': 'Invalid province selected'}), 400

            cur.execute("""
                INSERT INTO shipping_addresses 
                (province_id, city, street_address, postal_code)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (
                data['province_id'],
                data['city'].strip(),
                data['street_address'].strip(),
                data.get('postal_code', '').strip() or None
            ))

            address_id = cur.fetchone()[0]
            conn.commit()

            return jsonify({
                'success': True,
                'address_id': address_id,
                'message': 'Shipping address created successfully'
            })

        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            cur.close()
            conn.close()

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

# ------------------------- NEW CASH ON DELIVERY ROUTE -------------------------

@address_bp.route('/cash-on-delivery', methods=['POST'])
def cash_on_delivery():
    """Accept COD order details and send them to admin Gmail."""
    try:
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'Invalid JSON'}), 400

        required = [
            'full_name', 'phone', 'email',
            'price', 'province_id', 'city', 'street_address'
        ]

        if not all(data.get(field) for field in required):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400

        # Send email to admin
        admin_notified = send_admin_cod_notification(data)

        if admin_notified:
            return jsonify({
                'success': True,
                'message': 'Cash on Delivery order received. Admin has been notified.'
            }), 201
        else:
            return jsonify({
                'success': True,
                'message': 'Order received but failed to notify admin.'
            }), 201

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400
