import logging
import pandas as pd
import numpy as np
from unidecode import unidecode

from app.preprocessing.network import compute_distance_matrix
from app.methods.geodesic_distance import calculate_geodesic_distance

logger = logging.getLogger(__name__)

def pandana_distance_matrix(
    demands_gdf,
    opportunities_gdf,
    col_demand_id,
    col_name,
    city_name=None,
    #max_distance=50000,
    max_distance=10000,
    num_threads=1
):
    logger.info("Constructing distance matrix with Pandana (real distance). city_name=%s", city_name)
    distance_df, network, graph, nodes, edges, demand_nodes, ubs_nodes = compute_distance_matrix(
        demands_gdf,
        opportunities_gdf,
        city_name=city_name,
        max_distance=max_distance,
        num_threads=num_threads
    )
    logger.debug("Distance matrix shape from compute_distance_matrix: %s", distance_df.shape)
    # Convert meters to kilometers
    distance_df = distance_df / 1000.0

    # Fallback for zero distances
    logger.info("Checking for zero distances. Will replace with geodesic if found.")
    for demand_id in distance_df.index:
        row = distance_df.loc[demand_id]
        zero_cols = row[row == 0.0].index
        if len(zero_cols) > 0:
            demand_row = demands_gdf[demands_gdf[col_demand_id] == demand_id].iloc[0]
            demand_point = (demand_row.geometry.y, demand_row.geometry.x)

            for opp_name in zero_cols:
                # Match by normalized name
                opportunities_row = opportunities_gdf[opportunities_gdf[col_name].apply(lambda x: unidecode(x).lower()) 
                                                      == unidecode(opp_name).lower()]
                if not opportunities_row.empty:
                    opp = opportunities_row.iloc[0]
                    opp_point = (opp.geometry.y, opp.geometry.x)
                    dist_geo = calculate_geodesic_distance(demand_point, opp_point)
                    distance_df.loc[demand_id, opp_name] = dist_geo

    logger.info("Pandana distance matrix complete. Final shape: %s", distance_df.shape)
    return distance_df
