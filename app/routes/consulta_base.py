from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime
from io import BytesIO
from typing import Dict, Tuple
from unidecode import unidecode 

import geopandas as gpd
import pandas as pd
import requests
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from app.analysis.socioeconomic_analys import analyze_knn_allocation
from app.config import settings
from app.lib.convert_numpy import convert_numpy_types
from app.methods.knn_model import allocate_demands_knn
from app.preprocessing.common import prepare_data
from app.analysis.reporting import (
    analyze_allocation,  
    create_allocation_charts,
    create_coverage_stats,
    create_distance_boxplot,
    create_distance_hist,
    create_summary_table,
    generate_allocation_pdf,
    save_summary_table_image,
    gerar_perguntas_respostas,
)

# ------------------------------------------------------------------ #
#  Configuração básica                                               #
# ------------------------------------------------------------------ #
num_threads = os.cpu_count()
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/consulta_base")

BACK_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

DEMANDS_BASE_DIR   = os.path.join(BACK_ROOT, "data", "geojson_por_estado_cidade")
OPPORTUNITIES_PATH = os.path.join(BACK_ROOT, "data", "opportunities.geojson")


# --- ATUALIZAÇÃO PARA DOCKER ---
SHARED_DIR = "/shared"
os.makedirs(SHARED_DIR, exist_ok=True)
FRONT_DATA_DIR   = SHARED_DIR
FRONT_CONFIG_DIR = SHARED_DIR
FRONTEND_UPLOAD_URL = os.getenv("FRONTEND_UPLOAD_URL")

# ------------------------------------------------------------------ #
#  Cache de ZIPs (TTL simples)                                       #
# ------------------------------------------------------------------ #
ZIP_CACHE: Dict[str, Tuple[datetime, bytes]] = {}
ZIP_TTL_MIN = 30


def _clean_zip_cache() -> None:
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(minutes=ZIP_TTL_MIN)
    for k, (ts, _) in list(ZIP_CACHE.items()):
        if ts < cutoff:
            del ZIP_CACHE[k]


# ------------------------------------------------------------------ #
#  Funções de apoio                                                  #
# ------------------------------------------------------------------ #
def _uid() -> str:
    return uuid.uuid4().hex[:7]


