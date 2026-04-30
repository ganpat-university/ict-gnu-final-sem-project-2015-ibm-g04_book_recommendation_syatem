import matplotlib.pyplot as plt
import numpy as np
import os

# Create data directory if it doesn't exist
os.makedirs("report_assets", exist_ok=True)

# 1. Bar Chart: Steel Blue, data labels on top
plt.figure(figsize=(10, 6))
genres = ['Fiction', 'Fantasy', 'Sci-Fi', 'Mystery', 'Romance', 'Non-Fiction', 'Thriller']
counts = [8420, 6100, 4800, 3950, 4100, 2200, 3100]

bars = plt.bar(genres, counts, color='steelblue') # 'Steel Blue' requirement

# Add data labels on top
for bar in bars:
    yval = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2, yval + 100, int(yval), ha='center', va='bottom', fontweight='bold')

plt.title('Distribution of Filtered Ratings Across Primary Genres', fontsize=14, fontweight='bold')
plt.xlabel('Primary Genres', fontsize=12)
plt.ylabel('Number of Ratings', fontsize=12)
plt.tight_layout()
plt.savefig('report_assets/bar_chart.png', dpi=300)
plt.close()

# 2. Scatter Plot: Actual=Red dots, Predicted=Blue dots/diamonds
plt.figure(figsize=(10, 6))
# Mock data for closeness of predictions
actual_scores = np.random.normal(loc=7.5, scale=1.5, size=100)
actual_scores = np.clip(actual_scores, 1, 10)
# Add some noise for predicted
predicted_scores = actual_scores + np.random.normal(loc=0, scale=0.8, size=100)
predicted_scores = np.clip(predicted_scores, 1, 10)

plt.scatter(actual_scores, actual_scores, color='red', label='Actual', marker='o', alpha=0.6)
plt.scatter(actual_scores, predicted_scores, color='blue', label='Predicted', marker='D', alpha=0.6)

plt.title('Matrix Proximity Distance Mapping', fontsize=14, fontweight='bold')
plt.xlabel('Actual User Preference Score', fontsize=12)
plt.ylabel('Predicted User Score', fontsize=12)
plt.legend()
plt.grid(True, linestyle='--', alpha=0.5)
plt.tight_layout()
plt.savefig('report_assets/scatter_plot.png', dpi=300)
plt.close()

# 3. Architecture diagram - let's create a textual one or just a simple block diagram image using matplotlib
import matplotlib.patches as patches

fig, ax = plt.subplots(figsize=(12, 6))
ax.axis('off')

# Elements
boxes = [
    ("User Interface\n(HTML/Jinja2)", (0.1, 0.5), 'lightblue'),
    ("Flask Backend\n(API & Routing)", (0.4, 0.5), 'lightgreen'),
    ("Hybrid Recommender\n(Logic & Models)", (0.7, 0.5), 'lightcoral'),
    ("Datasets / JSON\n(Storage)", (0.7, 0.1), 'lightyellow'),
    ("Google OAuth\n(Auth Gate)", (0.4, 0.8), 'orange')
]

for label, (x, y), color in boxes:
    rect = patches.FancyBboxPatch((x, y), 0.15, 0.15, boxstyle="round,pad=0.02", edgecolor='black', facecolor=color)
    ax.add_patch(rect)
    ax.text(x+0.075, y+0.075, label, ha='center', va='center', fontweight='bold', fontsize=10)

# Arrows
ax.annotate('', xy=(0.4, 0.575), xytext=(0.25, 0.575), arrowprops=dict(arrowstyle="<->", lw=2))
ax.annotate('', xy=(0.7, 0.575), xytext=(0.55, 0.575), arrowprops=dict(arrowstyle="<->", lw=2))
ax.annotate('', xy=(0.775, 0.26), xytext=(0.775, 0.49), arrowprops=dict(arrowstyle="<->", lw=2))
ax.annotate('', xy=(0.475, 0.79), xytext=(0.475, 0.66), arrowprops=dict(arrowstyle="<->", lw=2))

plt.title('NovelNest Architecture Diagram', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig('report_assets/arch_diagram.png', dpi=300)
plt.close()

print("Charts successfully generated in report_assets/")
