from flask import Blueprint, request, jsonify
from auth.token_validator import require_admin
import os
import psycopg2
from psycopg2.extras import RealDictCursor

admin_products_bp = Blueprint('admin_products', __name__)

def get_db_connection(cursor_factory=None):
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432),
        sslmode='require'
    )
    cur = conn.cursor(cursor_factory=cursor_factory)
    return conn, cur

@admin_products_bp.route('/admin/products', methods=['GET'])
@require_admin
def list_products():
    conn, cur = get_db_connection(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT p.*, i.quantity as stock
            FROM products p
            LEFT JOIN inventory i ON p.id = i.product_id
            ORDER BY p.created_at DESC
        """)
        products = cur.fetchall()
        return jsonify({'success': True, 'products': products})
    finally:
        cur.close()
        conn.close()

@admin_products_bp.route('/admin/products', methods=['POST'])
@require_admin
def add_product():
    data = request.get_json()
    conn, cur = get_db_connection()
    try:
        # Insert main product
        cur.execute("""
            INSERT INTO products (product_code, name, type, description)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (data['code'], data['name'], data['type'], data['description']))
        product_id = cur.fetchone()[0]

        # Insert type-specific details
        if data['type'] == 'aluminum_shape':
            cur.execute("""
                INSERT INTO aluminum_shapes (product_id, diameter_mm, height_mm, volume_cm3)
                VALUES (%s, %s, %s, %s)
            """, (product_id, data['diameter'], data['height'], data['volume']))

        # Initialize inventory
        cur.execute("""
            INSERT INTO inventory (product_id, quantity)
            VALUES (%s, %s)
        """, (product_id, data.get('initial_stock', 0)))

        conn.commit()
        return jsonify({'success': True, 'product_id': product_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
