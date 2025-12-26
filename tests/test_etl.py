"""
Basic tests for ETL functions.
"""

import pytest
import os
import tempfile
import yaml
from src.data_prep.etl import init_db, close_db, geojson_to_csv_and_json

# Load config
with open('config.yaml') as f:
    config = yaml.safe_load(f)


def test_init_db():
    """Test database initialization."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        db_path = tmp.name

    try:
        con = init_db(db_path)
        assert con is not None
        close_db(con)
    finally:
        os.unlink(db_path)


def test_geojson_to_csv_and_json():
    """Test geojson conversion (mock data)."""
    # Create mock geojson
    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-74.0060, 40.7128]},
                "properties": {"name": "Test Store"},
                "id": "test_1"
            }
        ]
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as tmp:
        import json
        json.dump(geojson_data, tmp)
        geojson_path = tmp.name

    try:
        geojson_to_csv_and_json(geojson_path)

        # Check outputs exist
        csv_path = geojson_path + '.csv'
        json_path = geojson_path + '.json'

        assert os.path.exists(csv_path)
        assert os.path.exists(json_path)

        # Clean up
        os.unlink(csv_path)
        os.unlink(json_path)

    finally:
        os.unlink(geojson_path)


if __name__ == "__main__":
    pytest.main([__file__])
