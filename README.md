# IPSUM - Demand Allocation Backend

**IPSUM** is a specialized backend service designed to solve facility location and demand allocation problems using geospatial data. It provides a high-performance API built with FastAPI, capable of processing large datasets using various distance metrics and algorithms.

## 🚀 Key Features

* **Versatile Allocation Algorithms:**
    * **Geodesic Distance:** "As-the-crow-flies" calculations using `geopy`.
    * **Network Distance:** Real-world street network analysis using `pandana` and `osmnx`.
    * **High-Performance Indexing:** KD-Tree implementation via `libpysal` for rapid nearest-neighbor queries.
* **Automated Geoprocessing:**
    * Automatic centroid calculation for Polygon/MultiPolygon geometries.
    * Coordinate Reference System (CRS) handling and reprojection.
* **Socioeconomic Reporting:** Generates PDF reports and statistical summaries (coverage, racial distribution, population demographics).
* **Dockerized Environment:** Fully isolated runtime using Miniconda to handle complex geospatial dependencies (GDAL, PROJ).

## 📂 Project Structure

The codebase is organized for modularity and scalability:

* `app/main.py`: Application entry point and middleware configuration.
* `app/routes/`: API endpoints (e.g., KNN allocation, EDA).
* `app/methods/`: Core algorithms (Geodesic, Pandana, PySAL).
* `app/analysis/`: Business logic for reporting and chart generation.
* `app/preprocessing/`: Data cleaning, spatial joins, and network graph downloads.
* `data/`: Directory for storage of GeoJSON inputs and cache.

## 🛠️ Installation & Deployment

### Option 1: Docker (Recommended)

This project utilizes **Miniconda** within Docker to manage system-level geospatial libraries.

1.  **Build the Image:**
    ```bash
    docker build -t ipsum-backend .
    ```

2.  **Run the Container:**
    ```bash
    # Runs on port 8050
    docker run -d -p 8050:8050 --name ipsum-backend ipsum-backend
    ```

3.  **Access Documentation:**
    Open [http://localhost:8050/docs](http://localhost:8050/docs) to view the Swagger UI.

### Option 2: Local Development (Conda)

1.  **Create Environment:**
    ```bash
    conda env create -f environment.yml
    ```

2.  **Activate Environment:**
    ```bash
    conda activate ipsum
    ```

3.  **Run Server:**
    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8050 --reload
    ```

## 📊 Input Data Formats

The API expects specific column naming conventions for automatic detection, though it is robust enough to infer common variations (e.g., `lat`, `latitude`, `y`).

* **Demands:** GeoJSON or CSV containing population data and location.
* **Opportunities (Facilities):** GeoJSON or CSV containing facility locations (UBS, Hospitals, Schools).

*Check `app/config.py` for the full list of supported column aliases.*

## 🤝 Contributing

Contributions are welcome! We follow a strict standardization policy to ensure code quality.

* **Language:** English only (Code, Logs, Docs).
* **Workflow:** Gitflow (`main`, `develop`, `feature/...`).
* **Commits:** Conventional Commits.

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a Pull Request.

## 📄 License

This project is licensed under the [MIT License](LICENSE).