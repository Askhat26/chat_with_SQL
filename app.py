import os
import sqlite3
import json
import csv
import io
import uuid
from flask import Flask, request, jsonify, send_from_directory, session, send_file
from werkzeug.utils import secure_filename
from groq import Groq
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import matplotlib
import base64
import pandas as pd
matplotlib.use("Agg")
# Load environment variables
load_dotenv()

# Flask app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")

# Config for uploads
UPLOAD_FOLDER = "uploaded_dbs"
ALLOWED_EXTENSIONS = {"db"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


HOST = '0.0.0.0' if os.environ.get('DOCKERIZED') else '127.0.0.1'
# Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_chart(data, labels, chart_type="bar", title="Chart", x_label="X Axis", y_label="Y Axis"):
    """Generate different types of charts and return as base64 encoded image"""
    try:
        # Create figure and axis explicitly
        fig, ax = plt.subplots(figsize=(10, 6))
        
        if chart_type == "bar":
            ax.bar(labels, data, color='skyblue', edgecolor='black')
        elif chart_type == "line":
            ax.plot(labels, data, marker='o', linestyle='-', color='blue')
        elif chart_type == "pie":
            ax.pie(data, labels=labels, autopct='%1.1f%%', startangle=90)
            ax.axis('equal')
        elif chart_type == "scatter":
            ax.scatter(range(len(data)), data, color='red', alpha=0.6)
        
        if chart_type != "pie":
            ax.set_xlabel(x_label, fontsize=12)
            ax.set_ylabel(y_label, fontsize=12)
        
        ax.set_title(title, fontsize=16, fontweight='bold')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        # Save to buffer
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)  # Close the figure explicitly
        
        # Convert to base64
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f"data:image/png;base64,{img_base64}"
    except Exception as e:
        print(f"Chart generation error: {e}")
        return None

def get_table_names(db_path):
    """Get all table names from the database"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [table[0] for table in cursor.fetchall()]
        conn.close()
        return tables
    except Exception as e:
        print(f"Error getting table names: {e}")
        return []

def get_table_preview(db_path, table_name, limit=5):
    """Get a preview of table data"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit};")
        rows = cursor.fetchall()
        colnames = [description[0] for description in cursor.description] if cursor.description else []
        conn.close()
        return colnames, rows
    except Exception as e:
        print(f"Error getting table preview: {e}")
        return [], []

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/upload_db", methods=["POST"])
def upload_db():
    if "dbfile" not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files["dbfile"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
        file.save(filepath)
        
        # Get database schema information
        tables = get_table_names(filepath)
        table_previews = {}
        for table in tables:
            columns, rows = get_table_preview(filepath, table)
            table_previews[table] = {
                "columns": columns,
                "preview": rows
            }
        
        session["current_db"] = filepath
        session["original_filename"] = filename
        session["tables"] = tables
        session["table_previews"] = table_previews
        
        return jsonify({
            "message": "Database uploaded successfully", 
            "db": filename,
            "unique_id": unique_filename,
            "tables": tables,
            "table_previews": table_previews
        })
    
    return jsonify({"error": "Invalid file type"}), 400

@app.route("/query", methods=["POST"])
def query():
    current_db_path = session.get("current_db")
    
    if not current_db_path or not os.path.exists(current_db_path):
        return jsonify({"error": "No database uploaded or database file not found"}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400
    
    nl_query = data.get("query", "")
    if not nl_query:
        return jsonify({"error": "No query provided"}), 400

    try:
        # Prompt Groq to convert NL -> SQL
        schema_prompt = """You are a SQL assistant. Convert the following natural language request into an SQLite query.
        Only return the SQL query, nothing else.

        User request: {nl_query}
        SQL:""".format(nl_query=nl_query)

        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": schema_prompt}],
            temperature=0.1
        )
        
        sql_query = response.choices[0].message.content.strip()
        if sql_query.startswith("```sql"):
            sql_query = sql_query[6:]
        if sql_query.startswith("```"):
            sql_query = sql_query[3:]
        if sql_query.endswith("```"):
            sql_query = sql_query[:-3]
        sql_query = sql_query.strip()

        # Execute SQL safely
        conn = sqlite3.connect(current_db_path)
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        colnames = [description[0] for description in cursor.description] if cursor.description else []
        conn.close()
        
        return jsonify({
            "sql": sql_query, 
            "columns": colnames, 
            "rows": rows,
            "row_count": len(rows)
        })
        
    except sqlite3.Error as e:
        return jsonify({"error": f"SQLite error: {str(e)}", "sql": sql_query}), 400
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

@app.route("/visualize", methods=["POST"])
def visualize():
    """Generate visualization for any data"""
    current_db_path = session.get("current_db")
    
    if not current_db_path or not os.path.exists(current_db_path):
        return jsonify({"error": "No database uploaded"}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    sql_query = data.get("sql", "")
    chart_type = data.get("chart_type", "bar")
    x_column = data.get("x_column", "")
    y_column = data.get("y_column", "")
    
    if not sql_query:
        return jsonify({"error": "No SQL query provided"}), 400

    try:
        # Execute SQL query
        conn = sqlite3.connect(current_db_path)
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        colnames = [description[0] for description in cursor.description] if cursor.description else []
        conn.close()
        
        if not rows or not colnames:
            return jsonify({"error": "No data returned from query"}), 400
        
        # Convert to DataFrame for easier manipulation
        df = pd.DataFrame(rows, columns=colnames)
        
        # Determine which columns to use for visualization
        if not x_column and not y_column:
            # Auto-detect: use first column for x, first numeric for y
            x_column = colnames[0]
            numeric_columns = df.select_dtypes(include=['number']).columns
            if len(numeric_columns) > 0:
                y_column = numeric_columns[0]
            else:
                return jsonify({"error": "No numeric columns found for visualization"}), 400
        
        # Prepare data for charting
        if x_column in df.columns and y_column in df.columns:
            x_data = df[x_column].tolist()
            y_data = df[y_column].tolist()
            
            # Generate chart
            chart_image = generate_chart(
                y_data, 
                [str(x) for x in x_data], 
                chart_type,
                f"{y_column} by {x_column}",
                x_column,
                y_column
            )
            
            if chart_image:
                return jsonify({
                    "success": True,
                    "chart_image": chart_image,
                    "x_column": x_column,
                    "y_column": y_column,
                    "chart_type": chart_type
                })
            else:
                return jsonify({"error": "Failed to generate chart"}), 400
        else:
            return jsonify({"error": "Specified columns not found in results"}), 400
            
    except Exception as e:
        return jsonify({"error": f"Visualization error: {str(e)}"}), 500

@app.route("/export_csv", methods=["POST"])
def export_csv():
    """Export query results to CSV"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    columns = data.get("columns", [])
    rows = data.get("rows", [])
    
    if not columns or not rows:
        return jsonify({"error": "No data to export"}), 400
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(columns)
    
    # Write data
    for row in rows:
        writer.writerow(row)
    
    # Prepare response
    output.seek(0)
    
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='query_results.csv'
    )

@app.route("/current_db", methods=["GET"])
def get_current_db():
    current_db_path = session.get("current_db")
    if current_db_path and os.path.exists(current_db_path):
        return jsonify({
            "status": "database_loaded",
            "filename": session.get("original_filename", "unknown"),
            "tables": session.get("tables", []),
            "table_previews": session.get("table_previews", {})
        })
    return jsonify({"status": "no_database"})

# Serve static files
@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

if __name__ == "__main__":
    app.run(host=HOST, debug=os.environ.get('FLASK_ENV') == 'development')