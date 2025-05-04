# Use the official Python image
FROM python:3.12

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y iputils-ping telnet net-tools && apt-get clean

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install django-cors-headers gunicorn

# Copy project files
COPY . .

# Copy environment variables file
COPY .env .env

# Expose the application port
EXPOSE 8000

# Run migrations and start Gunicorn with debugging
CMD ["sh", "-c", "echo 'Starting migrations...' && python manage.py makemigrations --noinput && python manage.py migrate --noinput && echo 'Starting Gunicorn...' && gunicorn --workers=2 --timeout=60 --bind 0.0.0.0:8000 register.wsgi:application --log-level debug"]