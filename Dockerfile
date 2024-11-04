FROM python:alpine
WORKDIR /h2tg
COPY . .
RUN apk add --no-cache ca-certificates openssl && \
    update-ca-certificates && \
    pip install --no-cache-dir -r requirements.txt
CMD ["python", "main.py"]
