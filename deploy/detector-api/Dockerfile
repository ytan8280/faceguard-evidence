FROM python:3.12.10-slim-bookworm@sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY requirements-detector-api.txt /tmp/requirements-detector-api.txt
RUN pip install --no-cache-dir \
    torch==2.14.1+cpu \
    torchvision==0.29.1+cpu \
    --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r /tmp/requirements-detector-api.txt
RUN pip uninstall -y opencv-python \
    && pip install --no-cache-dir --force-reinstall \
        opencv-python-headless==4.10.0.84

ENTRYPOINT ["python"]
