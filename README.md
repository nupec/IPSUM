# IPSUM

Welcome to the **IPSUM** repository! This project provides a FastAPI-based application designed to allocate demands to different establishments based on geographic data using geodesic distance calculations and network analysis.

## Features

- **Geodesic Distance Calculation**: Efficiently calculates the geodesic distance between demand points and establishments.
- **Centroid Calculation**: Automatically calculates centroids for polygon geometries, ensuring accurate distance measurements when dealing with polygons or multipolygons.
- **K-Nearest Neighbors (KNN) Allocation**: Supports demand allocation using KNN, with configurable k for either demands or establishments.
- **Network Distance Calculation**: Utilizes road networks to compute a more realistic distance matrix between demands and establishments.
- **Flexible Configuration**: Easily configure which columns to use for demands and establishments through the `config.py` file.
- **Modular Structure**: Organized into modules for easy maintenance, extensibility, and scalability.
- **Containerization**: Now you can run the application inside a Docker container, ensuring a reproducible and isolated environment.

## Installation

### Prerequisites

- Python 3.10 (as specified in the environment file)
- Conda (environment manager)
- Git (to clone the repository)
- Docker (for containerization)

### Clone the Repository

```bash
git clone https://github.com/nupec/IPSUM.git
cd IPSUM
```
## Create a Conda Virtual Environment

It is recommended to use a conda environment to manage dependencies:
```bash
conda env create -f environment.yml
```
Activate the Conda Environment

### On Linux/macOS and Windows:
```bash
conda activate ipsum
```
Environment Setup

The environment.yml file includes:

name: ipsum
channels:
  - conda-forge
dependencies:
  - python 3.10
  - geopandas
  - geopy
  - pandas
  - fastapi
  - unidecode
  - uvicorn
  - libpysal
  - python-multipart
  - osmnx
  - pandana
  - numpy
  - matplotlib

Run the Application
Start the FastAPI Server

## Run the server with:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The application will be available at http://0.0.0.0:8000/docs.
Deactivate the Conda Environment

When you're done working, deactivate the environment:
```bash
conda deactivate
```
## Docker Container Setup

You can now run the application inside a Docker container to ensure a reproducible and isolated environment.

### 1. Build the Docker Image

Execute the following command in the root of the project:
```bash
docker build -t ipsum .
```
### 2. Run the Container

Start a container mapping port 8000:
```bash
docker run -d -p 8000:8000 ipsum
```
### 3. Test the API in Docker

Access the API at http://localhost:8000.

## Test Data

### To facilitate testing and validation of the IPSUM system, we provide sample GeoJSON files in a structured format. These files represent synthetic demand points and establishment locations in different configurations.
Sample Files Structure

```bash
test/
    ├── 10x10_rj_demands.geojson
    ├── 10x10_rj_opportunities.geojson
    ├── 5x5_am_demands.geojson
    └── 5x5_am_opportunities.geojson

