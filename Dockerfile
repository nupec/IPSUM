FROM mambaorg/micromamba:1.5.10

WORKDIR /app

COPY --chown=$MAMBA_USER:$MAMBA_USER backend/environment.yml /tmp/environment.yml

RUN micromamba install -y -n base -f /tmp/environment.yml \
    && micromamba clean --all --yes

COPY --chown=$MAMBA_USER:$MAMBA_USER backend/ ./

COPY --chown=$MAMBA_USER:$MAMBA_USER backend_data/ /app/data/

USER root
RUN mkdir -p /app/data/uploads /app/data/results /app/cache \
    && chown -R $MAMBA_USER:$MAMBA_USER /app

USER $MAMBA_USER

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8050

CMD ["micromamba", "run", "-n", "base", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8050", "--timeout-keep-alive", "60"]
