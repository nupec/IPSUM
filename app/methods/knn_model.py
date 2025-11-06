import logging
import pandas as pd
import os
from fastapi import HTTPException


from app.methods.geodesic_distance import geodesic_distance_matrix
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
    method="geodesic",
    city_name=None,
    num_threads: int = 1
):
    """
    Orquestra a alocação de demandas usando vários métodos de vizinhos mais próximos (KNN).

    Esta função atua como um controlador que seleciona o método de cálculo da distância 
    (geodésica, PySAL, ou Pandana) e, em seguida, enriquece os resultados com
    dados geográficos e estatísticas agregadas.

    Args:
        demands_gdf (gpd.GeoDataFrame): GeoDataFrame das demandas.
        opportunities_gdf (gpd.GeoDataFrame): GeoDataFrame das oportunidades.
        col_demand_id (str): Nome da coluna de ID nas demandas.
        col_name (str): Nome da coluna de nome/ID nas oportunidades.
        col_city (str): Nome da coluna da cidade nas oportunidades.
        col_state (str): Nome da coluna do estado nas oportunidades.
        k (int): Número de vizinhos a serem encontrados.
        method (str): O método de cálculo de distância ('geodesic', 'pysal', 'pandana_real_distance').
        city_name (str, optional): Nome da cidade para filtragem e cache. Defaults to None.
        num_threads (int): Número de threads para processamento paralelo. Defaults to 1.

    Returns:
        pd.DataFrame: DataFrame com os resultados da alocação.
    """
    if num_threads < 1:
        num_threads = os.cpu_count() or 1
        
    logger.info(
        "Iniciando alocação KNN com método='%s', k=%d, cidade=%s, threads=%d",
        method, k, city_name, num_threads
    )

    # DataFrame que conterá o resultado da alocação no formato longo
    knn_df = None

    # --- Bloco de Seleção de Método de Distância ---
    
    if method == "geodesic":
        logger.info("Usando matriz de distância geodésica (força bruta).")
        # 1. Calcula a matriz de distância completa (lento)
        dist_df = geodesic_distance_matrix(demands_gdf, opportunities_gdf, col_demand_id, col_name)
        logger.debug("Matriz de distância geodésica calculada. Shape: %s", dist_df.shape)
        # 2. Seleciona os k vizinhos a partir da matriz
        knn_df = select_knn_from_distance_matrix(dist_df, k=k)

    elif method == "pandana_real_distance":
        logger.info("Usando matriz de distância de rede viária (Pandana).")
        # 1. Calcula a matriz de distância baseada em rotas de rua (usando Pandana)
        dist_df = pandana_distance_matrix(
            demands_gdf,
            opportunities_gdf,
            col_demand_id,
            col_name,
            city_name=city_name,
            num_threads=num_threads
        )
        logger.debug("Matriz de distância Pandana calculada. Shape: %s", dist_df.shape)
        # 2. Seleciona os k vizinhos a partir da matriz
        knn_df = select_knn_from_distance_matrix(dist_df, k=k)

    # [MODIFICAÇÃO] Integração do método PySAL
    elif method == "pysal":
        logger.info("Usando KD-Tree (PySAL/SciPy) para alocação por proximidade.")
        knn_df = allocate_demands_pysal(
            demands_gdf, opportunities_gdf, col_demand_id, col_name, k=k
        )

    else:
        logger.error("Método de alocação inválido especificado: '%s'", method)
        raise HTTPException(
            status_code=400,
            detail="Método inválido. Use 'geodesic', 'pysal', ou 'pandana_real_distance'."
        )

    if knn_df is None or knn_df.empty:
        logger.warning("O DataFrame de alocação (knn_df) está vazio após a execução do método '%s'.", method)

        return pd.DataFrame(columns=[
            'demand_id', 'Destination_State', 'Destination_City', 'opportunity_name',
            'Origin_Lat', 'Origin_Lon', 'Destination_Lat', 'Destination_Lon',
            'distance_km', 'distance_mean', 'distance_variance'
        ])

    logger.info("Alocação KNN concluída. %d registros gerados.", len(knn_df))
    
    
    # Adiciona coordenadas (Lat/Lon) e informações de cidade/estado ao resultado
    logger.info("Juntando resultados do KNN com os GeoDataFrames originais para enriquecimento.")
    result_df = join_knn_with_geometries(
        knn_df, demands_gdf, opportunities_gdf, col_demand_id, col_name, col_city, col_state
    )
    logger.info("Junção com geometrias completa. Total de linhas: %d", len(result_df))

    # Calcula estatísticas agregadas de distância por oportunidade
    logger.info("Calculando estatísticas de distância (média e variância) por oportunidade.")
    stats = result_df.groupby('opportunity_name')['distance_km'].agg(
        distance_mean='mean',
        distance_variance=lambda x: x.var(ddof=0)  
    ).reset_index()
    result_df = result_df.merge(stats, on='opportunity_name', how='left')

    # Reordenar as colunas conforme a ordem desejada
    desired_order = [
        'demand_id',
        'Destination_State',
        'Destination_City',
        'opportunity_name',
        'Origin_Lat',
        'Origin_Lon',
        'Destination_Lat',
        'Destination_Lon',
        'distance_km',
        'distance_mean',
        'distance_variance'
    ]
    
    # Garante que apenas colunas existentes sejam selecionadas para evitar KeyErrors
    final_columns = [col for col in desired_order if col in result_df.columns]
    result_df = result_df[final_columns]

    logger.info("Processo de alocação KNN finalizado com sucesso.")
    return result_df