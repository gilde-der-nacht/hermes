FROM alpine:3.14
RUN apk update
RUN apk add --no-cache python3 py3-pip py3-wheel py3-yarl py3-multidict
WORKDIR /src
COPY requirements.txt .
RUN pip3 install --requirement requirements.txt
COPY src /src
ENTRYPOINT ["python3", "main.py"]
