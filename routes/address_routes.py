from flask import Blueprint, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()

address_bp = Blueprint('address', __name__)

def get_db_connection(cursor_factory=None):
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432),
        sslmode=os.getenv('DB_SSLMODE', 'require')
    )
    cur = conn.cursor(cursor_factory=cursor_factory)
    return conn, cur

@address_bp.route('/provinces', methods=['GET'])
def get_provinces():
    """Get list of all provinces for address form."""
    conn, cur = get_db_connection(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT id, name FROM provinces ORDER BY name")
        provinces = cur.fetchall()
        return jsonify({
            'success': True,
            'provinces': provinces
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@address_bp.route('/shipping-address', methods=['POST'])
def create_shipping_address():
    """Create shipping address and return ID for order creation."""
    try:
        data = request.get_json()
        required = ['province_id', 'city', 'street_address']
        if not all(data.get(field) for field in required):
            return jsonify({
                'success': False,
                'message': 'Missing required fields'
            }), 400

        conn, cur = get_db_connection()
        try:
            # First verify province exists
            cur.execute("SELECT id FROM provinces WHERE id = %s", (data['province_id'],))
            if not cur.fetchone():
                return jsonify({
                    'success': False,
                    'message': 'Invalid province selected'
                }), 400

            # Insert address
            cur.execute("""
                INSERT INTO shipping_addresses 
                (province_id, city, street_address, postal_code)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (
                data['province_id'],
                data['city'].strip(),
                data['street_address'].strip(),
                data.get('postal_code', '').strip() or None
            ))
            
            address_id = cur.fetchone()[0]
            conn.commit()
            
            return jsonify({
                'success': True,
                'address_id': address_id,
                'message': 'Shipping address created successfully'
            })
            
        except Exception as e:
            conn.rollback()
            return jsonify({
                'success': False,
                'message': f'Failed to create shipping address: {str(e)}'
            }), 500
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Invalid request: {str(e)}'
        }), 400
