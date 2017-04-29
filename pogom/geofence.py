#!/usr/bin/python
# -*- coding: utf-8 -*-

import time
import logging

from matplotlib.path import Path

#from .models import Geofence  # Why you no work? :-O

log = logging.getLogger(__name__)


class Geofences:
    def __init__(self, args, db_model, db_updates_queue):
        self.args = args

        if self.args.geofence_file or self.args.forbidden_area is not None:
            self.geofence_file = self.args.geofence_file
            self.forbidden_file = self.args.forbidden_file
            self.db_model = db_model
            self.db_updates_queue = db_updates_queue

            self.parse_geofences()
            self.push_db_geofences()
        else:
            self.geofences = {}

    def get_geofences():
        return self.geofences

    def is_enabled(self):
        enabled = False
        if self.geofences:
            enabled = True

        return enabled

    def parse_geofences(self):
        geofence_data = {}
        name = ''
        log.info('Looking for geofenced or forbidden areas')

        i = 0
        if self.geofence_file:
            j = 0
            startTime = time.time()

            # Read coordinates of geofences from file
            with open(self.geofence_file) as f:
                for line in f:
                    if len(line.strip()) == 0:
                        continue
                    elif line.startswith("["):  # Find new areas through comments
                        i = i + 1
                        nameLine = line.strip()
                        nameLine = nameLine.replace("[", "")
                        name = nameLine.replace("]", "")
                        log.info('Found geofence: %s', name)
                        continue

                    if i not in geofence_data:
                        j = j + 1
                        geofence_data[i] = {}
                        geofence_data[i]['forbidden'] = False
                        geofence_data[i]['name'] = name
                        geofence_data[i]['polygon'] = []
                        lat, lon = line.strip().split(",")
                        LatLon = {'lat': float(lat), 'lon': float(lon)}
                        geofence_data[i]['polygon'].append(LatLon)
                    else:
                        j = j + 1
                        lat, lon = (line.strip()).split(",")
                        LatLon = {'lat': float(lat), 'lon': float(lon)}
                        geofence_data[i]['polygon'].append(LatLon)

            endTime = time.time()
            elapsedTime = endTime - startTime
            lenGeofenceData = len(geofence_data)
            log.info(
                'Loaded %d geofences with a total of %d coordinates in %.2f s',
                lenGeofenceData, j, elapsedTime)

        if self.forbidden_file:
            j = 0
            startTime = time.time()

            # Read coordinates of forbidden areas from file
            with open(self.forbidden_file) as f:
                for line in f:
                    if len(line.strip()) == 0:
                        continue
                    elif line.startswith("["):  # Find new areas through comments
                        i = i + 1
                        nameLine = line.strip()
                        nameLine = nameLine.replace("[", "")
                        name = nameLine.replace("]", "")
                        log.info('Found forbidden area: %s', name)
                        continue

                    if i not in geofence_data:
                        j = j + 1
                        geofence_data[i] = {}
                        geofence_data[i]['forbidden'] = True
                        geofence_data[i]['name'] = name
                        geofence_data[i]['polygon'] = []
                        lat, lon = line.strip().split(",")
                        LatLon = {'lat': float(lat), 'lon': float(lon)}
                        geofence_data[i]['polygon'].append(LatLon)
                    else:
                        j = j + 1
                        lat, lon = (line.strip()).split(",")
                        LatLon = {'lat': float(lat), 'lon': float(lon)}
                        geofence_data[i]['polygon'].append(LatLon)

            endTime = time.time()
            elapsedTime = endTime - startTime
            log.info(
                'Loaded %d forbidden areas with a total of %d coordinates ' +
                'in %.2f s',
                len(geofence_data) - lenGeofenceData, j, elapsedTime)

        self.geofences = geofence_data

    def geofence_results(self, results):
        log.info('Found %d cells to geofence.', len(results))
        results_geofenced = []
        if self.geofences:
            startTime = time.time()
            for result in results:
                point = {'lat': result[0], 'lon': result[1]}
                for geofence in self.geofences:
                    if not self.geofences[geofence]['forbidden']:
                        if not self.args.no_matplotlib:  # Argument matplotlib
                            if self.point_in_polygon_matplotlib(
                                    point, self.geofences[geofence]['polygon']):
                                results_geofenced.append(result)
                        else:
                            if self.point_in_polygon_custom(
                                    point, self.geofences[geofence]['polygon']):
                                results_geofenced.append(result)
                    if self.geofences[geofence]['forbidden']:
                        if not self.args.no_matplotlib:  # Argument matplotlib
                            if self.point_in_polygon_matplotlib(
                                    point, self.geofences[geofence]['polygon']):
                                results_geofenced.pop(len(results_geofenced)-1)
                        else:
                            if self.point_in_polygon_custom(
                                    point, self.geofences[geofence]['polygon']):
                                results_geofenced.pop(len(results_geofenced)-1)

            endTime = time.time()
            elapsedTime = endTime - startTime
            log.info(
                'Geofenced to %s cells in %.2f s',
                len(results_geofenced), elapsedTime)

        return results_geofenced

    def push_db_geofences(self):
        db_geofences = {}

        key = 0
        id = 0
        for key in range(1, len(self.geofences) + 1):
            coords = 0
            for coords in range(0, len(self.geofences[key]['polygon'])):
                id = id + 1
                db_geofences[id] = {
                    'geofence_id': key,
                    'forbidden': self.geofences[key]['forbidden'],
                    'name': self.geofences[key]['name'],
                    'coordinates_id': coords,
                    'latitude': self.geofences[key]['polygon'][coords]['lat'],
                    'longitude': self.geofences[key]['polygon'][coords]['lon']
                }

        self.db_model.clear_all()  # Remove old geofences from DB

        self.db_updates_queue.put((self.db_model, db_geofences))
        log.debug('Upserted %d geofence entries.', len(db_geofences))

    @staticmethod
    def point_in_polygon_custom(point, polygon):

        # Initialize first coordinate as default.
        maxLat = polygon[0]['lat']
        minLat = polygon[0]['lat']
        maxLon = polygon[0]['lon']
        minLon = polygon[0]['lon']

        for coords in polygon:
            maxLat = max(coords['lat'], maxLat)
            minLat = min(coords['lat'], minLat)
            maxLon = max(coords['lon'], maxLon)
            minLon = min(coords['lon'], minLon)

        # Quickcheck
        if ((point['lat'] > maxLat) or (point['lat'] < minLat) or
                (point['lon'] > maxLon) or (point['lon'] < minLon)):
            return False

        inside = False
        lat1, lon1 = polygon[0]['lat'], polygon[0]['lon']
        N = len(polygon)
        for n in range(1, N+1):
            lat2, lon2 = polygon[n % N]['lat'], polygon[n % N]['lon']
            if (min(lon1, lon2) < point['lon'] <= max(lon1, lon2) and
                    point['lat'] <= max(lat1, lat2)):
                        if lon1 != lon2:
                            latIntersection = (
                                (point['lon'] - lon1) *
                                (lat2 - lat1) / (lon2 - lon1) +
                                lat1)

                        if lat1 == lat2 or point['lat'] <= latIntersection:
                            inside = not inside

            lat1, lon1 = lat2, lon2

        return inside

    @staticmethod
    def point_in_polygon_matplotlib(point, polygon):
        pointTouple = (point['lat'], point['lon'])
        polygonToupleList = []
        for c in polygon:
            coordinateTouple = (c['lat'], c['lon'])
            polygonToupleList.append(coordinateTouple)

        polygonToupleList.append(polygonToupleList[0])
        path = Path(polygonToupleList)

        return path.contains_point(pointTouple)
