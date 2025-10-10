
import uuid
import sqlite3
import chromadb
from sentence_transformers import SentenceTransformer


# -----------------------------
#  Initialize Embedding Model
# -----------------------------
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# -----------------------------
#  Initialize Chroma Client
# -----------------------------
client = chromadb.PersistentClient(path="./chroma_store")
collection = client.get_or_create_collection(name="schema_collection")


# -----------------------------
#  Extract Database Schema
# -----------------------------
def extract_db_schema(db_path):
    """
    Extract tables, columns, and sample data from the SQLite database
    to build schema documentation for embedding.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    schema_docs = []
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    for (table_name,) in tables:
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        column_info = ", ".join([f"{col[1]} ({col[2]})" for col in columns])

        schema_text = f"Table: {table_name}\nColumns: {column_info}\n"
        schema_docs.append(schema_text)

    conn.close()
    return schema_docs


# -----------------------------
#  Add Schema Embeddings
# -----------------------------
def add_schema_to_chroma(collection, schema_docs, db_filename):
    """Store schema information in Chroma, tagged with its database filename."""
    if not schema_docs:
        return

    embeddings = embedding_model.encode(schema_docs).tolist()
    metadatas = [{"db_filename": db_filename} for _ in schema_docs]
    ids = [str(uuid.uuid4()) for _ in schema_docs]

    collection.add(
        documents=schema_docs,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids
    )


# -----------------------------
#  Retrieve Relevant Schema
# -----------------------------
def retrieve_relevant_schema(collection, user_query, db_filename, n_results=3):
    """Retrieve schema chunks for a specific database."""
    if not collection.count():
        return ""

    query_embedding = embedding_model.encode([user_query]).tolist()[0]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where={"db_filename": db_filename}
    )

    if results["documents"]:
        return "\n\n".join(results["documents"][0])
    return ""


# -----------------------------
#  Helper: Embed New DB
# -----------------------------
def process_and_embed_db(db_path, db_filename):
    """Extract schema from DB and add it to Chroma collection."""
    schema_docs = extract_db_schema(db_path)
    add_schema_to_chroma(collection, schema_docs, db_filename)
