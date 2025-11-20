FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

# Build your personal gallery metadata inside the image
RUN python src/pipeline.py

EXPOSE 8080

CMD ["python", "-m", "flask", "--app", "src/app.py", "run", "--host=0.0.0.0", "--port=8080"]

