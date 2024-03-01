# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the Pipfile and Pipfile.lock to the container
COPY Pipfile Pipfile.lock /app/

# Install pipenv
RUN pip install pipenv

# Install project dependencies
RUN pipenv install

RUN pipenv install gunicorn

# Copy the local code to the container
COPY flask-server.py /app/

# Expose the port the app runs on
EXPOSE 5000

# Define environment variables
ENV FLASK_APP=flask-server.py
ENV FLASK_RUN_HOST=0.0.0.0

# Run the application
ENTRYPOINT pipenv run gunicorn --workers 2 --access-logfile - --log-level info --bind 0.0.0.0:5000 flask-server:app
