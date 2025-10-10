import os
import uuid
import sqlite3
from flask import Flask, request, jsonify, render_template, session
from werkzeug.utils import secure_filename
from flask_cors import CORS
from groq import Groq
from rag_utils import get_collection, add_schema_to_chroma, retrieve_relevant_schema

# ===============================
# Flask Configuration
# ===============================
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")
CORS(app)

UPLOAD_FOLDER = "uploaded_dbs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ===============================
# Initialize Groq and ChromaDB
# ===============================
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
collection = get_collection()  # From rag_utils.py


# ===============================
# Helper Functions
# ===============================
def get_db_schema(db_path):
    """Extract table schema as text for embedding."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    schema_docs = []
    table_previews = {}

    for (table_name,) in tables:
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        col_defs = [f"{col[1]} ({col[2]})" for col in columns]
        schema_text = f"Table: {table_name}\nColumns: {', '.join(col_defs)}"
        schema_docs.append(schema_text)

        # Preview data (first 3 rows)
        try:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3;")
            preview_rows = cursor.fetchall()
            table_previews[table_name] = preview_rows
        except Exception as e:
            print(f"Preview error for {table_name}: {e}")

    conn.close()
    return schema_docs, [t[0] for t in tables], table_previews


def execute_sql_query(db_path, query):
    """Execute SQL query and return results."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(query)
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    rows = cursor.fetchall()
    conn.close()
    return columns, rows


# ===============================
# Routes
# ===============================
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload_db", methods=["POST"])
def upload_db():
    """Handle SQLite DB upload and store schema in Chroma."""
    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
    file.save(filepath)

    # Extract schema
    schema_docs, tables, table_previews = get_db_schema(filepath)

    # Save session info
    session["current_db_path"] = filepath
    session["current_db_filename"] = unique_filename

    # Add schema embeddings to Chroma (with db filename)
    add_schema_to_chroma(collection, schema_docs, unique_filename)

    return jsonify({
        "message": "Database uploaded successfully.",
        "db_filename": unique_filename,
        "tables": tables,
        "table_previews": table_previews
    })


@app.route("/query", methods=["POST"])
def query():
    """Convert NL query → SQL using Groq + RAG + execute SQL."""
    data = request.get_json()
    nl_query = data.get("query", "")
    db_filename = data.get("db_filename")

    if not nl_query:
        return jsonify({"error": "No natural language query provided"}), 400

    if not db_filename:
        return jsonify({"error": "No database specified for query"}), 400

    db_path = os.path.join(app.config["UPLOAD_FOLDER"], db_filename)
    if not os.path.exists(db_path):
        return jsonify({"error": "Database not found on server"}), 404

    try:
        # === Retrieve schema context via RAG ===
        schema_context = retrieve_relevant_schema(collection, nl_query, db_filename)

        # === Prompt construction ===
        prompt = f"""
        You are an expert SQL assistant. 
        Based on the database schema below, convert the natural language question into a valid SQL query.

        Schema:
        {schema_context}

        Question:
        {nl_query}

        Return only the SQL query, no explanation.
        """

        # === Call Groq model ===
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-70b-versatile",
            temperature=0.1
        )
        sql_query = response.choices[0].message.content.strip()

        # === Execute SQL ===
        columns, rows = execute_sql_query(db_path, sql_query)

        return jsonify({
            "query": sql_query,
            "columns": columns,
            "rows": rows
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
