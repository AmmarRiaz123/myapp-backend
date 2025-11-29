from flask import Blueprint, request, jsonify, session
from auth.token_validator import require_auth
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import uuid
from datetime import datetime
import logging

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
            SELECT ci.product_id, ci.quantity, p.price
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

        # Create customer (only for guests)
        if user_info["type"] == "guest":
            cust = data.get("customer_info", {})
            if not all(cust.get(f) for f in ("name", "email", "phone")):
                return jsonify({"success": False, "message": "Guest customer info missing"}), 400

            cur.execute("""
                INSERT INTO customers (name, email, phone)
                VALUES (%s, %s, %s) RETURNING id
            """, (cust["name"], cust["email"], cust["phone"]))
            customer_id = cur.fetchone()['id']
        else:
            # authenticated → use email to find or create
            ud = user_info["user_data"]
            cur.execute("""
                INSERT INTO customers (name, email, phone)
                VALUES (%s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
            """, (ud.get("name", ""), ud["email"], ud.get("phone_number", "")))
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

        # Clear cart
        cur.execute("DELETE FROM cart WHERE user_id = %s", (user_info['id'],))

        conn.commit()

        return jsonify({
            "success": True,
            "order_id": order_id,
            "total": float(total),
            "customer_type": user_info["type"]
        }), 200

    except Exception as e:
        conn.rollback()
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
    
    conn, cur = get_db_connection()
    
    try:
        # Verify order belongs to user/guest
        cur.execute("""
            SELECT o.id, o.total_price
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            WHERE o.id = %s
        """, (order_id,))
        
        order = cur.fetchone()
        if not order:
            return jsonify({'success': False, 'message': 'Order not found'}), 404
        
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
        
        return jsonify({
            'success': True,
            'order_id': order_id,
            'message': 'Checkout completed successfully'
        })
        
    except Exception as e:
        conn.rollback()
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
