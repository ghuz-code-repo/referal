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

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# Use --no-cache-dir to reduce image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . .

# Make port 80 available to the world outside this container
EXPOSE 80


# Set environment variable to use this file
ENV RESOLV_CONF=/etc/resolv.conf.override

# Run app.py using flask run (or python app.py if preferred)
CMD ["python", "app.py"]