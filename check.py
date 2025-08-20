from dotenv import load_dotenv
import os

load_dotenv()

print("DB Host:", os.getenv("DB_HOST"))
print("AWS Region:", os.getenv("AWS_REGION"))
