"""
Ant Colony Optimization (ACO) solver for Constrained Vehicle Routing Problem (CVRP).

This module implements ACO to find optimal routes for delivering pallets and weight
from a distribution center to stores, respecting vehicle capacity constraints.
"""

import sqlite3
import numpy as np
import pandas as pd
from tqdm import trange
import csv
from typing import List, Tuple
import yaml

# Load config
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)


class ACOSolver:
    """
    ACO solver for CVRP.

    Attributes:
        dvrp_id: Unique identifier for the problem instance
        points_file: CSV file with point IDs to include
        db_path: Path to SQLite database
        origin: ID of the distribution center
        max_pall: Maximum pallets per vehicle
        max_lbs: Maximum weight per vehicle
        n_ants: Number of ants per iteration
        n_iterations: Number of ACO iterations
        alpha: Pheromone influence factor
        beta: Heuristic influence factor
        evaporation_rate: Pheromone evaporation rate
        Q: Pheromone deposit factor
    """

    def __init__(self, dvrp_id: str, points_file: str, db_path: str, origin: str,
                 max_pall: int, max_lbs: float, n_ants: int = 30, n_iterations: int = 150,
                 alpha: float = 1.0, beta: float = 1.0, evaporation_rate: float = 0.5, Q: float = 1.0):
        self.dvrp_id = dvrp_id
        self.points_file = points_file
        self.db_path = db_path
        self.origin = origin
        self.max_pall = max_pall
        self.max_lbs = max_lbs
        self.n_ants = n_ants
        self.n_iterations = n_iterations
        self.alpha = alpha
        self.beta = beta
        self.evaporation_rate = evaporation_rate
        self.Q = Q

    def _get_distance(self, point_a: str, point_b: str) -> float:
        """Get distance between two points from permutation matrix."""
        return self.perm_df.loc[point_a, point_b]

    def _save_solution(self) -> None:
        """Save the best solution to database."""
        if not self.best_path_id_p:
            return

        # Clean path (remove extra origin if present)
        if self.best_path_id_p[-1] == self.origin:
            self.best_path_id_p.pop()

        clusters = []
        cluster_id = 0
        sequence = 0
        for item in self.best_path_id_p:
            if item == self.origin:
                cluster_id += 1
                sequence = 1
            else:
                clusters.append([
                    self.dvrp_id, cluster_id, f'Tractor_{cluster_id}',
                    item, sequence
                ])
                sequence += 1

        # Filter out origin entries
        clusters = [c for c in clusters if c[3] != self.origin]

        self.cur.executemany(
            'INSERT INTO dvrp_set (dvrp_id, cluster_id, cluster_name, point, sequence) VALUES (?, ?, ?, ?, ?)',
            clusters
        )
        self.cur.execute(
            'INSERT INTO dvrp_origin (dvrp_id, dvrp_origin) VALUES (?, ?)',
            [self.dvrp_id, self.origin]
        )
        self.con.commit()

    def solve(self) -> str:
        """
        Run ACO algorithm to solve CVRP.

        Returns:
            Status message
        """
        # Load points from CSV
        with open(self.points_file, 'r') as f:
            reader = csv.reader(f)
            points = [row[0] for row in reader]

        self.con = sqlite3.connect(self.db_path)
        self.cur = self.con.cursor()

        # Check if solution already exists
        exists = pd.read_sql_query(
            'SELECT EXISTS(SELECT 1 FROM dvrp_origin WHERE dvrp_id = ?) AS exists_flag',
            self.con, params=[self.dvrp_id]
        ).iloc[0, 0]
        if exists:
            print(f'DVRP ID {self.dvrp_id} already exists.')
            self.con.close()
            return 'Solution already exists'

        # Load point data
        temp_table = 'temp_points'
        self.cur.execute(f'CREATE TEMPORARY TABLE {temp_table} (id_p TEXT)')
        self.cur.execute(f'DELETE FROM {temp_table}')
        self.cur.executemany(f'INSERT INTO {temp_table} VALUES (?)', [(p,) for p in points])
        self.con.commit()

        points_df = pd.read_sql_query(f'''
            SELECT gp.id_p, gp.pall_avg, gp.lbs_avg
            FROM geo_points gp
            INNER JOIN {temp_table} tp ON gp.id_p = tp.id_p
        ''', self.con)

        # Load distance matrix
        perm_df = pd.read_sql_query('SELECT id_1, id_2, distance FROM geo_permutations', self.con)
        self.perm_df = perm_df.pivot(index='id_1', columns='id_2', values='distance')

        n_points = len(points_df)
        pheromone = np.ones((n_points, n_points))
        best_path = None
        best_length = np.inf
        origin_idx = points_df[points_df['id_p'] == self.origin].index[0]

        for iteration in trange(self.n_iterations, desc='ACO Iterations'):
            paths = []
            lengths = []

            for ant in range(self.n_ants):
                visited = [False] * n_points

                # Start from random point (not origin)
                while True:
                    start_idx = np.random.randint(n_points)
                    if start_idx != origin_idx:
                        break

                visited[start_idx] = True
                path = [origin_idx, start_idx]
                length = self._get_distance(points_df.iloc[origin_idx, 0], points_df.iloc[start_idx, 0])
                load = points_df.iloc[start_idx, 1]
                weight = points_df.iloc[start_idx, 2]

                while sum(visited) < n_points - 1:  # All except origin must be visited
                    unvisited = np.where(~np.array(visited))[0]
                    probs = np.zeros(len(unvisited))

                    for i, next_idx in enumerate(unvisited):
                        p1 = points_df.iloc[path[-1], 0]
                        p2 = points_df.iloc[next_idx, 0]
                        dist = self._get_distance(p1, p2) ** self.beta
                        if dist > 0:  # Avoid division by zero
                            probs[i] = (pheromone[path[-1], next_idx] ** self.alpha) / dist

                    if probs.sum() > 0:
                        probs /= probs.sum()
                        next_idx = np.random.choice(unvisited, p=probs)
                    else:
                        next_idx = np.random.choice(unvisited)

                    if next_idx == origin_idx:
                        continue

                    next_load = points_df.iloc[next_idx, 1]
                    next_weight = points_df.iloc[next_idx, 2]

                    # Check capacity
                    if load + next_load > self.max_pall or weight + next_weight > self.max_lbs:
                        # Return to origin
                        path.append(origin_idx)
                        length += self._get_distance(points_df.iloc[path[-2], 0], self.origin)
                        visited[origin_idx] = True
                        path[-1] = origin_idx  # Current becomes origin
                        load = 0
                        weight = 0
                    else:
                        path.append(next_idx)
                        load += next_load
                        weight += next_weight
                        length += self._get_distance(points_df.iloc[path[-2], 0], points_df.iloc[next_idx, 0])
                        visited[next_idx] = True

                # Close path
                path.append(origin_idx)
                length += self._get_distance(points_df.iloc[path[-2], 0], self.origin)
                paths.append(path)
                lengths.append(length)

                if length < best_length:
                    best_path = path
                    best_length = length

            # Update pheromones
            pheromone *= self.evaporation_rate
            for path, length in zip(paths, lengths):
                deposit = self.Q / length
                for i in range(len(path) - 1):
                    pheromone[path[i], path[i+1]] += deposit
                pheromone[path[-1], path[0]] += deposit

        print(f'Best path indices: {best_path}')
        self.best_path_id_p = [points_df.iloc[i, 0] for i in best_path]
        print(f'Best path points: {self.best_path_id_p}')
        print(f'Best length: {best_length}')

        # Print tractor load summaries
        print('\\nTractor Load Summary:')
        tractor_loads = {}
        current_tractor = 0

        for item in self.best_path_id_p:
            if item == self.origin:
                current_tractor += 1
                tractor_loads[current_tractor] = {'pallets': 0, 'lbs': 0}
            elif current_tractor > 0:
                point_data = points_df[points_df['id_p'] == item]
                if not point_data.empty:
                    pall = point_data.iloc[0]['pall_avg']
                    lbs = point_data.iloc[0]['lbs_avg']
                    tractor_loads[current_tractor]['pallets'] += pall
                    tractor_loads[current_tractor]['lbs'] += lbs

        for tractor_id, loads in tractor_loads.items():
            print(f'Tractor {tractor_id} = {loads["pallets"]} pallets and {loads["lbs"]} lbs')

        self._save_solution()
        self.con.close()
        return 'CVRP solved and saved'


# Example usage
if __name__ == "__main__":
    solver = ACOSolver(
        dvrp_id='demo',
        points_file=config['samples']['points_csv'],
        db_path=config['data']['db_path'],
        origin=config['data']['origin'],
        max_pall=config['vehicle']['max_pall'],
        max_lbs=config['vehicle']['max_lbs']
    )
    result = solver.solve()
    print(result)
