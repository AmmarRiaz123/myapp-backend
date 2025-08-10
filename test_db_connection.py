import os
import psycopg2

def test_db_connection():
    try:
        print('host:', os.environ.get('DB_HOST'))
        conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432),
        sslmode='require'
        )
        print('host:', os.environ.get('DB_HOST'))
        print("Database connection successful!")
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        print("Test query executed successfully!")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Database connection failed: {e}")

if __name__ == "__main__":
    test_db_connection()
