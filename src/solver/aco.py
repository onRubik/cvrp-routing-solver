import sys
import sqlite3
import numpy as np
import pandas as pd
from tqdm import tqdm
import csv
import os


class ACOSolver:
    def __init__(self, dvrp_id, points_file, db_path, origin, max_pall, max_lbs, n_ants=30, n_iterations=50, alpha=1, beta=1, evaporation_rate=0.5, Q=1):
        self.dvrp_id = dvrp_id
        self.points_file = points_file
        self.db_path = db_path
        self.origin = origin
        self.max_pall = int(max_pall)
        self.max_lbs = int(max_lbs)
        self.n_ants = int(n_ants)
        self.n_iterations = int(n_iterations)
        self.alpha = float(alpha)
        self.beta = float(beta)
        self.evaporation_rate = float(evaporation_rate)
        self.Q = float(Q)

    def distance(self, point_a, point_b):
        """Get distance between two points from pre-computed matrix"""
        distance = self.perm_df.loc[point_a, point_b]
        return distance

    def load_best_path_id_p(self):
        """Save the best solution to database"""
        if self.best_path_id_p and self.best_path_id_p[-1] == self.origin:
            self.best_path_id_p.pop()

        cluster_l = []
        cluster_counter = 0
        sequence_n = 0
        for item in self.best_path_id_p:
            if item == self.origin:
                cluster_counter += 1
                sequence_n = 1
            else:
                cluster_l.append([
                    self.dvrp_id,
                    cluster_counter,
                    f'Tractor_{cluster_counter}',
                    item,
                    sequence_n
                ])
                sequence_n += 1

        cluster_l = [x for x in cluster_l if x[3] != self.origin]

        self.cur.executemany(
            'INSERT INTO dvrp_set (dvrp_id, cluster_id, cluster_name, point, sequence) VALUES (?, ?, ?, ?, ?)',
            cluster_l
        )
        self.cur.execute('INSERT INTO dvrp_origin (dvrp_id, dvrp_origin) VALUES (?, ?)', [self.dvrp_id, self.origin])
        self.con.commit()

    def solve(self):
        """Run the ACO algorithm to solve CVRP"""
        # Load points to solve
        with open(self.points_file, 'r') as r:
            reader = csv.reader(r)
            in_points = [row[0] for row in reader]

        self.con = sqlite3.connect(self.db_path)
        self.cur = self.con.cursor()

        # Check if solution already exists
        dvrp_id_query = '''
            SELECT EXISTS (
                SELECT 1
                FROM dvrp_origin
                WHERE dvrp_id = ?
            ) as dvrp_id_exists
        '''

        res_exists = pd.read_sql_query(dvrp_id_query, self.con, params=[self.dvrp_id])
        if res_exists.iloc[0, 0] == 1:
            print(f'Solution with dvrp_id "{self.dvrp_id}" already exists in the database.')
            self.con.close()
            return f'Solution {self.dvrp_id} already exists'

        # Load points data
        self.cur.execute('CREATE TEMPORARY TABLE IF NOT EXISTS temp_items (item TEXT)')
        self.cur.execute('DELETE FROM temp_items')
        self.cur.executemany('INSERT INTO temp_items (item) VALUES (?)', [(item,) for item in in_points])

        points_query = '''
            SELECT gp.id_p, gp.pall_avg, gp.lbs_avg
            FROM geo_points gp, temp_items tp
            WHERE gp.id_p = tp.item
        '''

        self.points_df = pd.read_sql_query(points_query, self.con)

        # Load permutations data
        perm_query = '''
            SELECT id_1, id_2, distance
            FROM geo_permutations
        '''

        perm_df = pd.read_sql_query(perm_query, self.con)
        self.perm_df = perm_df.pivot(index='id_1', columns='id_2', values='distance')

        n_points = len(self.points_df)
        pheromone = np.ones((n_points, n_points))
        best_path = None
        best_path_length = np.inf
        self.origin_index = self.points_df[self.points_df['id_p'] == self.origin].index[0]

        print(f"🐜 Starting ACO with {n_points} points, {self.n_ants} ants, {self.n_iterations} iterations")

        for iteration in tqdm(range(self.n_iterations), desc="ACO Iterations"):
            paths = []
            path_lengths = []

            for ant in range(self.n_ants):
                visited = [False] * n_points

                # Start from a random point (not origin)
                while True:
                    current_point = np.random.randint(n_points)
                    if self.points_df.iloc[current_point, 0] != self.origin:
                        break

                visited[current_point] = True
                path = [self.origin_index, current_point]
                point_a = self.points_df.iloc[self.origin_index, 0]
                point_b = self.points_df.iloc[current_point, 0]
                path_length = self.distance(point_a, point_b)
                current_load = self.points_df.iloc[current_point, 1]
                current_weight = self.points_df.iloc[current_point, 2]

                while False in visited:
                    unvisited = np.where(np.logical_not(visited))[0]
                    probabilities = np.zeros(len(unvisited))

                    for i, unvisited_point in enumerate(unvisited):
                        point_a = self.points_df.iloc[current_point, 0]
                        point_b = self.points_df.iloc[unvisited_point, 0]
                        dist = self.distance(point_a, point_b)**self.beta
                        pheromone_value = pheromone[current_point, unvisited_point]**self.alpha
                        probabilities[i] = pheromone_value / dist

                    p_sum = np.sum(probabilities)
                    if p_sum > 0:
                        probabilities /= p_sum
                    else:
                        probabilities = np.ones(len(probabilities)) / len(probabilities)

                    next_point = np.random.choice(unvisited, p=probabilities)
                    if self.points_df.iloc[next_point, 0] == self.origin:
                        continue

                    next_load = self.points_df.iloc[next_point, 1]
                    next_weight = self.points_df.iloc[next_point, 2]

                    # Check capacity constraints
                    if current_load + next_load > self.max_pall or current_weight + next_weight > self.max_lbs:
                        # Return to origin and start new route
                        path.append(self.origin_index)
                        point_a = self.points_df.iloc[current_point, 0]
                        point_b = self.points_df.iloc[self.origin_index, 0]
                        path_length += self.distance(point_a, point_b)
                        visited[self.origin_index] = True
                        current_point = self.origin_index
                        current_load = 0
                        current_weight = 0
                    else:
                        # Add point to current route
                        path.append(next_point)
                        current_load += next_load
                        current_weight += next_weight
                        point_a = self.points_df.iloc[current_point, 0]
                        point_b = self.points_df.iloc[next_point, 0]
                        path_length += self.distance(point_a, point_b)
                        visited[next_point] = True
                        current_point = next_point

                # Return to origin
                path.append(self.origin_index)
                paths.append(path)
                point_a = self.points_df.iloc[current_point, 0]
                point_b = self.points_df.iloc[self.origin_index, 0]
                path_length += self.distance(point_a, point_b)
                path_lengths.append(path_length)

                if path_length < best_path_length:
                    best_path = path
                    best_path_length = path_length

            # Update pheromones
            pheromone *= self.evaporation_rate

            for path, path_length in zip(paths, path_lengths):
                for i in range(len(path)-1):
                    pheromone[path[i], path[i + 1]] += self.Q / path_length
                pheromone[path[-1], path[0]] += self.Q / path_length

        print(f"\\n✅ Best solution found with total distance: {best_path_length:.2f} meters")
        self.best_path_id_p = [self.points_df.iloc[i, 0] for i in best_path]
        print(f"📍 Route points: {len([p for p in self.best_path_id_p if p != self.origin])} stores visited")

        self.load_best_path_id_p()
        self.con.close()

        return f'CVRP solved successfully. Solution ID: {self.dvrp_id}'
