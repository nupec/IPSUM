import logging
import geopandas as gpd
import pandas as pd
import numpy as np
from libpysal.cg import KDTree
from scipy.spatial import cKDTree 

logger = logging.getLogger(__name__)

def allocate_demands_pysal(
    demands_gdf: gpd.GeoDataFrame,
    opportunities_gdf: gpd.GeoDataFrame,
    col_demand_id: str,
    col_name: str,
    k: int = 1
) -> pd.DataFrame:
    """
    Aloca demandas às oportunidades mais próximas usando uma KD-Tree do PySAL (via SciPy).

    Args:
        demands_gdf (gpd.GeoDataFrame): GeoDataFrame com os pontos de demanda.
        opportunities_gdf (gpd.GeoDataFrame): GeoDataFrame com os pontos de oportunidade.
        col_demand_id (str): Nome da coluna de ID nas demandas.
        col_name (str): Nome da coluna de nome/ID nas oportunidades.
        k (int): O número de vizinhos mais próximos a encontrar.

    Returns:
        pd.DataFrame: Um DataFrame longo com [demand_id, opportunity_name, distance_km].
    """
    logger.info(f"Iniciando alocação com PySAL/KDTree para k={k}.")

    # CRS comum como o Web Mercator (EPSG:3857).
    if demands_gdf.crs != "EPSG:3857":
        logger.debug("Reprojetando demandas para EPSG:3857.")
        demands_gdf = demands_gdf.to_crs(epsg=3857)
    if opportunities_gdf.crs != "EPSG:3857":
        logger.debug("Reprojetando oportunidades para EPSG:3857.")
        opportunities_gdf = opportunities_gdf.to_crs(epsg=3857)

    # Extrair as coordenadas como arrays NumPy
    demand_coords = np.array(list(demands_gdf.geometry.apply(lambda p: (p.x, p.y))))
    opportunity_coords = np.array(list(opportunities_gdf.geometry.apply(lambda p: (p.x, p.y))))

    # cKDTree de SciPy info
    logger.info(f"Construindo KD-Tree com {len(opportunity_coords)} oportunidades.")
    kdtree = cKDTree(opportunity_coords)

    # A consulta retorna (distâncias, índices)
    logger.info(f"Consultando a árvore para {len(demand_coords)} demandas.")
    distances_m, indices = kdtree.query(demand_coords, k=k)

    # O resultado precisa ser "achatado" (long format) se k > 1
    if k == 1:
        results_df = pd.DataFrame({
            'demand_id': demands_gdf[col_demand_id],
            'opportunity_index': indices,
            'distance_m': distances_m
        })
    else:
        # Se k > 1, kdtree.query retorna um array de arrays. Precisamos expandi-lo.
        demand_ids_repeated = np.repeat(demands_gdf[col_demand_id].values, k)
        results_df = pd.DataFrame({
            'demand_id': demand_ids_repeated,
            'opportunity_index': indices.flatten(),
            'distance_m': distances_m.flatten()
        })
    
    # Mapear os índices de volta para os nomes das oportunidades
    opportunity_names = opportunities_gdf.iloc[results_df['opportunity_index']][col_name].values
    results_df['opportunity_name'] = opportunity_names
    
    # Converter distância de metros para km
    results_df['distance_km'] = results_df['distance_m'] / 1000.0

    # Limpar e retornar o DataFrame final no formato esperado
    final_df = results_df[['demand_id', 'opportunity_name', 'distance_km']]
    
    logger.info(f"Alocação com PySAL concluída. {len(final_df)} alocações geradas.")
    return final_df