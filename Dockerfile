FROM ollama/ollama:latest AS ollama-base

FROM python:3.11-slim-bookworm

WORKDIR /app

COPY --from=ollama-base /usr/bin/ollama /usr/bin/ollama
COPY --from=ollama-base /lib/x86_64-linux-gnu/libncursesw.so.* /lib/x86_64-linux-gnu/
COPY --from=ollama-base /lib/x86_64-linux-gnu/libedit.so* /lib/x86_64-linux-gnu/
COPY --from=ollama-base /lib/x86_64-linux-gnu/libpthread.so* /lib/x86_64-linux-gnu/
COPY --from=ollama-base /lib/x86_64-linux-gnu/libcrypto.so* /lib/x86_64-linux-gnu/
COPY --from=ollama-base /lib/x86_64-linux-gnu/libssl.so* /lib/x86_64-linux-gnu/
COPY --from=ollama-base /lib/x86_64-linux-gnu/libz.so* /lib/x86_64-linux-gnu/
COPY --from=ollama-base /lib/x86_64-linux-gnu/libc.so* /lib/x86_64-linux-gnu/
COPY --from=ollama-base /lib/x86_64-linux-gnu/libtinfo* /lib/x86_64-linux-gnu/
COPY --from=ollama-base /lib/x86_64-linux-gnu/libgcc_s.so* /lib/x86_64-linux-gnu/

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV OLLAMA_HOST=0.0.0.0
ENV OLLAMA_MODEL=llama3.2:1b
ENV OLLAMA_BASE_URL=http://localhost:11434

COPY <<"EOF" /etc/supervisor/conf.d/supervisord.conf
[supervisord]
nodaemon=true
user=root
logfile=/tmp/supervisord.log
logfile_maxbytes=0

[program:ollama]
command=/usr/bin/ollama serve
autostart=true
autorestart=true
stdout_logfile=/tmp/ollama.log
stderr_logfile=/tmp/ollama.err

[program:model-puller]
command=/bin/sh -c "sleep 5 && /usr/bin/ollama pull llama3.2:1b && touch /tmp/model_ready"
autostart=true
autorestart=false
stdout_logfile=/tmp/puller.log
stderr_logfile=/tmp/puller.err
startsecs=0

[program:api-server]
command=/bin/sh -c "while [ ! -f /tmp/model_ready ]; do sleep 2; done && python scripts/api_server.py"
autostart=true
autorestart=true
stdout_logfile=/tmp/api.log
stderr_logfile=/tmp/api.err
EOF

EXPOSE 8080 11434

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
