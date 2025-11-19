# Use an official Python runtime as a parent image
FROM python:3.13-slim

ENV TZ=Asia/Tashkent
# Install locales package and generate ru_RU.UTF-8 locale
# Install locales package and generate ru_RU.UTF-8 locale more thoroughly
RUN apt-get update && apt-get install -y --no-install-recommends locales \
    && sed -i -e 's/# ru_RU.UTF-8 UTF-8/ru_RU.UTF-8 UTF-8/' /etc/locale.gen \
    && locale-gen ru_RU.UTF-8 \
    && update-locale LANG=ru_RU.UTF-8 LC_ALL=ru_RU.UTF-8 \
    && dpkg-reconfigure --frontend=noninteractive locales \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for locale
ENV LANG=ru_RU.UTF-8
ENV LANGUAGE=ru_RU:ru
ENV LC_ALL=ru_RU.UTF-8

ENV FLASK_APP=app.py

# Set the working directory in the container
WORKDIR /app

# Copy requirements file first for better caching
COPY referal/requirements.txt .

# Install any needed packages specified in requirements.txt
# Use --no-cache-dir to reduce image size  
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared auth-connector package from parent directory
COPY auth-connector /tmp/auth-connector

# Install auth-connector (will be updated on each build with --force-reinstall)
RUN pip install --no-cache-dir --force-reinstall /tmp/auth-connector

# Copy the rest of the application code into the container at /app
COPY referal/ .

# Make port 80 available to the world outside this container
EXPOSE 80


# Set environment variable to use this file
ENV RESOLV_CONF=/etc/resolv.conf.override

# Run with gunicorn production server
# --workers 1: Use 1 worker process (single registration for service discovery)
# --bind 0.0.0.0:80: Listen on all interfaces, port 80
# --timeout 600: Timeout for worker processes (10 min for long-running sync tasks)
# --graceful-timeout 600: Graceful shutdown timeout
# --access-logfile -: Log requests to stdout
# --error-logfile -: Log errors to stdout
CMD ["gunicorn", "--workers", "1", "--bind", "0.0.0.0:80", "--timeout", "600", "--graceful-timeout", "600", "--access-logfile", "-", "--error-logfile", "-", "app_with_auth_connector:app"]
