FROM python:alpine
WORKDIR /h2tg
RUN apk add --no-cache gcc musl-dev libffi-dev
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
RUN apk del gcc musl-dev libffi-dev
CMD ["python", "main.py"]
