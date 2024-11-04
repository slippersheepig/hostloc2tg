FROM python:alpine
WORKDIR /h2tg
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "main.py"]
