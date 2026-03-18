FROM python:3.12-alpine
WORKDIR /app
COPY main.py .
CMD ["python", "-u", "main.py"]
