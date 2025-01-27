# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Create a working directory for the app
WORKDIR /app

# Install dumb-init (for proper signal handling)
RUN apt-get update && \
    apt-get install -y --no-install-recommends dumb-init && \
    rm -rf /var/lib/apt/lists/*


COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code to the container
COPY . .

# Expose port 5000 for the Flask app
EXPOSE 5000

# Use dumb-init as the container entrypoint
ENTRYPOINT ["/usr/bin/dumb-init", "--"]

# By default, run the Flask app
# You can pass additional arguments at runtime if needed
CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "5000"]
