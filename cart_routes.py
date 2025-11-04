from flask import Blueprint, request, jsonify
from auth.token_validator import require_auth
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
        print("🧠 DEBUG:", user_id, product_id, quantity)  # 👈 add this
        # Get or create cart
        cur.execute("SELECT id FROM cart WHERE user_id = %s", (user_id,))
        cart = cur.fetchone()
        print("🛒 Existing cart:", cart)  # 👈 add this

        if not cart:
            cur.execute("INSERT INTO cart (user_id) VALUES (%s) RETURNING id", (user_id,))
            cart = cur.fetchone()
            print("✨ New cart created:", cart)

        # Add item to cart
        cur.execute("""
            INSERT INTO cart_items (cart_id, product_id, quantity)
            VALUES (%s, %s, %s)
            ON CONFLICT (cart_id, product_id) 
            DO UPDATE SET quantity = cart_items.quantity + %s
        """, (cart[0], product_id, quantity, quantity))
        
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
@require_auth
def get_cart():
    user_id = request.user['sub']
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
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        cart_items = [dict(zip(columns, row)) for row in rows]

        # Fetch images for each product
        for item in cart_items:
            cur.execute("""
                SELECT image_url
                FROM product_images
                WHERE product_id = %s
                ORDER BY id ASC
            """, (item['product_id'],))
            images = [row[0] for row in cur.fetchall()]
            item['images'] = images  # attach images to cart item

        return jsonify({'success': True, 'items': cart_items})
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()



# All routes already protected with @require_auth
