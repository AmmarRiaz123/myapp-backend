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

def send_admin_cod_notification(order):
    """Send COD order to admin with accurate product names and prices from DB."""
    admin_email = os.getenv("ADMIN_EMAIL", "admin@pekypk.com")
    cart_items = order.get("cart_items", [])

    if not cart_items:
        items_html = "<tr><td colspan='3'>No cart items</td></tr>"
        total_price = order.get("price", 0)
    else:
        # Fetch product details from DB
        conn, cur = get_db_connection()
        total_price = 0
        for item in cart_items:
            product_id = item.get("product_id")
            cur.execute("SELECT name, price FROM products WHERE id = %s", (product_id,))
            result = cur.fetchone()
            if result:
                name, price = result
                item["name"] = name
                item["price"] = price
                item["line_total"] = price * item.get("quantity", 1)
                total_price += item["line_total"]
            else:
                item["name"] = f"Product #{product_id}"
                item["price"] = item.get("price", 0)
                item["line_total"] = item["price"] * item.get("quantity", 1)
                total_price += item["line_total"]
        cur.close()
        conn.close()

        # Build HTML table rows
        items_html = "".join(
            f"""
            <tr style='border-bottom:1px solid #ddd'>
                <td>{item.get('name')}</td>
                <td>{item.get('quantity')}</td>
                <td>Rs {item.get('line_total')}</td>
            </tr>
            """
            for item in cart_items
        )

    html = f"""
        <h2>New Cash on Delivery Order</h2>

        <h3>Customer Info</h3>
        <p>
            <strong>Name:</strong> {order.get('full_name')}<br>
            <strong>Email:</strong> {order.get('email')}<br>
            <strong>Phone:</strong> {order.get('phone')}<br>
        </p>

        <h3>Address</h3>
        <p>
            <strong>Province ID:</strong> {order.get('province_id')}<br>
            <strong>City:</strong> {order.get('city')}<br>
            <strong>Street:</strong> {order.get('street_address')}<br>
            <strong>Postal:</strong> {order.get('postal_code') or 'N/A'}<br>
        </p>

        <h3>Order Summary</h3>
        <p><strong>Total Price:</strong> Rs {total_price}</p>

        <h3>Cart Items</h3>
        <table style="width:100%; border-collapse:collapse">
            <thead>
                <tr style="background:#f0f0f0">
                    <th style="text-align:left">Product</th>
                    <th style="text-align:left">Qty</th>
                    <th style="text-align:left">Price</th>
                </tr>
            </thead>
            <tbody>
                {items_html}
            </tbody>
        </table>
    """

    return send_email_with_retry(
        to_email=admin_email,
        subject="New Cash on Delivery Order",
        html_content=html
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

        # cart_items optional but recommended
        cart_items = data.get("cart_items", [])

        if not isinstance(cart_items, list):
            return jsonify({'success': False, 'message': 'Invalid cart_items'}), 400

        # Send email to admin
        admin_notified = send_admin_cod_notification(data)

        if admin_notified:
            return jsonify({
                'success': True,
                'message': 'Cash on Delivery order received. Admin has been notified.'
            }), 201

        return jsonify({
            'success': True,
            'message': 'Order received but failed to notify admin.'
        }), 201

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

