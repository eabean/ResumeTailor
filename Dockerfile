FROM python:3.12-slim

# Install tectonic runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    libssl-dev \
    libfontconfig1 \
    libharfbuzz0b \
    libicu-dev \
    && rm -rf /var/lib/apt/lists/*

# Install tectonic
RUN curl --proto '=https' --tlsv1.2 -fsSL \
    https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.15.0/tectonic-0.15.0-x86_64-unknown-linux-musl.tar.gz \
    | tar -xz -C /usr/local/bin/

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data

EXPOSE 8501

CMD ["streamlit", "run", "app/main.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
