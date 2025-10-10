
import io, base64
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")

def generate_chart(data, labels, chart_type="bar", title="Chart", x_label="X Axis", y_label="Y Axis"):
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
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
    
    ax.set_title(title, fontsize=16, fontweight='bold')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
    buffer.seek(0)
    plt.close(fig)
    
    return f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode('utf-8')}"
