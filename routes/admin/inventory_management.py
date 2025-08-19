from flask import Blueprint, request, jsonify
from auth.token_validator import require_admin
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv() 

admin_inventory_bp = Blueprint('admin_inventory', __name__)

def get_db_connection():
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432),
        sslmode=os.getenv('DB_SSLMODE', 'require')
    )
    cur = conn.cursor()
    return conn, cur

@admin_inventory_bp.route('/admin/inventory/<int:product_id>', methods=['PUT'])
@require_admin
def update_stock(product_id):
    data = request.get_json()
    new_quantity = data.get('quantity')
    
    conn, cur = get_db_connection()
    try:
        cur.execute("""
            UPDATE inventory 
            SET quantity = %s 
            WHERE product_id = %s
            RETURNING quantity
        """, (new_quantity, product_id))
        updated = cur.fetchone()
        conn.commit()
        
        if not updated:
            return jsonify({'success': False, 'message': 'Product not found'}), 404
            
        return jsonify({'success': True, 'new_quantity': updated[0]})
    finally:
        cur.close()
        conn.close()
