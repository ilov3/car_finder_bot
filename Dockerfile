FROM python:3.7

ENV PYTHONUNBUFFERED=1
ADD requirements.txt .
RUN pip install -r requirements.txt

COPY . /app
WORKDIR /app

CMD ["python", "run_bot.py"]
