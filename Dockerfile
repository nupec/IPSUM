FROM continuumio/miniconda3

WORKDIR /app

# 1. Copia apenas o environment.yml primeiro
COPY environment.yml .

# 2. Instala dependências. Isso ficará em cache se o environment.yml não mudar.
# Adicionamos o 'conda clean' para deixar a imagem menor.
RUN conda env update -n base -f environment.yml && conda clean -afy

# 3. SÓ AGORA copia o código fonte. Se você mudar o código, o Docker só refaz daqui pra baixo.
COPY . .

# Variáveis para melhorar logs e performance do Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8050

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8050", "--timeout-keep-alive", "60"]