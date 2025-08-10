import psycopg2
import configparser

def test_db_connection():
    try:
        config = configparser.ConfigParser()
        config.read('config.ini')
        db_config = config['database']
        print('host:', db_config.get('host'))
        conn = psycopg2.connect(
            host=db_config.get('host'),
            port=db_config.get('port'),
            database=db_config.get('database'),
            user=db_config.get('user'),
            password=db_config.get('password')
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
    test_db_connection()
