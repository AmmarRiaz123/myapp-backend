import os
from flask import Blueprint, request, jsonify
import psycopg2

contact_bp = Blueprint('contact', __name__)

def resolve_ipv4(hostname):
    """Resolve hostname to an IPv4 address."""
    try:
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_INET)
        ipv4 = addr_info[0][4][0]
        return ipv4
    except Exception as e:
        print(f"Could not resolve IPv4 for {hostname}: {e}")
        return hostname  # fallback to hostname if resolution fails

def connection():
    hostname = os.environ.get('DB_HOST')
    ipv4_host = resolve_ipv4(hostname)

    try:
        conn = psycopg2.connect(
            host=ipv4_host,
            database=os.environ.get('DB_NAME'),
            user=os.environ.get('DB_USER'),
            password=os.environ.get('DB_PASSWORD'),
            port=os.environ.get('DB_PORT', 5432),
            sslmode='require'
        )
        return conn
    except Exception as e:
        print(f"Error connecting to DB: {e}")
        return None

def get_db_connection():
    return connection()
@contact_bp.route('/contact', methods=['POST'])
def contact():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    message = data.get('message')

    if not name or not email or not phone or not message:
        return jsonify({'success': False, 'message': 'All fields are required'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO customers (name, email, phone, message) VALUES (%s, %s, %s, %s)",
            (name, email, phone, message)
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Contact form submitted successfully'}), 201
    except Exception as e:
        print(f"Error inserting contact: {e}")
        return jsonify({'success': False, 'message': 'Failed to submit contact form', 'error': str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

