from flask import Blueprint, request, jsonify
from auth.token_validator import require_auth
import os
import psycopg2

order_bp = Blueprint('order', __name__)

def get_db_connection():
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432),
        sslmode='require'
    )
    cur = conn.cursor()
    return conn, cur

@order_bp.route('/checkout', methods=['POST'])
@require_auth
def checkout():
    user_id = request.user['sub']
    conn, cur = get_db_connection()
    if not conn or not cur:
        return jsonify({'success': False, 'message': 'Database connection failed'}), 500
    try:
        # Get cart items
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
        cur.execute(
            "INSERT INTO orders (customer_id, status) VALUES (%s, 'pending') RETURNING id",
            (user_id,)
        )
        order_id = cur.fetchone()[0]

        # Add order items and update inventory
        for item in cart_items:
            product_id, quantity = item[0], item[1]
            cur.execute("""
                INSERT INTO order_items (order_id, product_id, quantity)
                VALUES (%s, %s, %s)
            """, (order_id, product_id, quantity))
            
            # Update inventory
            cur.execute("""
                UPDATE inventory 
                SET quantity = quantity - %s 
                WHERE product_id = %s AND quantity >= %s
            """, (quantity, product_id, quantity))

        # Clear cart
        cur.execute("DELETE FROM cart WHERE user_id = %s", (user_id,))
        
        conn.commit()
        return jsonify({'success': True, 'order_id': order_id}), 201

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
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

# All routes already protected with @require_auth
