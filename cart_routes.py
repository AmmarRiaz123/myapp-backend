from flask import Blueprint, request, jsonify, session
import os
import psycopg2
from dotenv import load_dotenv
import uuid

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

def get_user_identifier_for_cart(request):
    """Get user identifier for cart operations."""
    # First check if user_id provided in request (backwards compatibility)
    data = request.get_json(silent=True) if request.method == 'POST' else None
    query_user_id = request.args.get('user_id') if request.method == 'GET' else None
    
    if data and data.get('user_id'):
        return data['user_id']
    elif query_user_id:
        return query_user_id
    
    # Check for authenticated user
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        try:
            from auth.token_validator import verify_token, extract_token
            token = extract_token()
            if token:
                user_data = verify_token(token)
                return user_data['sub']
        except:
            pass
    
    # Guest user - use session (ensure app has secret_key)
    try:
        if 'guest_id' not in session:
            session['guest_id'] = str(uuid.uuid4())
        return session['guest_id']
    except RuntimeError:
        # Fallback if session not available (like in tests without secret key)
        return f"guest_{uuid.uuid4().hex[:8]}"

@cart_bp.route('/cart/add', methods=['POST'])
def add_to_cart():
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)
    
    # Get user identifier (auth user, provided user_id, or session-based guest)
    user_id = get_user_identifier_for_cart(request)

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
        return jsonify({
            'success': True, 
            'message': 'Item added to cart',
            'user_id': user_id,  # Return for frontend to store
            'user_type': 'guest' if not request.headers.get('Authorization') else 'authenticated'
        }), 201

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@cart_bp.route('/cart/update', methods=['POST'])
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
    user_id = get_user_identifier_for_cart(request)
    
    conn, cur = get_db_connection()
    if not conn or not cur:
        return jsonify({'success': False, 'message': 'Database connection failed'}), 500
    try:
        # Fetch cart items with product info - ensure column order matches usage
        cur.execute("""
            SELECT ci.id AS cart_item_id,
                   p.id AS product_id,
                   p.name AS product_name,
                   p.product_code,
                   ci.quantity,
                   COALESCE(p.price, 0) AS price
            FROM cart c
            JOIN cart_items ci ON c.id = ci.cart_id
            JOIN products p ON ci.product_id = p.id
            WHERE c.user_id = %s
        """, (user_id,))
        items = cur.fetchall()
        
        # Format response properly - match column order
        formatted_items = []
        for item in items:
            formatted_items.append({
                'cart_item_id': item[0],    # ci.id
                'product_id': item[1],      # p.id  
                'product_name': item[2],    # p.name
                'product_code': item[3],    # p.product_code
                'quantity': item[4],        # ci.quantity
                'price': float(item[5]) if item[5] is not None else 0.0  # p.price
            })
        
        return jsonify({'success': True, 'items': formatted_items})
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


