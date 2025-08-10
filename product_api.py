import os
from flask import Blueprint, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor

product_bp = Blueprint('product', __name__)

def get_db_connection():
    """Create and return a database connection using environment variables"""
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432),
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
