from google.cloud import firestore
from google.cloud import bigquery

PROJECT_ID = 'surfn-peru'

# FirestoreConfiguration
COLLECTION_NAME = 'expenses'
DATABASE_ID = 'expenses'
db = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)

#BigQuery 
bq_client = bigquery.Client(project=PROJECT_ID)
DATASET_ID = 'gastosrep'
TABLE_ID = 'expenses'
TABLE_REF = f"{bq_client.project}.{DATASET_ID}.{TABLE_ID}"

def sync_firestore_to_bigquery():
    # 1. Fetch data from Firestore
    docs = db.collection(COLLECTION_NAME).stream()
    rows_to_insert = [doc.to_dict() for doc in docs]

    if not rows_to_insert:
        print("No documents found in collection.")
        return

    # 2. Define BigQuery Load Job Configuration
    job_config = bigquery.LoadJobConfig(
        # This setting replaces the data instead of appending
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=True,  # Automatically detects schema from the data
    )

    # 3. Start the load job
    job = bq_client.load_table_from_json(
        rows_to_insert, 
        TABLE_REF, 
        job_config=job_config
    )

    job.result()  # Wait for the job to complete
    print(f"Successfully synced {len(rows_to_insert)} rows to {TABLE_REF}.")

if __name__ == "__main__":
    sync_firestore_to_bigquery()