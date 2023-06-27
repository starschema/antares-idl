FROM python:3.10

WORKDIR /app_pred

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# load or predict
# ENV LOAD_MODE="load"

ENTRYPOINT ["./entrypoint.sh"]