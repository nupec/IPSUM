import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
import pandas as pd
import geopandas as gpd
from io import BytesIO
import zipfile

# Importações de lógica de análise do módulo centralizado
from app.analysis.reporting import (
    analyze_allocation,
    create_allocation_charts,
    create_coverage_stats,
    create_distance_boxplot,
    create_distance_hist,
    generate_allocation_pdf,
    create_summary_table,
    save_summary_table_image
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/allocation")
async def eda_allocation_endpoint(
    allocation_file: UploadFile = File(...),
    demanda_file: UploadFile = File(...),
):
    """
    Endpoint que recebe:
      - O arquivo CSV de alocação (output da API, contendo os cálculos de distância já realizados,
        incluindo as novas colunas 'Destination_State' e 'Destination_City')
      - O arquivo demanda.geojson (com informações socioeconômicas adicionais, como população, raça, etc.)
    
    Realiza o merge entre os dois arquivos usando a função 'analyze_allocation' (centralizada),
    gera estatísticas, gráficos e um relatório PDF, e retorna todos os resultados em um arquivo ZIP.
    """
    
    logger = logging.getLogger(__name__)

    try:
        logger.info("Recebendo arquivo CSV de alocação.")
        allocation_content = await allocation_file.read()
        allocation_df = pd.read_csv(BytesIO(allocation_content))
        logger.info("Arquivo CSV de alocação lido. Linhas: %d, Colunas: %d", allocation_df.shape[0], allocation_df.shape[1])
        
        logger.info("Recebendo arquivo GeoJSON de demandas.")
        demanda_content = await demanda_file.read()
        demanda_gdf = gpd.read_file(BytesIO(demanda_content))
        logger.info("Arquivo GeoJSON de demandas lido. Linhas: %d, Colunas: %d", demanda_gdf.shape[0], len(demanda_gdf.columns))

        logger.info("Iniciando processo de análise e merge.")
        # Chama a função IMPORTADA de app.analysis.reporting
        merged_df, summary = analyze_allocation(allocation_df, demanda_gdf)
        
        if merged_df.empty or summary.empty:
            logger.error("Falha no merge ou análise. DataFrames resultantes estão vazios.")
            raise HTTPException(status_code=400, detail="Erro ao processar e mesclar os arquivos. Verifique se as colunas de ID (ex: CD_SETOR) são compatíveis.")

        logger.info("Análise concluída. Tamanho do DataFrame mesclado: %s, e summary: %s", merged_df.shape, summary.shape)
        logger.info("Gerando gráficos (chart_population, chart_racial).")
        chart1_buf, chart2_buf = create_allocation_charts(summary)
        
        logger.info("Gerando relatório PDF.")
        pdf_buf = generate_allocation_pdf(summary, merged_df)

        # Gera estatísticas adicionais de cobertura
        coverage_stats = create_coverage_stats(merged_df)

        # Gera histograma de distâncias
        distance_hist_buf = create_distance_hist(merged_df)

        logger.info("Gerando gráfico boxplot.")
        box_plo_distence = create_distance_boxplot(merged_df)
        
        logger.info("Gerando tabela mais descritiva por UBS")
        resumo = create_summary_table(summary)
        table_image = save_summary_table_image(resumo)

        logger.info("Empacotando resultados em um arquivo ZIP.")
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            # 1) JSON com a alocação mesclada
            json_str = merged_df.to_json(orient="records", force_ascii=False)
            zipf.writestr("merged_allocation.json", json_str)

            # 2) CSV com o resumo
            zipf.writestr("summary.csv", summary.to_csv(index=False))

            # 3) PNGs (chart_population, chart_racial)
            zipf.writestr("chart_population.png", chart1_buf.getvalue())
            zipf.writestr("chart_racial.png", chart2_buf.getvalue())

            logger.info('Table gerada')
            zipf.writestr("table_image.png", table_image.getvalue())

            # 4) PDF
            zipf.writestr("report.pdf", pdf_buf.getvalue())

            # 5) coverage_stats.csv (se coverage_stats não estiver vazio)
            if not coverage_stats.empty:
                coverage_csv = coverage_stats.to_csv(index=False)
                zipf.writestr("coverage_stats.csv", coverage_csv)

            # 6) distance_hist.png (se gerado)
            if distance_hist_buf:
                zipf.writestr("distance_hist.png", distance_hist_buf.getvalue())

            # 7) [CORREÇÃO DE BUG] Salva o boxplot com um nome de arquivo diferente
            if box_plo_distence:
                zipf.writestr("distance_boxplot.png", box_plo_distence.getvalue())

        zip_buffer.seek(0)
        logger.info("Processo finalizado com sucesso. Retornando arquivo ZIP.")
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=eda_allocation_results.zip"}
        )
    except Exception as e:
        logger.exception("Erro ao processar os arquivos na rota EDA allocation.")
        raise HTTPException(status_code=400, detail=f"Erro ao processar os arquivos: {e}")
