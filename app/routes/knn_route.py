import json
import uuid
import os
import pandas as pd
import io
import unicodedata
import logging
import zipfile

from fastapi import APIRouter, UploadFile, File, Query, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from enum import Enum
from app.preprocessing.common import prepare_data
from app.methods.knn_model import allocate_demands_knn
# CORREÇÃO AQUI: Importar do local correto
from app.preprocessing.utils import get_polygon_path 

from app.analysis.reporting import (
    analyze_allocation,
    create_allocation_charts,
    create_coverage_stats,
    create_distance_hist,
    generate_allocation_pdf,
    create_distance_boxplot,
    save_summary_table_image,
    create_summary_table
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Enum para métodos (Geodesic removido, Valhalla adicionado)
class MethodEnum(str, Enum):
    pandana_real_distance = "pandana_real_distance"
    pysal = "pysal"
    valhalla = "valhalla"  

# Enum para formatos de saída
class OutputFormatEnum(str, Enum):
    csv = "csv"
    geojson = "geojson"
    json = "json"

@router.post("/allocate_demands_knn/")
def allocate_demands_knn_api(
    opportunities_file: UploadFile,
    demands_file: UploadFile,
    num_threads: int = Query(0, description="Número de threads (0 = todos os núcleos)"),
    state: str = Query("", description="State (optional)"),
    city: str = Query("", description="City (optional)"),
    cities: str = Query("", description="Optional JSON array of cities for multi-city allocation"),
    k: int = Query(1, description="Number of neighbors for KNN"),
    method: MethodEnum = Query(MethodEnum.pysal, description="Choose the allocation method"),
    output_format: OutputFormatEnum = Query(OutputFormatEnum.csv, description="Output format: 'csv', 'geojson', or 'json'"),
    eda: bool = Query(False, description="If true, also perform EDA and return a ZIP with allocation and analysis results")
):
    threads = num_threads if num_threads > 0 else os.cpu_count()
    
    logger.info("Received request to allocate demands using KNN.")
    logger.info("Parameters: state=%s, city=%s, cities=%s, k=%d, method=%s, output_format=%s, eda=%s",
                state, city, cities, k, method, output_format, eda)

    opp_bytes = opportunities_file.file.read()
    dem_bytes = demands_file.file.read()

    cities_list = []
    if cities:
        try:
            cities_list = json.loads(cities)
            if not isinstance(cities_list, list):
                raise ValueError("Parameter 'cities' must be a JSON array.")
        except Exception as e:
            logger.exception("Error parsing 'cities' parameter.")
            raise HTTPException(status_code=400, detail="Invalid 'cities' parameter. Must be a JSON array string.")

    # Função auxiliar interna para preparar dados a partir dos bytes lidos
    def prepare_data_from_bytes(state: str = "", city_filter: str = ""):
        from app.preprocessing.common import prepare_data
        from io import BytesIO
        
        # Classe dummy para simular o comportamento de UploadFile para o prepare_data
        class FakeUploadFile:
            def __init__(self, content):
                self.file = content
        
        fake_opp = FakeUploadFile(io.BytesIO(opp_bytes))
        fake_dem = FakeUploadFile(io.BytesIO(dem_bytes))
        return prepare_data(fake_opp, fake_dem, state=state, city=city_filter)

    results_df_list = []

    if cities_list:
        logger.info("Allocating demands for multiple cities: %s", cities_list)
        for city_name in cities_list:
            # Prepara os dados filtrando (se a lógica interna permitir) ou carrega tudo para filtrar depois
            error, demands_gdf, opportunities_gdf, col_demand_id, col_name, col_city, col_state_opp, col_state_dem = prepare_data_from_bytes(
                state=state, city_filter=None
            )
            if error:
                logger.error("Error in prepare_data: %s", error)
                raise HTTPException(status_code=400, detail=str(error))
            
            # Normalização e filtro manual para garantir precisão
            city_norm = unicodedata.normalize("NFKD", city_name.strip().lower()).encode("ascii", "ignore").decode("utf-8")
            
            demands_city = demands_gdf[demands_gdf["NM_MUN"].astype(str).apply(lambda x: unicodedata.normalize("NFKD", x.strip().lower()).encode("ascii", "ignore").decode("utf-8")) == city_norm]
            
            # Tenta filtrar oportunidades pela coluna de cidade identificada
            if col_city:
                opp_city = opportunities_gdf[opportunities_gdf[col_city].astype(str).apply(lambda x: unicodedata.normalize("NFKD", x.strip().lower()).encode("ascii", "ignore").decode("utf-8")) == city_norm]
            else:
                # Se não achou coluna de cidade nas oportunidades, usa todas (fallback)
                opp_city = opportunities_gdf

            if demands_city.empty or opp_city.empty:
                logger.warning("No records found for city '%s'. Skipping.", city_name)
                continue
            
            logger.info("Allocating demands for city: %s", city_name)
            partial_df = allocate_demands_knn(
                demands_city,
                opp_city,
                col_demand_id,
                col_name,
                col_city,
                col_state_opp,
                k=k,
                method=method, # Passa 'valhalla' se selecionado
                city_name=city_name,
                num_threads=threads
            )
            partial_df["city_allocated"] = city_name
            results_df_list.append(partial_df)
        
        if not results_df_list:
            raise HTTPException(status_code=404, detail="No records found for any provided city.")
        result_df = pd.concat(results_df_list, ignore_index=True)
    else:
        logger.info("Allocating demands for single city='%s' or entire region if blank.", city)
        error, demands_gdf, opportunities_gdf, col_demand_id, col_name, col_city, col_state_opp, col_state_dem = prepare_data_from_bytes(
            state=state, city_filter=city
        )
        if error:
            logger.error("Error in prepare_data: %s", error)
            raise HTTPException(status_code=400, detail=str(error))
        
        result_df = allocate_demands_knn(
            demands_gdf,
            opportunities_gdf,
            col_demand_id,
            col_name,
            col_city,
            col_state_opp,
            k=k,
            method=method, # Passa 'valhalla' se selecionado
            city_name=city,
            num_threads=threads
        )

    logger.info("Allocation completed successfully. Number of rows in result: %d", len(result_df))

    if eda:
        logger.info("EDA option enabled. Generating analysis results.")
        import geopandas as gpd
        # Recarrega o GeoDataFrame original de demandas para o merge da EDA
        demanda_gdf = gpd.read_file(io.BytesIO(dem_bytes))
        
        merged_df, summary = analyze_allocation(result_df, demanda_gdf)
        logger.info("Analysis completed. Merged allocation shape: %s, Summary shape: %s", merged_df.shape, summary.shape)
        
        chart1_buf, chart2_buf = create_allocation_charts(summary)
        coverage_stats = create_coverage_stats(merged_df)
        distance_hist_buf = create_distance_hist(merged_df)
        resumo = create_summary_table(summary)
        table_image = save_summary_table_image(resumo)
        box_plot = create_distance_boxplot(merged_df)
        pdf_buf = generate_allocation_pdf(summary, merged_df)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            allocation_csv = result_df.to_csv(index=False)
            zipf.writestr("allocation_result.csv", allocation_csv)
            
            merged_json = merged_df.to_json(orient="records", force_ascii=False)
            zipf.writestr("merged_allocation.json", merged_json)
            
            summary_csv = summary.to_csv(index=False)
            zipf.writestr("summary.csv", summary_csv)
            
            zipf.writestr("chart_population.png", chart1_buf.getvalue())
            zipf.writestr("chart_racial.png", chart2_buf.getvalue())
            zipf.writestr("Table_resumo.png", table_image.getvalue())
            zipf.writestr("report.pdf", pdf_buf.getvalue())
            
            if not coverage_stats.empty:
                zipf.writestr("coverage_stats.csv", coverage_stats.to_csv(index=False))
            if distance_hist_buf:
                zipf.writestr("distance_hist.png", distance_hist_buf.getvalue())
            if box_plot:
                zipf.writestr("Box_plot.png", box_plot.getvalue())    
        
        zip_buffer.seek(0)
        logger.info("EDA analysis generated successfully. Returning ZIP file.")
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=allocation_eda_result.zip"}
        )
    else:
        file_id = str(uuid.uuid4())
        OUTPUT_DIR = "/tmp/api_output/"
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        logger.info("Saving allocation output to directory: %s", OUTPUT_DIR)

        if output_format == "csv":
            output_file = os.path.join(OUTPUT_DIR, f"allocation_result_{file_id}.csv")
            result_df.to_csv(output_file, index=False)
            logger.info("Returning CSV file: %s", output_file)
            return FileResponse(output_file, media_type="text/csv", filename=os.path.basename(output_file))
        elif output_format == "geojson":
            output_file = os.path.join(OUTPUT_DIR, f"allocation_result_{file_id}.geojson")
            result_df.to_json(output_file, index=False, orient="records")
            logger.info("Returning GeoJSON file: %s", output_file)
            return FileResponse(output_file, media_type="application/geo+json", filename=os.path.basename(output_file))
        elif output_format == "json":
            logger.info("Returning JSON response directly.")
            return JSONResponse(content=result_df.to_dict(orient="records"))
        else:
            logger.error("Invalid output format requested: %s", output_format)
            raise HTTPException(status_code=400, detail="Invalid output format. Use 'csv', 'geojson', or 'json'.")