import configparser
from flask import Blueprint, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
import socket

product_bp = Blueprint('product', __name__)

def get_db_connection():
    config = configparser.ConfigParser()
    config.read('config.ini')
    db_config = config['database']
    conn = psycopg2.connect(
        host=db_config.get('host'),
        database=db_config.get('database'),
        user=db_config.get('user'),
        password=db_config.get('password'),
        port=db_config.get('port', 5432),
        sslmode='require'
    )
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
