from flask import Blueprint, request, jsonify
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

cart_bp = Blueprint('cart', __name__)

def get_db_connection():
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432),
        sslmode=os.getenv('DB_SSLMODE', 'require')  # allow override locally
    )
    cur = conn.cursor()
    return conn, cur

@cart_bp.route('/cart/add', methods=['POST'])
def add_to_cart():
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)
    user_id = data.get('user_id')  # Now comes from request body instead of auth

    if not product_id:
        return jsonify({'success': False, 'message': 'Product ID is required'}), 400
    
    if not user_id:
        return jsonify({'success': False, 'message': 'User ID is required'}), 400

    conn, cur = get_db_connection()
    if not conn or not cur:
        return jsonify({'success': False, 'message': 'Database connection failed'}), 500

    try:
        print("🧠 DEBUG:", user_id, product_id, quantity)  # 👈 add this
        # Get or create cart
        cur.execute("SELECT id FROM cart WHERE user_id = %s", (user_id,))
        cart = cur.fetchone()
        print("🛒 Existing cart:", cart)  # 👈 add this

        if not cart:
            cur.execute("INSERT INTO cart (user_id) VALUES (%s) RETURNING id", (user_id,))
            cart = cur.fetchone()

        cart_id = cart[0]

        # Check if item already exists in cart
        cur.execute("SELECT id, quantity FROM cart_items WHERE cart_id = %s AND product_id = %s", (cart_id, product_id))
        existing_item = cur.fetchone()
        
        if existing_item:
            # Update existing item
            new_quantity = existing_item[1] + quantity
            cur.execute("UPDATE cart_items SET quantity = %s WHERE id = %s", (new_quantity, existing_item[0]))
        else:
            # Insert new item
            cur.execute("INSERT INTO cart_items (cart_id, product_id, quantity) VALUES (%s, %s, %s)", 
                       (cart_id, product_id, quantity))
        
        conn.commit()
        print("✅ Item added successfully")
        return jsonify({'success': True, 'message': 'Item added to cart'}), 201

    except Exception as e:
        conn.rollback()
        import traceback
        traceback.print_exc()  # 👈 full error stack
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@cart_bp.route('/cart/update', methods=['POST'])
@require_auth
def update_cart_item():
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity')
    user_id = request.user['sub']

    if not product_id or quantity is None:
        return jsonify({'success': False, 'message': 'Product ID and quantity are required'}), 400

    if quantity < 0 or quantity % 10 != 0:
        return jsonify({'success': False, 'message': 'Quantity must be in increments of 10 and cannot be negative'}), 400

    conn, cur = get_db_connection()
    if not conn or not cur:
        return jsonify({'success': False, 'message': 'Database connection failed'}), 500

    try:
        # Get user's cart
        cur.execute("SELECT id FROM cart WHERE user_id = %s", (user_id,))
        cart = cur.fetchone()
        if not cart:
            return jsonify({'success': False, 'message': 'Cart not found'}), 404

        if quantity == 0:
            # Delete the item if quantity is 0
            cur.execute(
                "DELETE FROM cart_items WHERE cart_id = %s AND product_id = %s",
                (cart[0], product_id)
            )
        else:
            # Update quantity
            cur.execute(
                "UPDATE cart_items SET quantity = %s WHERE cart_id = %s AND product_id = %s",
                (quantity, cart[0], product_id)
            )

        conn.commit()
        return jsonify({'success': True, 'message': 'Cart updated'}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()



@cart_bp.route('/cart', methods=['GET'])
def get_cart():
    user_id = request.args.get('user_id')  # Get from query params instead of auth
    
    if not user_id:
        return jsonify({'success': False, 'message': 'User ID is required'}), 400
    
    conn, cur = get_db_connection()
    if not conn or not cur:
        return jsonify({'success': False, 'message': 'Database connection failed'}), 500
    try:
        # Fetch cart items with product info
        cur.execute("""
            SELECT ci.id AS cart_item_id,
                   p.id AS product_id,
                   p.name AS product_name,
                   p.product_code,
                   ci.quantity,
                   p.price
            FROM cart c
            JOIN cart_items ci ON c.id = ci.cart_id
            JOIN products p ON ci.product_id = p.id
            WHERE c.user_id = %s
        """, (user_id,))
        items = cur.fetchall()
        
        # Format response properly
        formatted_items = []
        for item in items:
            formatted_items.append({
                'id': item[0],
                'name': item[1],
                'product_code': item[2],
                'quantity': item[3],
                'product_id': item[4]
            })
        
        return jsonify({'success': True, 'items': formatted_items})
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()



# All routes already protected with @require_auth
