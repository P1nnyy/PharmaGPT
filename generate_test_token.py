from jose import jwt
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

def create_token(email):
    expire = datetime.utcnow() + timedelta(days=7)
    to_encode = {"sub": email, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

if __name__ == "__main__":
    email = "pranavgupta1638@gmail.com" # The user's email from the system settings
    token = create_token(email)
    print(f"FOR TEST: User: {email}")
    print(f"TOKEN: {token}")
