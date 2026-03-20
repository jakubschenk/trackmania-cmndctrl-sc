FROM python:3.12-alpine
WORKDIR /app
COPY *.py ./
COPY tests/ ./tests/
CMD ["python", "-u", "main.py"]
