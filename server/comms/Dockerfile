FROM python:3.8-slim-buster as base

FROM base as builder

RUN apt-get update && apt-get install -y --no-install-recommends tzdata

WORKDIR /root
COPY requirements.txt /requirements.txt
RUN pip install --user -r /requirements.txt

FROM base

COPY --from=builder /root/.local /root/.local
COPY --from=builder /usr/share/zoneinfo/Europe/London /etc/localtime
RUN echo "Europe/London" > /etc/timezone

ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1

COPY app.py /root/
WORKDIR /root


ENTRYPOINT ["python", "-m", "flask", "run"]
