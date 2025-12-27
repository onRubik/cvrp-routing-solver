"""
Visualization functions for CVRP solutions using Plotly.

Provides functions to generate tables and maps for DVRP results.
"""

import pandas as pd
import plotly.graph_objects as go
import json
import sqlite3
import openrouteservice
from typing import Dict, List
import yaml

# Load config
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)


def plot_solution_table(dvrp_id: str = None, db_path: str = None) -> go.Figure:
    """
    Generate a Plotly table of DVRP solution data with tractor load summaries.

    Args:
        dvrp_id: Specific DVRP ID to plot, or None for all
        db_path: Path to database

    Returns:
        Plotly figure with table
    """
    if db_path is None:
        db_path = config['data']['db_path']

    con = sqlite3.connect(db_path)

    if dvrp_id:
        query = 'SELECT * FROM dvrp_set WHERE dvrp_id = ? ORDER BY cluster_id, sequence'
        params = [dvrp_id]
    else:
        query = 'SELECT * FROM dvrp_set ORDER BY dvrp_id, cluster_id, sequence'
        params = []

    df = pd.read_sql_query(query, con, params=params)

    # Calculate tractor load summaries
    if not df.empty:
        # Join with geo_points to get pallet and weight data
        summary_query = f'''
            SELECT
                ds.dvrp_id,
                ds.cluster_id,
                ds.cluster_name,
                COUNT(ds.point) as stops,
                SUM(gp.pall_avg) as total_pallets,
                SUM(gp.lbs_avg) as total_weight_lbs
            FROM dvrp_set ds
            JOIN geo_points gp ON ds.point = gp.id_p
            {'WHERE ds.dvrp_id = ?' if dvrp_id else ''}
            GROUP BY ds.dvrp_id, ds.cluster_id, ds.cluster_name
            ORDER BY ds.cluster_id
        '''
        summary_params = [dvrp_id] if dvrp_id else []
        summary_df = pd.read_sql_query(summary_query, con, params=summary_params)

        # Add summary columns to main dataframe
        df = df.merge(summary_df, on=['dvrp_id', 'cluster_id', 'cluster_name'], how='left')

    con.close()

    fig = go.Figure(data=[go.Table(
        header=dict(
            values=list(df.columns),
            fill_color='paleturquoise',
            align='left'
        ),
        cells=dict(
            values=[df[col].tolist() for col in df.columns],
            fill_color='lavender',
            align='left'
        )
    )])

    title = f"DVRP Solution{' - ' + dvrp_id if dvrp_id else ''}"
    if not df.empty and 'total_pallets' in df.columns:
        title += " (with Tractor Load Summary)"

    fig.update_layout(
        title=title,
        margin=dict(l=10, r=18, t=50, b=10)
    )

    return fig