def build_kepler_config(
    csv_filename: str,
    center_lat: float,
    center_lon: float,
    zoom: float = 8.6,
    lat_o: str = "Origin_Lat",
    lon_o: str = "Origin_Lon",
    lat_d: str = "Destination_Lat",
    lon_d: str = "Destination_Lon",
) -> dict:
    """Cria dinamicamente a configuração do KeplerGL."""
    origin_id, dest_id, arc_id, line_id = (_uid() for _ in range(4))

    TEMPERATURE_RANGE = {
        "name": "Temperature",
        "type": "sequential",
        "category": "Uber",
        "colors": [
            "#2b83ba", "#4ea0c0", "#71b7c8", "#92cad0", "#b4dcd5",
            "#f4e0c0", "#fdb663", "#f57d4e", "#d7191c"
        ],
        "reversed": False,
    }

    def point_layer(layer_id, label, color, lat, lon, radius, opacity):
        return {
            "id": layer_id,
            "type": "point",
            "config": {
                "dataId": csv_filename,
                "label": label,
                "color": color,
                "highlightColor": [252, 242, 26, 255],
                "columns": {"lat": lat, "lng": lon, "altitude": None},
                "isVisible": True,
                "visConfig": {
                    "radius": radius,
                    "fixedRadius": False,
                    "opacity": opacity,
                    "outline": False,
                    "thickness": 2,
                    "strokeColor": None,
                    "radiusRange": [0, 50],
                    "filled": True,
                },
                "hidden": False,
                "textLabel": [],
            },
            "visualChannels": {
                "colorField": None,
                "colorScale": "quantile",
                "strokeColorField": None,
                "strokeColorScale": "quantile",
                "sizeField": None,
                "sizeScale": "linear",
            },
        }

    origin_layer = point_layer(_uid(), "origin", [117, 222, 227], lat_o, lon_o, 10, 0.31)
    destination_layer = point_layer(_uid(), "destination", [227, 26, 26], lat_d, lon_d, 15.4, 0.8)

    arc_layer = {
        "id": arc_id,
        "type": "arc",
        "config": {
            "dataId": csv_filename,
            "label": "origin → destination arc",
            "color": [100, 100, 100],
            "highlightColor": [255, 255, 255],
            "columns": {"lat0": lat_o, "lng0": lon_o, "lat1": lat_d, "lng1": lon_d},
            "isVisible": True,
            "visConfig": {
                "opacity": 0.8,
                "thickness": 2,
                "sizeRange": [0, 10],
                "colorRange": TEMPERATURE_RANGE,
            },
            "hidden": False,
            "textLabel": [],
        },
        "visualChannels": {
            "colorField": {"name": "distance_km", "type": "real"},
            "colorScale": "quantile",
        },
    }

    line_layer = {
        "id": line_id,
        "type": "line",
        "config": {
            "dataId": csv_filename,
            "label": "origin → destination line",
            "color": [130, 154, 227],
            "highlightColor": [252, 242, 26, 255],
            "columns": {
                "lat0": lat_o, "lng0": lon_o, "alt0": None,
                "lat1": lat_d, "lng1": lon_d, "alt1": None
            },
            "isVisible": False,
            "visConfig": {"opacity": 0.8, "thickness": 2},
            "hidden": False,
            "textLabel": [],
        },
    }

    return {
        "version": "v1",
        "config": {
            "visState": {
                "filters": [],
                "layers": [origin_layer, destination_layer, arc_layer, line_layer],
                "interactionConfig": {
                    "tooltip": {
                        "fieldsToShow": {
                            csv_filename: [
                                {"name": "demand_id"},
                                {"name": "Destination_State"},
                                {"name": "Destination_City"},
                                {"name": "opportunity_name"},
                                {"name": "Origin_Lat"},
                            ]
                        },
                        "enabled": True,
                    }
                },
                "layerBlending": "normal",
                "splitMaps": [],
            },
            "mapState": {
                "bearing": -33,
                "dragRotate": True,
                "latitude": round(center_lat, 6),
                "longitude": round(center_lon, 6),
                "pitch": 59,
                "zoom": zoom,
                "isSplit": False,
            },
            "mapStyle": {"styleType": "dark"},
        },
    }


def _upload_to_frontend(map_id: str, csv_path: str, cfg_path: str) -> str | None:
    """Envia CSV/JSON ao endpoint /api/upload_map do frontend."""
    if not FRONTEND_UPLOAD_URL:
        logger.info("FRONTEND_UPLOAD_URL não definido – pulando upload.")
        return None
    logger.info("Enviando mapa para front‑end: %s", FRONTEND_UPLOAD_URL)
    try:
        with open(csv_path, "rb") as f_csv, open(cfg_path, "rb") as f_cfg:
            files = {
                "map_id":   (None, map_id),
                "csv_file": ("map.csv", f_csv, "text/csv"),
                "cfg_file": ("map.json", f_cfg, "application/json"),
            }
            resp = requests.post(FRONTEND_UPLOAD_URL, files=files, timeout=30)
        resp.raise_for_status()
        link = resp.json().get("link")
        logger.info("Upload concluído – link recebido: %s", link)
        return link
    except Exception as e:
        logger.error("Falha no upload: %s", e, exc_info=True)
        return None


# ------------------------------------------------------------------ #
# [ALTERAÇÃO] Pré-carregamento foi removido. Rotas agora são dinâmicas. #
# ------------------------------------------------------------------ #

@router.get("/ufs")
def get_ufs():
    """[NOVO] Obtém a lista de UFs dinamicamente listando os diretórios."""
    try:
        if not os.path.exists(DEMANDS_BASE_DIR):
             raise FileNotFoundError("Diretório base de demandas não encontrado.")
        # Lista apenas os diretórios que correspondem a nomes de UFs (ex: 2 letras)
        ufs = [d for d in os.listdir(DEMANDS_BASE_DIR) if os.path.isdir(os.path.join(DEMANDS_BASE_DIR, d)) and len(d) == 2]
        return sorted(ufs)
    except Exception as e:
        logger.error("Erro ao listar UFs do diretório: %s", e)
        return JSONResponse(status_code=500, content={"error": f"Não foi possível carregar a lista de estados: {e}"})


