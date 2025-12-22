import os
import geopandas as gpd

# Carregar o arquivo GeoJSON
gdf = gpd.read_file("demands.geojson")

# Verificar se as colunas UF e NM_MUN existem
if 'UF' not in gdf.columns or 'NM_MUN' not in gdf.columns:
    raise ValueError("O arquivo GeoJSON precisa conter as colunas 'UF' e 'NM_MUN'.")

# Pasta de saída
output_dir = "geojson_por_estado_cidade"
os.makedirs(output_dir, exist_ok=True)

# Iterar por estado
for estado in gdf['UF'].unique():
    gdf_estado = gdf[gdf['UF'] == estado]
    
    # Criar pasta para o estado
    estado_dir = os.path.join(output_dir, estado)
    os.makedirs(estado_dir, exist_ok=True)
    
    # Iterar por cidade dentro do estado
    for cidade in gdf_estado['NM_MUN'].unique():
        gdf_cidade = gdf_estado[gdf_estado['NM_MUN'] == cidade]
        
        # Sanitizar nome da cidade para o nome do arquivo
        nome_cidade = cidade.replace("/", "_").replace(" ", "_").replace("'", "")
        nome_arquivo = f"{nome_cidade}.geojson"
        caminho_arquivo = os.path.join(estado_dir, nome_arquivo)
        
        # Salvar como GeoJSON
        gdf_cidade.to_file(caminho_arquivo, driver="GeoJSON")

print("Arquivos GeoJSON gerados com sucesso por estado e cidade.")
