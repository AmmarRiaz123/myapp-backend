import os
from flask import Blueprint, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
import socket

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
            i.quantity as stock,
            (
                SELECT image_url 
                FROM product_images 
                WHERE product_id = p.id AND is_primary = TRUE 
                LIMIT 1
            ) as primary_image
        FROM 
            products p
        LEFT JOIN 
            inventory i ON p.id = i.product_id
        ORDER BY 
            p.name
        """
        cursor.execute(query)
        products = cursor.fetchall()
        
        return jsonify({
            'success': True,
            'products': [{
                'id': p['id'],
                'code': p['product_code'],
                'name': p['name'],
                'description': p['description'],
                'image': p.get('primary_image', ''),
                'stock': p.get('stock', 0),
                'type': p['type']
            } for p in products]
        })

    except Exception as e:
        print(f"Error fetching products: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch products',
            'error': str(e)
        }), 500

