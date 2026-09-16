FROM python:3.11-slim

WORKDIR /app

# ለ MoviePy እና ሌሎች ሲስተም ፋይሎች የሚያስፈልጉትን 툴ዎች መጫን
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# ላይብረሪዎችን መጫን
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# የኮድ ፋይሎቹን ወደ ሰርቨሩ ማስተላለፍ
COPY . .

# ቦቱን ማስጀመር
CMD ["python3", "main.py"]
