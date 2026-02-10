import json
from google.cloud import firestore

PROJECT_ID = 'surfn-peru'

# FirestoreConfiguration
COLLECTION_NAME = 'clients'
DATABASE_ID = 'expenses'
db = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)

def import_json():
    with open('uib-clientes.json', 'r') as f:
        data = json.load(f)

    print(f"Importing {len(data)} documents...")
    
    # Use a batch for efficiency (Firestore allows up to 500 writes per batch)
    batch = db.batch()
    
    for item in data:
        # Using the 'id' from your JSON as the Document ID
        doc_id = str(item['id'])
        doc_ref = db.collection(COLLECTION_NAME).document(doc_id)
        batch.set(doc_ref, item)

    batch.commit()
    print("✅ Import complete.")

if __name__ == "__main__":
    import_json()