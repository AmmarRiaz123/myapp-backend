import os
from flask import Blueprint, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
import socket

product_bp = Blueprint('product', __name__)

def resolve_ipv4(hostname):
    """Resolve hostname to an IPv4 address."""
    try:
        print(f"[DEBUG] Attempting to resolve IPv4 for hostname: {hostname}")
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_INET)
        ipv4 = addr_info[0][4][0]
        print(f"[DEBUG] Resolved IPv4 address: {ipv4}")
        return ipv4
    except Exception as e:
        print(f"[ERROR] Could not resolve IPv4 for {hostname}: {e}")
        return hostname  # fallback to hostname if resolution fails

def connection():
    hostname = os.environ.get('DB_HOST')
    if not hostname:
        print("[ERROR] Environment variable DB_HOST is not set.")
        return None
    
    print(f"[DEBUG] Using hostname from env: {hostname}")
    ipv4_host = resolve_ipv4(hostname)

    print(f"[DEBUG] Connecting to DB at host: {ipv4_host}")
    try:
        conn = psycopg2.connect(
            host=ipv4_host,
            database=os.environ.get('DB_NAME'),
            user=os.environ.get('DB_USER'),
            password=os.environ.get('DB_PASSWORD'),
            port=os.environ.get('DB_PORT', 5432),
            sslmode='require'
        )
        print("[DEBUG] Database connection established successfully.")
        return conn
    except Exception as e:
        print(f"[ERROR] Error connecting to DB: {e}")
        return None

def get_db_connection():
    conn = connection()
    if conn is None:
        print("[ERROR] get_db_connection: connection() returned None.")
    return conn

@product_bp.route('/products', methods=['GET'])
def get_products():
    """
    Fetch all products with their primary images.
    Returns a list of products with basic info and primary image URL.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        query = """
        SELECT 
            p.id, 
            p.product_code, 
            p.name, 
            p.type, 
            p.description,
            (
                SELECT image_url 
                FROM product_images 
                WHERE product_id = p.id AND is_primary = TRUE 
                ORDER BY id ASC LIMIT 1
            ) as primary_image
        FROM 
            products p
        ORDER BY 
            p.name
        """
        cursor.execute(query)
        db_products = cursor.fetchall()

        cursor.close()
        conn.close()

        # Transform DB products to match frontend expectations
        products = [
            {
                'id': p['id'],
                'image': p.get('primary_image', ''),
                'title': p.get('name', ''),
                'description': p.get('description', ''),
                'price': p.get('type', '')  # Replace with actual price if available
            }
            for p in db_products
        ]

        return jsonify(products)

    except Exception as e:
        print(f"Error fetching products: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch products',
            'error': str(e)
        }), 500
