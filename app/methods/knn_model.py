import logging
import pandas as pd
import os
from fastapi import HTTPException

# Importações de métodos internos
from app.methods.pandana_distance import pandana_distance_matrix
from app.methods.pysal_allocation import allocate_demands_pysal
from app.methods.valhalla_distance import get_valhalla_matrix
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
    method="pysal", 
    city_name=None,
    num_threads: int = 1
):
    """
    Realiza a alocação KNN utilizando o método escolhido.
    Se o método for 'valhalla', inclui uma camada de fallback para 'pysal' em caso de erro.
    """
    if num_threads < 1:
        num_threads = os.cpu_count() or 1
        
    logger.info(
        "Iniciando alocação KNN com método='%s', k=%d, cidade=%s, threads=%d",
        method, k, city_name, num_threads
    )

    knn_df = None

    # --- 1. Método Pandana (Rede Viária Local via OSMnx) ---
    if method == "pandana_real_distance":
        logger.info("Executando alocação via Pandana (Rede Viária).")
        dist_df = pandana_distance_matrix(
            demands_gdf,
            opportunities_gdf,
            col_demand_id,
            col_name,
            city_name=city_name,
            num_threads=num_threads
        )
        knn_df = select_knn_from_distance_matrix(dist_df, k=k)

    # --- 2. Método Valhalla (Docker) com FALLBACK Geodésico ---
    elif method == "valhalla":
        logger.info("Tentando motor de rotas Valhalla...")
        try:
            dist_df = get_valhalla_matrix(
                demands_gdf,
                opportunities_gdf,
                col_demand_id,
                col_name
            )
            
            # Se a matriz voltou vazia ou toda preenchida com NaN (falha em todos os lotes)
            if dist_df.empty or dist_df.isna().all().all():
                raise ValueError("Valhalla não retornou distâncias válidas (matriz vazia ou NaN).")

            logger.info("✅ Alocação via Valhalla realizada com sucesso.")
            knn_df = select_knn_from_distance_matrix(dist_df, k=k)

        except Exception as e:
            # MECANISMO DE RESILIÊNCIA: Se o Valhalla falhar, não paramos o processo.
            logger.warning(f"⚠️ FALHA NO VALHALLA para {city_name}: {e}")
            logger.warning("🔄 ATIVANDO FALLBACK: Calculando via Distância Geodésica (PySAL/KD-Tree)...")
            
            knn_df = allocate_demands_pysal(
                demands_gdf, 
                opportunities_gdf, 
                col_demand_id, 
                col_name, 
                k=k,
            )

            if knn_df is not None and not knn_df.empty:
                knn_df['fallback_used'] = True 
            
            # Sinaliza nos logs que o resultado desta cidade é aproximado
            logger.info(f"✅ Fallback concluído para {city_name}.")

    # --- 3. Método PySAL (KD-Tree / Distância Geodésica Rápida) ---
    elif method == "pysal":
        logger.info("Executando alocação via PySAL (KD-Tree).")
        knn_df = allocate_demands_pysal(
            demands_gdf, 
            opportunities_gdf, 
            col_demand_id, 
            col_name, 
            k=k
        )

    else:
        logger.error("Método de alocação inválido: '%s'", method)
        raise HTTPException(
            status_code=400,
            detail="Método inválido. Use 'pysal', 'valhalla' ou 'pandana_real_distance'."
        )

    # --- Tratamento de Resultados Vazios ---
    if knn_df is None or knn_df.empty:
        logger.warning("Nenhum registro de alocação gerado para %s.", city_name)
        return pd.DataFrame(columns=[
            'demand_id', 'Destination_State', 'Destination_City', 'opportunity_name',
            'Origin_Lat', 'Origin_Lon', 'Destination_Lat', 'Destination_Lon',
            'distance_km', 'distance_mean', 'distance_variance'
        ])

    # --- Enriquecimento e Junção com Dados Geográficos ---
    logger.info("Enriquecendo resultados com atributos de origem e destino.")
    result_df = join_knn_with_geometries(
        knn_df, demands_gdf, opportunities_gdf, col_demand_id, col_name, col_city, col_state
    )

    # --- Cálculo de Estatísticas por Oportunidade (UBS) ---
    logger.info("Calculando médias de distância por unidade.")
    stats = result_df.groupby('opportunity_name')['distance_km'].agg(
        distance_mean='mean',
        distance_variance=lambda x: x.var(ddof=0) if len(x) > 1 else 0.0
    ).reset_index()
    
    result_df = result_df.merge(stats, on='opportunity_name', how='left')


# --- Ordenação Final das Colunas ---
    desired_order = [
        'demand_id', 'Destination_State', 'Destination_City', 'opportunity_name',
        'distance_km', 'distance_mean', 'distance_variance',
        'Origin_Lat', 'Origin_Lon', 'Destination_Lat', 'Destination_Lon',
        'fallback_used'  
    ]
    
    # O filtro abaixo agora deixará a coluna passar se ela existir
    final_columns = [col for col in desired_order if col in result_df.columns]
    result_df = result_df[final_columns]

    logger.info("Processo de alocação KNN finalizado com sucesso para %s.", city_name)
    return result_df