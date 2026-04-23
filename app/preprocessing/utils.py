import logging
import os
from unidecode import unidecode

logger = logging.getLogger(__name__)

def infer_column(gdf, possible_names):
    logger.debug("Inferring column from possible names: %s", possible_names)
    for name in possible_names:
        columns = [col for col in gdf.columns if unidecode(col).lower() == unidecode(name).lower()]
        if columns:
            logger.info("Inferred column '%s' from the provided list: %s", columns[0], possible_names)
            return columns[0]
    logger.warning("No column found for the possible names: %s", possible_names)
    return None

def get_polygon_path(base_dir, uf, city):
    """
    Busca o arquivo CSV de polígono no diretório data/municipios-poligonos/{UF}/{CITY}.csv
    """
    if not uf or not city:
        return None
        
    # Normalização: Remove acentos, maiúsculas, espaços viram underline
    # Ex: "São Paulo" -> "SAO_PAULO"
    city_norm = unidecode(city).upper().replace(" ", "_").replace("'", "")
    uf_norm = uf.upper()
    
    # O base_dir geralmente é a raiz do backend ou onde está a pasta data
    # No Docker, /app/data é montado. Se base_dir for passado corretamente:
    poly_path = os.path.join(base_dir, "municipios-poligonos", uf_norm, f"{city_norm}.csv")
    
    if os.path.exists(poly_path):
        logger.info(f"Arquivo de polígono encontrado: {poly_path}")
        return poly_path
    
    logger.warning(f"Arquivo de polígono não encontrado em: {poly_path}")
    return None