@router.get("/municipios")
def get_municipios(uf: str = Query("")):
    """[NOVO] Obtém a lista de municípios dinamicamente listando os arquivos."""
    if not uf:
        return []
    try:
        uf_path = os.path.join(DEMANDS_BASE_DIR, uf.upper())
        if not os.path.isdir(uf_path):
            return [] # Retorna lista vazia se o diretório da UF não existir
        
        # Lista arquivos, remove a extensão .geojson e substitui '_' por ' '
        files = [f for f in os.listdir(uf_path) if f.lower().endswith('.geojson')]
        cities = [os.path.splitext(f)[0].replace('_', ' ') for f in files]
        return sorted(cities)
    except Exception as e:
        logger.error("Erro ao listar municípios para a UF '%s': %s", uf, e)
        return JSONResponse(status_code=500, content={"error": f"Não foi possível carregar os municípios para {uf}: {e}"})

# ------------------------------------------------------------------ #
#  Rota principal                                                    #
# ------------------------------------------------------------------ #
@router.get("/resultado_completo")
def consulta_completa(uf: str, municipio: str, tipo: str = Query("geodesic")):
    try:
        logger.info("Consulta UF=%s | Mun=%s | Tipo=%s", uf, municipio, tipo)

        # ---------- 1. prepara dados ----------
        
        # [ALTERAÇÃO] Lógica de carregamento de arquivo de demanda agora é dinâmica.
        # Normaliza o nome do município para corresponder ao padrão de nome de arquivo (MAIÚSCULAS, _ no lugar de espaço).
        municipio_filename = f"{unidecode(municipio.upper().replace(' ', '_'))}.geojson"
        demands_file_path = os.path.join(DEMANDS_BASE_DIR, uf.upper(), municipio_filename)

        logger.info("Tentando carregar arquivo de demanda de: %s", demands_file_path)

        if not os.path.exists(demands_file_path):
            logger.error("Arquivo de demanda não encontrado: %s", demands_file_path)
            # Tenta uma variação sem unidecode como fallback
            municipio_filename_fallback = f"{municipio.upper().replace(' ', '_')}.geojson"
            demands_file_path = os.path.join(DEMANDS_BASE_DIR, uf.upper(), municipio_filename_fallback)
            if not os.path.exists(demands_file_path):
                 logger.error("Arquivo de demanda (fallback) também não encontrado: %s", demands_file_path)
                 raise HTTPException(status_code=404, detail=f"Arquivo de dados para o município '{municipio}' não encontrado.")

        class _Buf:
            def __init__(self, f): self.file = f

        # [ALTERAÇÃO] Abre o arquivo de demanda específico da cidade e o arquivo de oportunidades completo.
        with open(demands_file_path, "rb") as dem_f, open(OPPORTUNITIES_PATH, "rb") as opp_f:
            err, demands_gdf, opps_gdf, col_did, col_name, col_city, col_state_opp, _ = prepare_data(
                _Buf(opp_f), _Buf(dem_f), state=uf, city=municipio
            )
        
        if err:
            return JSONResponse(status_code=500, content={"erro": err})
        if demands_gdf.empty or opps_gdf.empty:
            return JSONResponse(status_code=404, content={"erro": "Sem dados suficientes para a localidade."})

        # ---------- 2. KNN + resumo ----------
        df_knn = allocate_demands_knn(
            demands_gdf, opps_gdf,
            col_did, col_name, col_city, col_state_opp,
            k=1, method=tipo, city_name=municipio, num_threads=num_threads
        )
        allocation_dict, city_summary = analyze_knn_allocation(df_knn, demands_gdf, opps_gdf, settings=settings)

        # ---------- 3. artefatos EDA ----------
        merged_df, summary_ubs = analyze_allocation(df_knn, demands_gdf)
        perguntas_guiadas       = gerar_perguntas_respostas(summary_ubs, merged_df)

        chart_pop_buf, chart_racial_buf = create_allocation_charts(summary_ubs)
        coverage_stats_df = create_coverage_stats(merged_df)
        hist_buf    = create_distance_hist(merged_df)
        boxplot_buf = create_distance_boxplot(merged_df)
        resumo_df   = create_summary_table(summary_ubs)
        resumo_img_buf = save_summary_table_image(resumo_df)
        pdf_buf = generate_allocation_pdf(summary_ubs, merged_df)

        # ---------- 4. ZIP em cache ----------
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("allocation_result.csv", df_knn.to_csv(index=False))
            z.writestr("allocation_merged.json", merged_df.to_json(orient="records", force_ascii=False))
            z.writestr("city_summary.json", json.dumps(convert_numpy_types(city_summary)))
            z.writestr("ubs_summary.csv", summary_ubs.to_csv(index=False))
            z.writestr("chart_population.png", chart_pop_buf.getvalue())
            z.writestr("chart_racial.png", chart_racial_buf.getvalue())
            z.writestr("table_indicadores.png", resumo_img_buf.getvalue())
            z.writestr("report.pdf", pdf_buf.getvalue())
            if not coverage_stats_df.empty:
                z.writestr("coverage_stats.csv", coverage_stats_df.to_csv(index=False))
            if hist_buf:
                z.writestr("distance_hist.png", hist_buf.getvalue())
            if boxplot_buf:
                z.writestr("distance_boxplot.png", boxplot_buf.getvalue())
        zip_buffer.seek(0)

        cache_key = f"{uf}_{municipio}_{tipo}"
        _clean_zip_cache()
        ZIP_CACHE[cache_key] = (datetime.utcnow(), zip_buffer.getvalue())

        # ---------- 5. gera CSV + JSON para o mapa ----------
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        map_id    = f"knn_{timestamp}"
        csv_file  = f"{map_id}.csv"
        cfg_file  = f"{map_id}.json"

        tmpdir   = tempfile.mkdtemp(prefix="vis_upload_")
        csv_path = os.path.join(tmpdir, csv_file)
        cfg_path = os.path.join(tmpdir, cfg_file)
        df_knn.to_csv(csv_path, index=False)

        try:
            centroide = demands_gdf.geometry.unary_union.centroid
            center_lat, center_lon = centroide.y, centroide.x
        except Exception:
            center_lat = df_knn["Origin_Lat"].mean()
            center_lon = df_knn["Origin_Lon"].mean()

        kepler_cfg = build_kepler_config(csv_file, center_lat, center_lon)
        kepler_cfg["label"] = f"Alocação – {municipio}/{uf}"
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(kepler_cfg, f, ensure_ascii=False, indent=2)

        # ---------- 6. upload ou modo legado ----------
        map_link = _upload_to_frontend(map_id, csv_path, cfg_path)

        if map_link:
            try:
                shutil.rmtree(tmpdir)
            except OSError as e:
                logger.warning(f"Não foi possível remover o diretório temporário {tmpdir}: {e}")
        else:
            logger.info(f"Modo legado: movendo arquivos para o diretório compartilhado: {SHARED_DIR}")
            shutil.move(csv_path, os.path.join(FRONT_DATA_DIR, csv_file))
            shutil.move(cfg_path, os.path.join(FRONT_CONFIG_DIR, cfg_file))
            try:
                os.rmdir(tmpdir)
            except OSError as e:
                logger.warning(f"Não foi possível remover o diretório temporário vazio {tmpdir}: {e}")
            map_link = f"/map/{map_id}"

        # ---------- 7. resposta ----------
        return {
            "alocacao":  convert_numpy_types(allocation_dict),
            "eda":       convert_numpy_types(city_summary),
            "info":      {"UF": uf, "Município": municipio, "Distância": tipo},
            "map_url":   map_link,
            "perguntas": perguntas_guiadas,
        }

    except HTTPException as e:
        # Re-lança exceções HTTP para que o FastAPI as manipule corretamente
        raise e
    except Exception as e:
        logger.exception("Erro inesperado em /consulta_base/resultado_completo")
        return JSONResponse(status_code=500, content={"erro": str(e)})


# ------------------------------------------------------------------ #
#  Download do ZIP                                                   #
# ------------------------------------------------------------------ #
@router.get("/download_zip")
def download_zip(uf: str, municipio: str, tipo: str = "geodesic"):
    cache_key = f"{uf}_{municipio}_{tipo}"
    cached = ZIP_CACHE.get(cache_key)
    if not cached:
        return JSONResponse(status_code=404, content={"erro": "ZIP não disponível. Execute a consulta primeiro."})

    _clean_zip_cache()
    _, zip_bytes = cached
    headers = {"Content-Disposition": f"attachment; filename=alocacao_{cache_key}.zip"}
    return StreamingResponse(BytesIO(zip_bytes), media_type="application/zip", headers=headers)