def plot_routes_map(dvrp_id: str, api_key: str, db_path: str = None) -> go.Figure:
    """
    Generate an interactive map of DVRP routes using Plotly and ORS.

    Args:
        dvrp_id: DVRP solution ID
        api_key: Open Route Service API key
        db_path: Path to database

    Returns:
        Plotly figure with map
    """
    if db_path is None:
        db_path = config['data']['db_path']

    con = sqlite3.connect(db_path)
    client = openrouteservice.Client(key=api_key)

    # Get origin
    origin_query = pd.read_sql_query(
        'SELECT dvrp_origin FROM dvrp_origin WHERE dvrp_id = ?',
        con, params=[dvrp_id]
    )
    if origin_query.empty:
        con.close()
        raise ValueError(f"No origin found for DVRP ID {dvrp_id}")

    origin_id = origin_query.iloc[0, 0]

    # Get origin coordinates
    origin_coords = pd.read_sql_query(
        'SELECT lat, lon FROM geo_points WHERE id_p = ?',
        con, params=[origin_id]
    )
    if origin_coords.empty:
        con.close()
        raise ValueError(f"No coordinates found for origin {origin_id}")

    origin_lat, origin_lon = origin_coords.iloc[0]
    origin_coords_list = [origin_lon, origin_lat]  # [lon, lat]

    # Get clusters
    clusters_query = pd.read_sql_query('''
        SELECT ds.cluster_id, ds.sequence, gp.lat, gp.lon, ds.point
        FROM dvrp_set ds
        JOIN geo_points gp ON ds.point = gp.id_p
        WHERE ds.dvrp_id = ?
        ORDER BY ds.cluster_id, ds.sequence
    ''', con, params=[dvrp_id])

    con.close()

    if clusters_query.empty:
        raise ValueError(f"No solution data found for DVRP ID {dvrp_id}")

    # Group by cluster
    clusters = {}
    for _, row in clusters_query.iterrows():
        cluster_id = int(row['cluster_id'])
        if cluster_id not in clusters:
            clusters[cluster_id] = []
        clusters[cluster_id].append({
            'coords': [row['lon'], row['lat']],  # [lon, lat]
            'sequence': int(row['sequence']),
            'desc': row['point']
        })

    # Create map
    fig = go.Figure()

    fig.add_trace(go.Scattermapbox(
        mode='markers',
        lon=[origin_lon],
        lat=[origin_lat],
        marker={'size': 20, 'color': 'red'},
        name='Origin (Distribution Center)',
        text=[f'Origin: {origin_id}'],
        hoverinfo='text'
    ))

    for cluster_id, points in clusters.items():
        # Route coordinates: origin -> points -> origin
        route_coords = [origin_coords_list] + [p['coords'] for p in points] + [origin_coords_list]

        try:
            # Get route from ORS
            route = client.directions(
                coordinates=route_coords,
                profile='driving-hgv',
                format='geojson'
            )
            line_coords = route['features'][0]['geometry']['coordinates']

            # Add route line
            route_color = 'rgba({}, {}, {}, 0.8)'.format(
                (cluster_id * 50) % 255,
                (cluster_id * 80) % 255,
                (cluster_id * 110) % 255
            )
            fig.add_trace(go.Scattermapbox(
                lon=[c[0] for c in line_coords],
                lat=[c[1] for c in line_coords],
                mode='lines',
                line={'width': 4, 'color': route_color},
                name=f'Vehicle {cluster_id} Route',
                hoverinfo='none'
            ))

            # Add points
            for point in points:
                fig.add_trace(go.Scattermapbox(
                    lon=[point['coords'][0]],
                    lat=[point['coords'][1]],
                    mode='markers',
                    marker={'size': 16, 'color': 'gray'},
                    text=["Stop {}: {}".format(point['sequence'], point['desc'])],
                    hoverinfo='text',
                    name='Vehicle {} - Stop {}'.format(cluster_id, point['sequence']),
                    showlegend=False
                ))

        except Exception as e:
            print(f"Error getting route for cluster {cluster_id}: {e}")
            # Fallback: straight lines
            fig.add_trace(go.Scattermapbox(
                lon=[c[0] for c in route_coords],
                lat=[c[1] for c in route_coords],
                mode='lines',
                line={'width': 2, 'dash': 'dash'},
                name=f'Vehicle {cluster_id} (straight line)',
            ))

    fig.update_layout(
        title=f"CVRP Routes for {dvrp_id}",
        mapbox={
            'style': "open-street-map",
            'zoom': 10,
            'center': {'lat': origin_lat, 'lon': origin_lon},
        },
        margin={'l': 0, 'r': 0, 't': 50, 'b': 0},
        showlegend=True
    )

    return fig


def get_available_solutions(db_path: str = None) -> List[str]:
    """
    Get list of available DVRP solution IDs.

    Args:
        db_path: Path to database

    Returns:
        List of DVRP IDs
    """
    if db_path is None:
        db_path = config['data']['db_path']

    con = sqlite3.connect(db_path)
    solutions = pd.read_sql_query('SELECT DISTINCT dvrp_id FROM dvrp_origin', con)
    con.close()

    return solutions['dvrp_id'].tolist()


# Example usage
if __name__ == "__main__":
    # Plot table for all solutions
    fig_table = plot_solution_table()
    fig_table.show()

    # Plot map for a specific solution (requires API key)
    solutions = get_available_solutions()
    if solutions:
        api_key = input("Enter ORS API key: ")
        fig_map = plot_routes_map(solutions[0], api_key)
        fig_map.show()
