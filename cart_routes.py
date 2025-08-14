from flask import Blueprint, request, jsonify
from auth.token_validator import require_auth
import os
import psycopg2

cart_bp = Blueprint('cart', __name__)

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

@cart_bp.route('/cart/add', methods=['POST'])
@require_auth
def add_to_cart():
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)
    user_id = request.user['sub']  # Cognito user ID

    if not product_id:
        return jsonify({'success': False, 'message': 'Product ID is required'}), 400

    conn, cur = get_db_connection()
    if not conn or not cur:
        return jsonify({'success': False, 'message': 'Database connection failed'}), 500
    try:
        # Get or create cart
        cur.execute("SELECT id FROM cart WHERE user_id = %s", (user_id,))
        cart = cur.fetchone()
        if not cart:
            cur.execute("INSERT INTO cart (user_id) VALUES (%s) RETURNING id", (user_id,))
            cart = cur.fetchone()

        # Add item to cart
        cur.execute("""
            INSERT INTO cart_items (cart_id, product_id, quantity)
            VALUES (%s, %s, %s)
            ON CONFLICT (cart_id, product_id) 
            DO UPDATE SET quantity = cart_items.quantity + %s
        """, (cart[0], product_id, quantity, quantity))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Item added to cart'}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@cart_bp.route('/cart', methods=['GET'])
@require_auth
def get_cart():
    user_id = request.user['sub']
    conn, cur = get_db_connection()
    if not conn or not cur:
        return jsonify({'success': False, 'message': 'Database connection failed'}), 500
    try:
        cur.execute("""
            SELECT ci.id, p.name, p.product_code, ci.quantity, p.id as product_id
            FROM cart c
            JOIN cart_items ci ON c.id = ci.cart_id
            JOIN products p ON ci.product_id = p.id
            WHERE c.user_id = %s
        """, (user_id,))
        items = cur.fetchall()
        return jsonify({'success': True, 'items': items})
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# All routes already protected with @require_auth
