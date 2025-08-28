# Text-to-SQL with Visualization Tool

A powerful web application that converts natural language queries into SQL, executes them against SQLite databases, and provides data visualization capabilities. Built with Flask, Groq AI, and Docker.

![APP](text2sql)


## ✨ Features

- **Natural Language to SQL**: Convert plain English questions into SQL queries using Groq AI
- **Database Upload**: Easily upload and manage SQLite database files
- **Data Visualization**: Generate interactive charts (Bar, Line, Pie, Scatter) from query results
- **CSV Export**: Download query results as CSV files
- **Real-time Preview**: View database structure and sample data
- **Docker Support**: Fully containerized for easy deployment
- **Responsive UI**: Clean and intuitive web interface

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Groq API account ([Sign up here](https://console.groq.com/))


```bash
sql-to-text-app/
├── app.py                 # Main Flask application
├── index.html            # Frontend interface
├── requirements.txt      # Python dependencies
├── Dockerfile           # Docker configuration
├── docker-compose.yml   # Docker compose setup
├── uploaded_dbs/        # Uploaded database files (auto-created)
```

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Askhat26/chat_with_SQL
   cd sql-to-text-app

   Run with: docker-compose up --build   
  

### 🎯 Usage Guide
1. Upload a Database
Click "Choose File" and select your SQLite database (.db file)

Click "Upload" to load the database into the system

View database structure and table previews

2. Ask Questions in Natural Language
Examples of supported queries:

"Show all students with marks greater than 80"

"Display average sales by region"

"List employees by department with their salaries"

"Find top 5 performing products"

3. Visualize Results
After running a query, click "Visualize Data"

Select chart type (Bar, Line, Pie, Scatter)

Choose X and Y axis columns

Click "Generate Chart" to create visualization

4. Export Data
Click "Export to CSV" to download query results

Files are automatically generated and downloaded


### 📜 License

This project is licensed under the MIT License - see the LICENSE
 file for details.
