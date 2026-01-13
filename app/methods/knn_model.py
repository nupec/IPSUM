import logging
import pandas as pd
import os
from fastapi import HTTPException

# --- ALTERAÇÃO: Removida a importação de geodesic_distance_matrix ---
from app.methods.pandana_distance import pandana_distance_matrix
from app.methods.pysal_allocation import allocate_demands_pysal
from app.methods.knn_allocation import select_knn_from_distance_matrix, join_knn_with_geometries

logger = logging.getLogger(__name__)

def allocate_demands_knn(
    demands_gdf,
    opportunities_gdf,
    col_demand_id,
    col_name,
    col_city,
    col_state,  
    k=1,
    method="pysal", # Novo padrão
    city_name=None,
    num_threads: int = 1
):
    if num_threads < 1:
        num_threads = os.cpu_count() or 1
        
    logger.info(
        "Iniciando alocação KNN com método='%s', k=%d, cidade=%s, threads=%d",
        method, k, city_name, num_threads
    )

    knn_df = None

    # --- Bloco de Seleção de Método ---
    
    if method == "pandana_real_distance":
        logger.info("Usando matriz de distância de rede viária (Pandana).")
        dist_df = pandana_distance_matrix(
            demands_gdf,
            opportunities_gdf,
            col_demand_id,
            col_name,
            city_name=city_name,
            num_threads=num_threads
        )
        logger.debug("Matriz de distância Pandana calculada. Shape: %s", dist_df.shape)
        knn_df = select_knn_from_distance_matrix(dist_df, k=k)

    # [MODIFICAÇÃO] PySAL agora é o padrão para "geodésica" (euclidiana rápida)
    elif method == "pysal":
        logger.info("Usando KD-Tree (PySAL/SciPy) para alocação por proximidade.")
        knn_df = allocate_demands_pysal(
            demands_gdf, opportunities_gdf, col_demand_id, col_name, k=k
        )

    # Removido o bloco "geodesic" antigo

    else:
        logger.error("Método de alocação inválido especificado: '%s'", method)
        raise HTTPException(
            status_code=400,
            detail="Método inválido. Use 'pysal' (para Geodésica) ou 'pandana_real_distance' (para Real)."
        )

    if knn_df is None or knn_df.empty:
        logger.warning("O DataFrame de alocação (knn_df) está vazio após a execução do método '%s'.", method)
        return pd.DataFrame(columns=[
            'demand_id', 'Destination_State', 'Destination_City', 'opportunity_name',
            'Origin_Lat', 'Origin_Lon', 'Destination_Lat', 'Destination_Lon',
            'distance_km', 'distance_mean', 'distance_variance'
        ])

    logger.info("Alocação KNN concluída. %d registros gerados.", len(knn_df))
    
    logger.info("Juntando resultados do KNN com os GeoDataFrames originais para enriquecimento.")
    result_df = join_knn_with_geometries(
        knn_df, demands_gdf, opportunities_gdf, col_demand_id, col_name, col_city, col_state
    )
    logger.info("Junção com geometrias completa. Total de linhas: %d", len(result_df))

    logger.info("Calculando estatísticas de distância (média e variância) por oportunidade.")
    stats = result_df.groupby('opportunity_name')['distance_km'].agg(
        distance_mean='mean',
        distance_variance=lambda x: x.var(ddof=0)  
    ).reset_index()
    result_df = result_df.merge(stats, on='opportunity_name', how='left')

    desired_order = [
        'demand_id', 'Destination_State', 'Destination_City', 'opportunity_name',
        'Origin_Lat', 'Origin_Lon', 'Destination_Lat', 'Destination_Lon',
        'distance_km', 'distance_mean', 'distance_variance'
    ]
    
    final_columns = [col for col in desired_order if col in result_df.columns]
    result_df = result_df[final_columns]

    logger.info("Processo de alocação KNN finalizado com sucesso.")
    return result_df