FROM continuumio/miniconda3

WORKDIR /app

COPY environment.yml .

RUN conda env update -n base -f environment.yml && conda clean -afy

COPY . .

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8050

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8050", "--timeout-keep-alive", "60"]
