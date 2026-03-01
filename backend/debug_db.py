import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

uri = os.environ.get("MONGO_URI")
print(f"Connecting to: {uri[:30]}...")
client = MongoClient(uri, tls=True, tlsAllowInvalidCertificates=True)

print("\n--- Databases on Cluster ---")
for db_name_on_cluster in client.list_database_names():
    print(f"- {db_name_on_cluster}")

db_name = os.environ.get("DB_NAME", "healthflow")
print(f"\nTarget Database: {db_name}")
db = client[db_name]

print("\n--- Collections ---")
for coll in db.list_collection_names():
    count = db[coll].count_documents({})
    print(f"Collection: {coll} | Count: {count}")
    if count > 0:
        for doc in db[coll].find():
            sample = doc.copy()
            if "password" in sample: sample["password"] = "[HASHED]"
            print(f"Doc from {coll}: {sample}")

print("\n--- Done ---")
