import os
import certifi
from pymongo import MongoClient

# Option A: hard-code (not recommended)
# uri = "mongodb+srv://Invoice:<db_password>@invoice.nlglhbe.mongodb.net/invoice_db?retryWrites=true&w=majority&appName=Invoice"

# Option B: pull from env var (best practice)
uri = os.getenv(
    "MONGODB_URI",
    "mongodb+srv://Invoice:Invoice123@invoice.nlglhbe.mongodb.net/invoice_db?retryWrites=true&w=majority&appName=Invoice"
)

# Create the client, using certifi’s CA bundle for proper TLS validation
client = MongoClient(
    uri,
    tls=True,
    tlsCAFile=certifi.where()
)

# Select your database
db = client["invoice_db"]

# Quick ping test
try:
    client.admin.command("ping")
    print("✅ Connected to MongoDB Atlas!")
except Exception as err:
    print("❌ Connection error:", err)