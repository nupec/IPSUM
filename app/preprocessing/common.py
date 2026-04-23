import logging
import geopandas as gpd
from unidecode import unidecode
import pandas as pd

from app.preprocessing.geoprocessing import process_geometries
from app.preprocessing.utils import infer_column
from app.config import settings

logger = logging.getLogger(__name__)

def prepare_data(opportunities_file, demands_file, state=None, city=None):
    logger.info("Reading GeoDataFrames from uploaded files.")
    opportunities_gdf = gpd.read_file(opportunities_file.file)
    demands_gdf = gpd.read_file(demands_file.file)

    logger.info("Calling process_geometries on both GDFs.")
    opportunities_gdf = process_geometries(opportunities_gdf)
    demands_gdf = process_geometries(demands_gdf)

    logger.info("Inferring column names for demands and opportunities.")
    col_demand_id = infer_column(demands_gdf, settings.DEMAND_ID_POSSIBLE_COLUMNS)
    col_name = infer_column(opportunities_gdf, settings.NAME_POSSIBLE_COLUMNS)
    col_city = infer_column(opportunities_gdf, settings.CITY_POSSIBLE_COLUMNS)
    col_state_opportunities = infer_column(opportunities_gdf, settings.STATE_POSSIBLE_COLUMNS)
    col_state_demand = infer_column(demands_gdf, settings.STATE_POSSIBLE_COLUMNS)

    if not col_demand_id or not col_name or not col_city or not col_state_opportunities or not col_state_demand:
        logger.error("Could not infer all necessary columns. Check the input data.")
        return {"error": "Could not infer all necessary columns. Please check the input data."}, None, None, None, None, None

    if state:
        logger.info("Filtering by state='%s'.", state)
        opportunities_gdf = opportunities_gdf[opportunities_gdf[col_state_opportunities] == state]
        demands_gdf = demands_gdf[demands_gdf[col_state_demand] == state]
    else:
        logger.info("No state provided. Using entire dataset for allocation.")

    if city:
        logger.info("Filtering by city='%s'.", city)
        city = unidecode(city.lower())
        
        # Correção: Verifica se não é nulo antes de aplicar unidecode e lower
        safe_format = lambda x: unidecode(str(x).lower()) if pd.notnull(x) else ""
        
        opportunities_gdf = opportunities_gdf[opportunities_gdf[col_city].apply(safe_format) == city]
        demands_gdf = demands_gdf[demands_gdf['NM_MUN'].apply(safe_format) == city]

    logger.info("prepare_data completed successfully.")
    return None, demands_gdf, opportunities_gdf, col_demand_id, col_name, col_city, col_state_opportunities, col_state_demand
