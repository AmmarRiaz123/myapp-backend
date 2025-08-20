import os
import psycopg2

def test_db_connection():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT', 5432),
            sslmode=os.getenv('DB_SSLMODE', 'require')  # <- new
        )
        print("Database connection successful!")
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        print("Test query executed successfully!")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Database connection failed: {e}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    test_db_connection()
