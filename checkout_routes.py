from flask import Blueprint, request, jsonify, session
from auth.token_validator import require_auth
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import uuid
from datetime import datetime
import logging
import requests
from time import sleep

load_dotenv()

checkout_bp = Blueprint('checkout', __name__)

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

def get_user_identifier(request):
    """Get user identifier - either auth user_id or session_id for guests."""
    # Check if user is authenticated
    auth_header = request.headers.get('Authorization', '') or ''
    if auth_header.lower().startswith('bearer '):
        try:
            token = auth_header.split(' ', 1)[1].strip()
            if token and token.lower() not in ('null', 'undefined', ''):
                from auth.token_validator import verify_token
                user_data = verify_token(token)
                return {'type': 'authenticated', 'id': user_data['sub'], 'user_data': user_data}
        except Exception:
            pass

    # Guest user - use session or create new session
    if 'guest_id' not in session:
        session['guest_id'] = str(uuid.uuid4())
    
    return {'type': 'guest', 'id': session['guest_id']}

def validate_email_config():
    """Validate Resend API configuration."""
    if not os.getenv('RESEND_API_KEY'):
        logging.error("Missing RESEND_API_KEY environment variable")
        return False
    return True

def send_email_with_retry(to_email, subject, html_content, max_retries=3):
    """Send email using Resend API with retry mechanism."""
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
            logging.info(f"Email sent successfully to {to_email}")
            return True
        except requests.RequestException as e:
            logging.error(f"Failed to send email (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                sleep(1)
    return False

def send_order_confirmation_email(customer_email, customer_name, order_id, total_price, order_items):
    """Send order confirmation email to customer."""
    if not validate_email_config():
        return False

    items_html = ""
    for item in order_items:
        items_html += f"<li>{item['name']} - Quantity: {item['quantity']} - Price: ${item['price']:.2f}</li>"

    html_content = f"""
    <p>Dear {customer_name},</p>
    <p>Thank you for your order! Your order has been received and is being processed.</p>
    <p><strong>Order Details:</strong></p>
    <p>Order ID: {order_id}</p>
    <p>Total Amount: ${total_price:.2f}</p>
    <p><strong>Items Ordered:</strong></p>
    <ul>{items_html}</ul>
    <p>We will notify you once your order is shipped.</p>
    <p>Best regards,<br>Peky PK Team</p>
    """

    return send_email_with_retry(
        customer_email,
        f'Order Confirmation - Order #{order_id}',
        html_content
    )

def send_admin_order_notification(customer_name, customer_email, customer_phone, order_id, total_price, order_items, shipping_address):
    """Send new order notification to admin."""
    if not validate_email_config():
        return False

    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@pekypk.com')
    
    items_html = ""
    for item in order_items:
        items_html += f"<li>{item['name']} - Quantity: {item['quantity']} - Price: ${item['price']:.2f}</li>"

    html_content = f"""
    <h3>New Order Received</h3>
    <p><strong>Order ID:</strong> {order_id}</p>
    <p><strong>Customer Information:</strong></p>
    <p>Name: {customer_name}</p>
    <p>Email: {customer_email}</p>
    <p>Phone: {customer_phone or 'Not provided'}</p>
    <p><strong>Shipping Address:</strong></p>
    <p>{shipping_address}</p>
    <p><strong>Order Details:</strong></p>
    <p>Total Amount: ${total_price:.2f}</p>
    <p><strong>Items:</strong></p>
    <ul>{items_html}</ul>
    """

    return send_email_with_retry(
        admin_email,
        f'New Order #{order_id} - ${total_price:.2f}',
        html_content
    )

@checkout_bp.route('/checkout/cart-merge', methods=['POST'])
@require_auth
def merge_guest_cart():
    """Merge guest cart with authenticated user cart after login."""
    data = request.get_json()
    guest_id = data.get('guest_id')
    
    if not guest_id:
        return jsonify({'success': False, 'message': 'Guest ID required'}), 400
    
    user_id = request.user['sub']
    conn, cur = get_db_connection()
    
    try:
        # Get guest cart
        cur.execute("SELECT id FROM cart WHERE user_id = %s", (guest_id,))
        guest_cart = cur.fetchone()
        
        if not guest_cart:
            return jsonify({'success': True, 'message': 'No guest cart to merge'})
        
        # Get or create user cart
        cur.execute("SELECT id FROM cart WHERE user_id = %s", (user_id,))
        user_cart = cur.fetchone()
        
        if not user_cart:
            cur.execute("INSERT INTO cart (user_id) VALUES (%s) RETURNING id", (user_id,))
            user_cart = cur.fetchone()
        
        user_cart_id = user_cart[0]
        guest_cart_id = guest_cart[0]
        
        # Merge cart items
        cur.execute("""
            INSERT INTO cart_items (cart_id, product_id, quantity)
            SELECT %s, product_id, quantity FROM cart_items WHERE cart_id = %s
            ON CONFLICT (cart_id, product_id) 
            DO UPDATE SET quantity = cart_items.quantity + EXCLUDED.quantity
        """, (user_cart_id, guest_cart_id))
        
        # Delete guest cart
        cur.execute("DELETE FROM cart WHERE id = %s", (guest_cart_id,))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Cart merged successfully'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@checkout_bp.route('/checkout', methods=['POST'])
def checkout():
    """Unified checkout route: guest + authenticated users."""
    user_info = get_user_identifier(request)
    data = request.get_json()

    conn, cur = get_db_connection(cursor_factory=RealDictCursor)

    try:
        # Get cart
        cur.execute("""
            SELECT ci.product_id, ci.quantity, p.price, p.name
            FROM cart c
            JOIN cart_items ci ON c.id = ci.cart_id
            JOIN products p ON ci.product_id = p.id
            WHERE c.user_id = %s
        """, (user_info['id'],))
        cart_items = cur.fetchall()

        if not cart_items:
            return jsonify({'success': False, 'message': 'Cart is empty'}), 400

        # Total price
        total = sum(float(i['price']) * i['quantity'] for i in cart_items)

        # Create customer (handle both guest and authenticated)
        if user_info["type"] == "guest":
            cust = data.get("customer_info", {})
            if not all(cust.get(f) for f in ("name", "email", "phone")):
                return jsonify({"success": False, "message": "Guest customer info missing"}), 400

            cur.execute("""
                INSERT INTO customers (name, email, phone)
                VALUES (%s, %s, %s) RETURNING id
            """, (cust["name"], cust["email"], cust["phone"]))
            customer_id = cur.fetchone()['id']
            customer_email = cust["email"]
            customer_phone = cust["phone"]
            customer_name = cust["name"]
        else:
            # authenticated → get from token and customer_info if provided
            ud = user_info["user_data"]
            cust = data.get("customer_info", {})
            
            # Use customer_info if provided, otherwise fall back to token data
            customer_name = cust.get("name") or ud.get("name", ud.get("given_name", ""))
            customer_email = cust.get("email") or ud.get("email", "")
            customer_phone = cust.get("phone") or ud.get("phone_number", "")
            
            if not customer_email:
                return jsonify({"success": False, "message": "Customer email is required"}), 400
            
            # Insert or update customer record
            cur.execute("""
                INSERT INTO customers (name, email, phone)
                VALUES (%s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET 
                    name = CASE WHEN EXCLUDED.name != '' THEN EXCLUDED.name ELSE customers.name END,
                    phone = CASE WHEN EXCLUDED.phone != '' THEN EXCLUDED.phone ELSE customers.phone END
                RETURNING id
            """, (customer_name, customer_email, customer_phone))
            customer_id = cur.fetchone()["id"]

        # Shipping address
        ship = data.get("shipping_address", {})
        cur.execute("""
            INSERT INTO shipping_addresses (province_id, city, street_address, postal_code)
            VALUES (%s, %s, %s, %s) RETURNING id
        """, (
            ship["province_id"],
            ship["city"],
            ship["street_address"],
            ship.get("postal_code", "")
        ))
        shipping_id = cur.fetchone()['id']

        # Order
        cur.execute("""
            INSERT INTO orders (customer_id, status, total_price, shipping_address_id)
            VALUES (%s, 'pending', %s, %s)
            RETURNING id
        """, (customer_id, total, shipping_id))
        order_id = cur.fetchone()['id']

        # Order items
        for item in cart_items:
            cur.execute("""
                INSERT INTO order_items (order_id, product_id, quantity, price)
                VALUES (%s, %s, %s, %s)
            """, (order_id, item['product_id'], item['quantity'], item['price']))

        # Send immediate order notification emails
        shipping_address = f"{ship['street_address']}, {ship['city']}"
        
        # Get province name for complete address
        cur.execute("SELECT name FROM provinces WHERE id = %s", (ship["province_id"],))
        province_result = cur.fetchone()
        if province_result:
            shipping_address += f", {province_result['name']}"
        
        customer_email_sent = send_order_confirmation_email(
            customer_email, 
            customer_name, 
            order_id, 
            float(total), 
            cart_items
        )
        
        admin_email_sent = send_admin_order_notification(
            customer_name,
            customer_email, 
            customer_phone,
            order_id, 
            float(total), 
            cart_items,
            shipping_address
        )

        # Clear cart
        cur.execute("DELETE FROM cart WHERE user_id = %s", (user_info['id'],))

        conn.commit()

        # Prepare response message based on email status
        message = 'Order created successfully'
        if customer_email_sent and admin_email_sent:
            message += '. Confirmation email sent and admin notified.'
        elif customer_email_sent:
            message += '. Confirmation email sent, but failed to notify admin.'
        elif admin_email_sent:
            message += '. Admin notified, but failed to send confirmation email.'
        else:
            message += ', but failed to send any emails.'

        return jsonify({
            "success": True,
            "order_id": order_id,
            "total": float(total),
            "customer_type": user_info["type"],
            "message": message
        }), 200

    except Exception as e:
        conn.rollback()
        logging.error(f"Error during checkout: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        cur.close()
        conn.close()


@checkout_bp.route('/checkout/complete', methods=['POST'])
def complete_checkout():
    """Complete checkout and clear cart."""
    user_info = get_user_identifier(request)
    data = request.get_json()
    
    order_id = data.get('order_id')
    payment_method = data.get('payment_method', 'payfast')
    
    if not order_id:
        return jsonify({'success': False, 'message': 'Order ID required'}), 400
    
    conn, cur = get_db_connection(cursor_factory=RealDictCursor)
    
    try:
        # Get order details with customer and items info
        cur.execute("""
            SELECT o.id, o.total_price, c.name, c.email, c.phone,
                   sa.street_address, sa.city, p.name as province_name
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            LEFT JOIN shipping_addresses sa ON o.shipping_address_id = sa.id
            LEFT JOIN provinces p ON sa.province_id = p.id
            WHERE o.id = %s
        """, (order_id,))
        
        order = cur.fetchone()
        if not order:
            return jsonify({'success': False, 'message': 'Order not found'}), 404

        # Get order items
        cur.execute("""
            SELECT oi.quantity, oi.price, p.name
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = %s
        """, (order_id,))
        order_items = cur.fetchall()
        
        # Clear cart after successful checkout
        cur.execute("DELETE FROM cart WHERE user_id = %s", (user_info['id'],))
        
        # Update order status
        cur.execute("""
            UPDATE orders SET 
                status = 'confirmed',
                payment_provider = %s,
                m_payment_id = %s
            WHERE id = %s
        """, (payment_method, str(order_id), order_id))
        
        conn.commit()

        # Send email notifications
        shipping_address = f"{order['street_address']}, {order['city']}, {order['province_name']}"
        
        customer_email_sent = send_order_confirmation_email(
            order['email'], 
            order['name'], 
            order_id, 
            float(order['total_price']), 
            order_items
        )
        
        admin_email_sent = send_admin_order_notification(
            order['name'],
            order['email'], 
            order['phone'],
            order_id, 
            float(order['total_price']), 
            order_items,
            shipping_address
        )

        # Prepare response message based on email status
        message = 'Checkout completed successfully'
        if customer_email_sent and admin_email_sent:
            message += '. Confirmation email sent and admin notified.'
        elif customer_email_sent:
            message += '. Confirmation email sent, but failed to notify admin.'
        elif admin_email_sent:
            message += '. Admin notified, but failed to send confirmation email.'
        else:
            message += ', but failed to send any emails.'
        
        return jsonify({
            'success': True,
            'order_id': order_id,
            'message': message
        })
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error completing checkout: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@checkout_bp.route('/checkout/guest-to-auth', methods=['POST'])
@require_auth
def convert_guest_to_auth():
    """Convert guest checkout to authenticated user checkout."""
    data = request.get_json()
    guest_id = data.get('guest_id')
    
    if not guest_id:
        return jsonify({'success': False, 'message': 'Guest ID required'}), 400
    
    user_id = request.user['sub']
    
    # Merge cart first - call the function directly
    try:
        # Create a temporary request with guest_id for merge function
        temp_data = {'guest_id': guest_id}
        request._cached_json = temp_data
        
        merge_response = merge_guest_cart()
        
        # Handle both tuple and Response object returns
        if isinstance(merge_response, tuple):
            response_obj, status_code = merge_response
            if hasattr(response_obj, 'get_json'):
                merge_data = response_obj.get_json()
            else:
                merge_data = response_obj
        else:
            merge_data = merge_response.get_json()
            
        if not merge_data.get('success'):
            return jsonify({
                'success': False, 
                'message': f"Cart merge failed: {merge_data.get('message', 'Unknown error')}"
            }), 400
            
    except Exception as e:
        logging.error(f"Error merging guest cart: {e}")
        # Continue even if merge fails
    
    return jsonify({
        'success': True,
        'message': 'Successfully converted to authenticated checkout',
        'user_id': user_id
    })
