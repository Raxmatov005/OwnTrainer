# Use the official Python image
FROM python:3.12

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Install system dependencies (optional, for debugging)
RUN apt-get update && apt-get install -y iputils-ping telnet && apt-get clean

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install django-cors-headers
# Copy project files into the container
COPY . .

# Copy environment variables file
COPY .env .env

# Expose the application port
EXPOSE 8000

# Run migrations and start Gunicorn
CMD ["sh", "-c", "gunicorn --workers=2 --timeout=60 --bind 0.0.0.0:8000 register.wsgi:application"]


# python manage.py makemigrations --noinput && python manage.py migrate --noinput &&
