FROM python:3.12.1-slim

RUN pip install jinja2==3.1.2

COPY src /app/src/

CMD /app/src/main.py
