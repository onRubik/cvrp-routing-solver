"""
ETL (Extract, Transform, Load) module for CVRP-ACO data preparation.

This module handles:
- Processing geojson data from overpass-turbo
- Generating permutations and distances
- Updating SQLite database with points and permutations
- Fetching distances via Open Route Service API
"""

import sqlite3
import json
import csv
import pandas as pd
from itertools import permutations
import time
import random
from os import environ
import urllib3
import yaml

# Load config
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)


def init_db(db_path: str) -> sqlite3.Connection:
    """Initialize SQLite database connection."""
    return sqlite3.connect(db_path)


def close_db(con: sqlite3.Connection) -> None:
    """Close database connection."""
    con.close()


def resize_geo_points(reduced_size: int, file_name: str) -> None:
    """
    Reduce the number of points in a geojson file by random selection.

    Args:
        reduced_size: Number of points to keep
        file_name: Path to input geojson file
    """
    with open(file_name, 'r', encoding='utf-8') as geojson_file:
        data = json.load(geojson_file)

    selected_points = [
        feature for feature in data.get('features', [])
        if feature.get('geometry', {}).get('type') == 'Point'
    ]

    random.shuffle(selected_points)
    selected_points = selected_points[:reduced_size]

    result_geojson = {
        "type": "FeatureCollection",
        "features": selected_points
    }

    with open(file_name + '_reduced.geojson', 'w', encoding='utf-8') as result_file:
        json.dump(result_geojson, result_file, indent=2)


def geojson_to_csv_and_json(file_name: str) -> None:
    """
    Convert geojson points to CSV and JSON formats.

    Args:
        file_name: Path to geojson file
    """
    with open(file_name, 'r') as geojson_file:
        geojson_data = json.load(geojson_file)

    point_features = [
        feature for feature in geojson_data['features']
        if feature['geometry']['type'] == 'Point'
    ]

    points_csv = []
    points_json = {}

    for point in point_features:
        id_p = point['id']
        name = point['properties'].get('name', '')
        lat = point['geometry']['coordinates'][1]
        lon = point['geometry']['coordinates'][0]

        points_csv.append({
            'id_p': id_p,
            'name': name,
            'lat': lat,
            'lon': lon
        })

        points_json[id_p] = {
            'name': name,
            'lat': lat,
            'lon': lon
        }

    with open(file_name + '.csv', 'w', newline='') as csvfile:
        fieldnames = ['id_p', 'name', 'lat', 'lon']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(points_csv)

    with open(file_name + '.json', 'w') as jsonfile:
        json.dump(points_json, jsonfile, indent=4)


def geo_points_update(file_name: str, db_path: str) -> None:
    """
    Update geo_points table in database from CSV.

    Args:
        file_name: Path to CSV file
        db_path: Database path
    """
    con = init_db(db_path)
    cur = con.cursor()
    points = pd.read_csv(file_name)

    # Clear staging table if exists
    cur.execute('CREATE TABLE IF NOT EXISTS stage_geo_points (id_p TEXT PRIMARY KEY, name TEXT, lat NUMERIC, lon NUMERIC)')
    cur.execute('DELETE FROM stage_geo_points')
    con.commit()

    points = points.set_index('id_p')
    points.to_sql('stage_geo_points', con, if_exists='append', index_label='id_p')
    con.commit()

    # Insert new points
    cur.execute('''
        INSERT OR IGNORE INTO geo_points(id_p, name, lat, lon)
        SELECT id_p, name, lat, lon FROM stage_geo_points
    ''')
    con.commit()
    close_db(con)


def assign_delivery_freq(db_path: str) -> None:
    """
    Assign random delivery frequencies to points without them.

    Args:
        db_path: Database path
    """
    con = init_db(db_path)
    cur = con.cursor()

    cur.execute('SELECT id_p FROM geo_points WHERE delivery_freq_per_week IS NULL')
    rows = cur.fetchall()

    for row in rows:
        # 20% chance for high freq (5 or 7), else low (1 or 3)
        if random.random() <= 0.2:
            freq = random.choice([5, 7])
        else:
            freq = random.choice([1, 3])
        cur.execute(
            'UPDATE geo_points SET delivery_freq_per_week = ? WHERE id_p = ?',
            (freq, row[0])
        )

    con.commit()
    close_db(con)


def assign_pallets_weights(db_path: str) -> None:
    """
    Assign random pallet counts and weights based on delivery frequency.

    Args:
        db_path: Database path
    """
    con = init_db(db_path)
    cur = con.cursor()

    cur.execute('''
        SELECT id_p, delivery_freq_per_week FROM geo_points
        WHERE pall_avg IS NULL AND lbs_avg IS NULL
    ''')
    rows = cur.fetchall()

    for row in rows:
        id_p, freq = row
        if freq > 3:
            pall_avg = random.randint(9, 15)
        else:
            pall_avg = random.randint(1, 8)
        lbs_avg = round(pall_avg * random.uniform(1200, 1700), 6)
        cur.execute(
            'UPDATE geo_points SET pall_avg = ?, lbs_avg = ? WHERE id_p = ?',
            (pall_avg, lbs_avg, id_p)
        )

    con.commit()
    close_db(con)


