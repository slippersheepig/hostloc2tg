FROM python:alpine
WORKDIR /h2tg
RUN apk add --no-cache gcc musl-dev
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "main.py"]
