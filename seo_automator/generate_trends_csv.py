import csv

# Example trending keywords (replace or expand as needed)
trending_keywords = [
    "AI video generator",
    "AI image editor",
    "Content automation",
    "Marketing automation",
    "SEO optimization",
    "Generative AI tools",
    "AI blog writing",
    "AI content creation",
    "Video marketing trends",
    "AI-powered design"
]

with open("trends.csv", "w", newline='', encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["keyword"])  # header
    for keyword in trending_keywords:
        writer.writerow([keyword])

print("trends.csv created with example keywords.")