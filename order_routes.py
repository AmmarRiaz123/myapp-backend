from flask import Blueprint, request, jsonify
from auth.token_validator import require_auth
from dotenv import load_dotenv
import os
import psycopg2
import uuid  # added import

load_dotenv()

order_bp = Blueprint('order', __name__)

def get_db_connection():
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432),
        sslmode=os.getenv('DB_SSLMODE', 'require')
    )
    cur = conn.cursor()
    return conn, cur

def get_user_identifier_for_cart(request):
    """Get user identifier for cart operations (logged-in or guest)."""

    # 1️⃣ Check if authenticated user (Authorization: Bearer ...)
    auth_header = request.headers.get('Authorization', '') or ''
    if auth_header.lower().startswith('bearer '):
        try:
            # parse token directly and ignore invalid tokens like 'null' or 'undefined'
            token = auth_header.split(' ', 1)[1].strip()
            if token and token.lower() not in ('null', 'undefined', ''):
                from auth.token_validator import verify_token
                user_data = verify_token(token)
                return str(user_data['sub'])
        except Exception:
            # fallthrough to guest handling
            pass

    # 2️⃣ Check if frontend sent guest ID
    guest_id = request.headers.get("X-Guest-ID")
    if guest_id:
        return str(guest_id)

    # 3️⃣ Fallback (should rarely happen)
    new_guest = f"guest_{uuid.uuid4().hex[:8]}"
    return new_guest


@order_bp.route('/checkout', methods=['POST'])
def checkout():
    user_id = get_user_identifier_for_cart(request)   # ✔ works for guest & user

    conn, cur = get_db_connection()
    if not conn or not cur:
        return jsonify({'success': False, 'message': 'Database connection failed'}), 500

    try:
        # Get cart items for this user/guest
        cur.execute("""
            SELECT ci.product_id, ci.quantity, p.name
            FROM cart c
            JOIN cart_items ci ON c.id = ci.cart_id
            JOIN products p ON ci.product_id = p.id
            WHERE c.user_id = %s
        """, (user_id,))
        cart_items = cur.fetchall()

        if not cart_items:
            return jsonify({'success': False, 'message': 'Cart is empty'}), 400

        # Create order
        cur.execute("""
            INSERT INTO orders (customer_id, status)
            VALUES (%s, 'pending') RETURNING id
        """, (user_id,))
        order_id = cur.fetchone()[0]

        # Add items & update inventory
        for product_id, quantity, product_name in cart_items:
            cur.execute("""
                INSERT INTO order_items (order_id, product_id, quantity)
                VALUES (%s, %s, %s)
            """, (order_id, product_id, quantity))

            cur.execute("""
                UPDATE inventory
                SET quantity = quantity - %s
                WHERE product_id = %s
            """, (quantity, product_id))

        # Clear ONLY cart items, not cart row
        cur.execute("""
            DELETE FROM cart_items 
            WHERE cart_id = (SELECT id FROM cart WHERE user_id = %s)
        """, (user_id,))

        conn.commit()

        return jsonify({'success': True, 'order_id': order_id}), 201

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

    finally:
        cur.close()
        conn.close()

@order_bp.route('/orders', methods=['GET'])
@require_auth
def get_orders():
    user_id = request.user['sub']
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT o.id, o.status, o.created_at, 
                   json_agg(json_build_object(
                       'product_id', oi.product_id,
                       'quantity', oi.quantity,
                       'product_name', p.name
                   )) as items
            FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            JOIN products p ON oi.product_id = p.id
            WHERE o.customer_id = %s
            GROUP BY o.id
            ORDER BY o.created_at DESC
        """, (user_id,))
        orders = cur.fetchall()
        return jsonify({'success': True, 'orders': orders})
    finally:
        cur.close()
        conn.close()
        
@order_bp.route('/orders', methods=['POST'])
def create_order():
    data = request.get_json() or {}

    # Try to resolve authenticated user id, if provided
    user_id = None
    auth_header = request.headers.get('Authorization', '') or ''
    if auth_header.lower().startswith('bearer '):
        try:
            token = auth_header.split(' ', 1)[1].strip()
            if token and token.lower() not in ('null', 'undefined', ''):
                from auth.token_validator import verify_token
                user = verify_token(token)
                user_id = user.get('sub')
        except Exception:
            user_id = None

    amount = data.get('amount')
    if amount is None:
        return jsonify({'success': False, 'message': 'Amount is required'}), 400

    conn = None
    cur = None
    try:
        conn, cur = get_db_connection()
        cur.execute("""
            INSERT INTO orders (customer_id, status, total_amount)
            VALUES (%s, %s, %s) RETURNING id
        """, (user_id, 'pending', amount))
        order_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({'success': True, 'order_id': order_id}), 201
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
