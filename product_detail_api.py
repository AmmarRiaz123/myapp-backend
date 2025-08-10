import os
from flask import Blueprint, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor

product_detail_bp = Blueprint('product_detail', __name__)

def get_db_connection():
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432),
        sslmode='require'
    )
    return conn

@product_detail_bp.route('/product/<int:product_id>', methods=['GET'])
def get_product_detail(product_id):
    """
    Fetch detailed information about a specific product,
    including type-specific details, all images, and inventory.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        # Get basic product info
        cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
        product = cursor.fetchone()
        if not product:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': f'Product with ID {product_id} not found'}), 404

        # Get product type-specific details
        product_type = product['type']
        type_details = {}
        if product_type == 'aluminum_shape':
            cursor.execute("SELECT * FROM aluminum_shapes WHERE product_id = %s", (product_id,))
            type_details = cursor.fetchone() or {}
        elif product_type == 'cardboard_lid':
            cursor.execute("SELECT * FROM cardboard_lids WHERE product_id = %s", (product_id,))
            type_details = cursor.fetchone() or {}
        elif product_type == 'pack':
            cursor.execute("SELECT * FROM product_packs WHERE product_id = %s", (product_id,))
            type_details = cursor.fetchone() or {}
        elif product_type == 'complement':
            cursor.execute("SELECT * FROM complements WHERE product_id = %s", (product_id,))
            type_details = cursor.fetchone() or {}

        # Get all product images
        cursor.execute(
            "SELECT id, image_url, is_primary FROM product_images WHERE product_id = %s ORDER BY is_primary DESC, id ASC",
            (product_id,))
        images = cursor.fetchall()

        # Get inventory information
        cursor.execute("SELECT quantity FROM inventory WHERE product_id = %s", (product_id,))
        inventory = cursor.fetchone()

        cursor.close()
        conn.close()

        response = {
            'success': True,
            'product': product,
            'type_details': type_details,
            'images': images,
            'inventory': inventory['quantity'] if inventory else 0
        }
        return jsonify(response)
    except Exception as e:
        print(f"Error fetching product details: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch product details',
            'error': str(e)
        }), 500

@product_detail_bp.route('/product/code/<product_code>', methods=['GET'])
def get_product_by_code(product_code):
    """
    Fetch detailed information about a specific product by its code.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT id FROM products WHERE product_code = %s", (product_code,))
        product_id_record = cursor.fetchone()
        cursor.close()
        conn.close()
        if not product_id_record:
            return jsonify({'success': False, 'message': f'Product with code {product_code} not found'}), 404
        # Call the existing function with the ID
        return get_product_detail(product_id_record['id'])
    except Exception as e:
        print(f"Error fetching product by code: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch product details',
            'error': str(e)
        }), 500
        if not product_id_record:
            return jsonify({'success': False, 'message': f'Product with code {product_code} not found'}), 404
        # Call the existing function with the ID
        return get_product_detail(product_id_record['id'])
    except Exception as e:
        print(f"Error fetching product by code: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch product details',
            'error': str(e)
        }), 500
