import logging
import geopandas as gpd
import pandas as pd
import numpy as np
from app.config import settings
from unidecode import unidecode

logger = logging.getLogger(__name__)

# Limites para avaliação de cobertura obs: isso está embasado na portaria nº 2.436, de 21 de setembro de 2017
INTERVALO_MAX = 0.5  # 1 UBS para cada 2000 pessoas => 0.5/1000
INTERVALO_MIN = 0.29 # 1 UBS para cada ~3500 pessoas => ~0.29/1000

def find_column(possible_columns, df):
    """
    Função utilitária para encontrar o nome real de uma coluna em um DataFrame
    com base em uma lista de nomes possíveis, ignorando acentos e capitalização.
    """
    normalized_cols = {unidecode(c).lower(): c for c in df.columns}
    for candidate in possible_columns:
        cand_norm = unidecode(candidate).lower()
        if cand_norm in normalized_cols:
            real_name = normalized_cols[cand_norm]
            logger.info("Coluna '%s' encontrada.", real_name)
            return real_name
    logger.warning("Nenhuma coluna encontrada dentre: %s", possible_columns)
    return None

def analyze_knn_allocation(knn_df, demands_gdf, opportunities_gdf, settings):
    """
    Analisa os resultados de uma alocação KNN.

    Esta função é mantida especificamente para a rota 'consulta_base',
    pois ela retorna os dados no formato de DICIONÁRIO que a UI (frontend)
    espera receber.

    Retorna:
     - allocation (dict): Dicionário com estatísticas por UBS.
     - summary_data (dict): Dicionário com estatísticas gerais da cidade.
    """

    logger.info("Iniciando análise socioeconômica (para UI) a partir de um DataFrame KNN.")

    # ----------------------------
    # 1) Identifica colunas de população e raça no demands_gdf
    # ----------------------------
    pop_column = find_column(settings.POPULATION_POSSIBLE_COLUMNS, demands_gdf)
    black_column = find_column(settings.BLACK_POPULATION_POSSIBLE_COLUMNS, demands_gdf)
    brown_column = find_column(settings.BROWN_POPULATION_POSSIBLE_COLUMNS, demands_gdf)
    indigenous_column = find_column(settings.INDIGENOUS_POPULATION_POSSIBLE_COLUMNS, demands_gdf)
    yellow_column = find_column(settings.YELLOW_POPULATION_POSSIBLE_COLUMNS, demands_gdf)
    sector_column = find_column(settings.DEMAND_ID_POSSIBLE_COLUMNS, demands_gdf)

    if not pop_column or not sector_column:
        logger.error("Colunas essenciais (População ou ID de Setor) não encontradas em demands_gdf.")
        raise ValueError("Nenhuma coluna correspondente à população ou ID do setor encontrada.")

    # Conversão de chave de merge para string
    # [NOTA]: O knn_df já deve ter 'demand_id' como str
    knn_df["demand_id"] = knn_df["demand_id"].astype(str)
    demands_gdf[sector_column] = demands_gdf[sector_column].astype(str)

    # ----------------------------
    # 2) Calcula população total da cidade
    # ----------------------------
    total_people_city = demands_gdf.drop_duplicates(subset=[sector_column])[pop_column].sum()
    logger.info("População total da cidade calculada: %s", total_people_city)

    # Calcula total para grupos raciais
    total_people_negros = demands_gdf.drop_duplicates(subset=[sector_column])[black_column].sum() if black_column else 0
    total_people_pardos = demands_gdf.drop_duplicates(subset=[sector_column])[brown_column].sum() if brown_column else 0
    total_people_indigenas = demands_gdf.drop_duplicates(subset=[sector_column])[indigenous_column].sum() if indigenous_column else 0
    total_people_amarela = demands_gdf.drop_duplicates(subset=[sector_column])[yellow_column].sum() if yellow_column else 0

    # ----------------------------
    # 3) Conta total de UBS
    # ----------------------------
    total_ubs = len(opportunities_gdf)
    ubs_per_1000 = (total_ubs / total_people_city) * 1000 if total_people_city > 0 else 0

    if ubs_per_1000 >= INTERVALO_MAX:
        ubs_situation = "Suficiente"
    elif ubs_per_1000 >= INTERVALO_MIN:
        ubs_situation = "Intermediário"
    else:
        ubs_situation = "Deficitário"

    # ----------------------------
    # 4) Colunas para identificar cada UBS
    # ----------------------------
    cnes_column = find_column(settings.ESTABLISHMENT_ID_POSSIBLE_COLUMNS, opportunities_gdf)
    city_column = find_column(settings.CITY_POSSIBLE_COLUMNS, opportunities_gdf)
    name_column = find_column(settings.NAME_POSSIBLE_COLUMNS, opportunities_gdf)

    if not cnes_column or not city_column or not name_column:
        logger.error("Colunas essenciais para estabelecimento não encontradas.")
        raise ValueError("Colunas essenciais (CNES, cidade, nome) não encontradas em opportunities_gdf.")

    # Cria um "mapa" do nome da oportunidade -> (cnes, city, nome_ubs)
    establishments_map = {}
    for idx, row in opportunities_gdf.iterrows():
        key_name = str(row[name_column])  
        cnes_val = row[cnes_column]
        city_val = row[city_column]
        ub_name = row[name_column]
        establishments_map[key_name] = (cnes_val, city_val, ub_name)

    # ----------------------------
    # 5) Mescla knn_df com demands_gdf para trazer colunas de população e raça
    # ----------------------------
    
    # Define as colunas a serem mescladas (apenas as que existem)
    cols_to_merge = [sector_column, pop_column]
    if black_column: cols_to_merge.append(black_column)
    if brown_column: cols_to_merge.append(brown_column)
    if indigenous_column: cols_to_merge.append(indigenous_column)
    if yellow_column: cols_to_merge.append(yellow_column)
    
    merged = knn_df.merge(
        demands_gdf[cols_to_merge],
        left_on="demand_id",
        right_on=sector_column,
        how="left"
    )

    # ----------------------------
    # 6) Agrupa por "opportunity_name" e calcular estatísticas
    # ----------------------------
    grouped = merged.groupby("opportunity_name")
    
    allocation = {}

    for opp_name, subdf in grouped:
        # Distância média em km
        mean_distance_km = subdf["distance_km"].mean() if not subdf["distance_km"].isnull().all() else 0.0
        # Converte para metros para a UI
        mean_distance_m = mean_distance_km * 1000.0

        if mean_distance_m <= 700:
            radius = 'Ótima (700m)'
        elif mean_distance_m <= 1000:
            radius = 'Boa (1000m)'
        elif mean_distance_m <= 2000:
            radius = 'Regular (2000m)'
        else:
            radius = 'Ruim (>2000m)'

        # Soma das populações atendidas
        total_people_ubs = subdf[pop_column].sum()
        percentage_ubs = (total_people_ubs / total_people_city) * 100 if total_people_city > 0 else 0

        total_negros = subdf[black_column].sum() if black_column else 0
        total_pardos = subdf[brown_column].sum() if brown_column else 0
        total_indigenas = subdf[indigenous_column].sum() if indigenous_column else 0
        total_amarela = subdf[yellow_column].sum() if yellow_column else 0

        percentage_ubs_negros = (total_negros / total_people_negros * 100) if total_people_negros > 0 else 0
        percentage_ubs_pardos = (total_pardos / total_people_pardos * 100) if total_people_pardos > 0 else 0
        percentage_ubs_indigenas = (total_indigenas / total_people_indigenas * 100) if total_people_indigenas > 0 else 0
        percentage_ubs_amarela = (total_amarela / total_people_amarela * 100) if total_people_amarela > 0 else 0

        # Recuperar info do establishments_map
        if opp_name in establishments_map:
            cnes_val, city_val, ub_name = establishments_map[opp_name]
        else:
            # Se não encontrou, define placeholders
            cnes_val = f"Desconhecido_{opp_name}"
            city_val = "?"
            ub_name = opp_name  # fallback

        # Monta o dicionário final
        allocation[cnes_val] = {
            'Establishment': city_val,      
            'UBS_Name': ub_name,            
            'Radius': radius,
            'Mean_Distance': mean_distance_m,  # Em METROS, para a UI
            'Total_People': total_people_ubs,
            'Total_People_Negros': total_negros,
            'Total_People_Pardos': total_pardos,
            'Total_People_Indigenas': total_indigenas,
            'Total_People_Amarela': total_amarela,
            'Percentage_City': percentage_ubs,
            'Percentage_Negros': percentage_ubs_negros,
            'Percentage_Pardos': percentage_ubs_pardos,
            'Percentage_Indigenas': percentage_ubs_indigenas,
            'Percentage_Amarela': percentage_ubs_amarela,
        }

    logger.info("Análise (UI) finalizada para %d estabelecimentos (UBS).", len(allocation))

    # ----------------------------
    # 7) Monta summary_data
    # ----------------------------
    summary_data = {
        "Total_City_Population": total_people_city,
        "Total_UBS": total_ubs,
        "UBS_per_1000": ubs_per_1000,
        "UBS_Situation": ubs_situation
    }

    logger.info("Resumo (UI) calculado: %s", summary_data)
    return allocation, summary_data
