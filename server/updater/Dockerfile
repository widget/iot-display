FROM python:3.6-slim-buster as base

FROM base as builder

RUN apt-get update && apt-get install -y --no-install-recommends build-essential tzdata

WORKDIR /root
COPY requirements.txt /requirements.txt
RUN pip install --user -r /requirements.txt

FROM base

COPY --from=builder /root/.local /root/.local
COPY --from=builder /usr/share/zoneinfo/Europe/London /etc/localtime
RUN echo "Europe/London" > /etc/timezone
COPY . /root
WORKDIR /root

CMD python tideclock_generator.py -c /data/mine.cfg