def generate_permutations(file_name: str) -> None:
    """
    Generate all permutations of points from geojson and save to CSV/JSON.

    Args:
        file_name: Path to geojson file
    """
    with open(file_name, 'r') as geojson_file:
        geojson_data = json.load(geojson_file)

    point_features = [
        feature for feature in geojson_data['features']
        if feature['geometry']['type'] == 'Point'
    ]

    perm_csv = []
    perm_json = {}

    for pair in permutations(point_features, 2):
        feature_0, feature_1 = pair
        id_1 = feature_0['id']
        id_2 = feature_1['id']
        name_1 = feature_0['properties'].get('name', '')
        name_2 = feature_1['properties'].get('name', '')
        lat_1 = feature_0['geometry']['coordinates'][1]
        lon_1 = feature_0['geometry']['coordinates'][0]
        lat_2 = feature_1['geometry']['coordinates'][1]
        lon_2 = feature_1['geometry']['coordinates'][0]

        perm = id_1 + id_2
        perm_csv.append({
            'perm': perm,
            'id_1': id_1,
            'id_2': id_2,
            'name_1': name_1,
            'name_2': name_2,
            'lat_id_1': lat_1,
            'lon_id_1': lon_1,
            'lat_id_2': lat_2,
            'lon_id_2': lon_2
        })

        perm_json[perm] = {
            'id_1': id_1,
            'id_2': id_2,
            'name_1': name_1,
            'name_2': name_2,
            'lat_id_1': lat_1,
            'lon_id_1': lon_1,
            'lat_id_2': lat_2,
            'lon_id_2': lon_2
        }

    with open(file_name + '_permutations.csv', 'w', newline='') as csvfile:
        fieldnames = ['perm', 'id_1', 'id_2', 'name_1', 'name_2', 'lat_id_1', 'lon_id_1', 'lat_id_2', 'lon_id_2']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(perm_csv)

    with open(file_name + '_permutations.json', 'w') as jsonfile:
        json.dump(perm_json, jsonfile, indent=4)


def geo_permutations_update(file_name: str, db_path: str) -> None:
    """
    Update geo_permutations table from CSV.

    Args:
        file_name: Path to permutations CSV
        db_path: Database path
    """
    con = init_db(db_path)
    cur = con.cursor()
    points = pd.read_csv(file_name)

    # Clear staging table
    cur.execute('CREATE TABLE IF NOT EXISTS stage_geo_permutations (perm TEXT PRIMARY KEY, id_1 TEXT, id_2 TEXT, name_1 TEXT, name_2 TEXT, lat_id_1 NUMERIC, lon_id_1 NUMERIC, lat_id_2 NUMERIC, lon_id_2 NUMERIC)')
    cur.execute('DELETE FROM stage_geo_permutations')
    con.commit()

    points = points.set_index('perm')
    points.to_sql('stage_geo_permutations', con, if_exists='append', index_label='perm')
    con.commit()

    # Insert new permutations
    cur.execute('''
        INSERT OR IGNORE INTO geo_permutations(perm, id_1, id_2, name_1, name_2, lat_id_1, lon_id_1, lat_id_2, lon_id_2)
        SELECT perm, id_1, id_2, name_1, name_2, lat_id_1, lon_id_1, lat_id_2, lon_id_2 FROM stage_geo_permutations
    ''')
    con.commit()
    close_db(con)


def fetch_ors_distances(api_key: str, db_path: str) -> None:
    """
    Fetch distances for permutations using ORS API.

    Args:
        api_key: Open Route Service API key
        db_path: Database path
    """
    con = init_db(db_path)
    cur = con.cursor()
    http = urllib3.PoolManager()
    endpoint = 'https://api.openrouteservice.org/v2/directions/driving-hgv'

    cur.execute('SELECT COUNT(*) FROM geo_permutations WHERE distance IS NULL')
    missing = cur.fetchone()[0]
    print(f'Rows missing distance: {missing}')

    if missing > 0:
        cur.execute('SELECT perm, lat_id_1, lon_id_1, lat_id_2, lon_id_2 FROM geo_permutations WHERE distance IS NULL')
        rows = cur.fetchall()

        delay = 1.5  # Rate limit delay
        for row in rows:
            perm, lat1, lon1, lat2, lon2 = row
            coords1 = f'{lon1},{lat1}'
            coords2 = f'{lon2},{lat2}'
            distance = ors_fetch_distance(api_key, http, endpoint, coords1, coords2)
            if distance is not None:
                cur.execute('UPDATE geo_permutations SET distance = ? WHERE perm = ?', (distance, perm))
            time.sleep(delay)

        con.commit()
    close_db(con)


def ors_fetch_distance(api_key: str, http: urllib3.PoolManager, endpoint: str, coords1: str, coords2: str) -> float:
    """
    Fetch distance between two coordinates using ORS.

    Args:
        api_key: API key
        http: HTTP pool manager
        endpoint: API endpoint
        coords1: Start coordinates (lon,lat)
        coords2: End coordinates (lon,lat)

    Returns:
        Distance in meters or None if error
    """
    url = f'{endpoint}?api_key={api_key}&start={coords1}&end={coords2}'
    r = http.request('GET', url, headers={'Content-Type': 'application/json'})
    if r.status == 200:
        data = json.loads(r.data)
        return data['features'][0]['properties']['segments'][0]['distance']
    else:
        print(f'ORS API error: {r.status}')
        return None


# Example usage
if __name__ == "__main__":
    # Example: Process sample data
    geojson_to_csv_and_json(config['samples']['geojson'])
    geo_points_update(config['samples']['points_csv'], config['data']['db_path'])
    assign_delivery_freq(config['data']['db_path'])
    assign_pallets_weights(config['data']['db_path'])
