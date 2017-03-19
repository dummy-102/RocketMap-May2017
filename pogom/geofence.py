#!/usr/bin/python
# -*- coding: utf-8 -*-

import time
import logging
import pprint

log = logging.getLogger(__name__)

geofence_data = {}


def parse_geofences(geofence_file):
    name = ''
    i = 0
    j = 0
    log.info('Looking for geofenced areas')
    startTime = time.time()

    # Read coordinates of areas from file
    with open(geofence_file) as f:
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
        'Loaded %d geofence(s) with a total of %d coordinates in %s s',
        len(geofence_data), j, elapsedTime)
    log.debug(
        'Geofenced results: \n\r{}'.format(
        pprint.PrettyPrinter(indent=4).pformat(geofence_data)))

    return geofence_data


def pointInPolygon(point, polygon):
    log.debug('Point: %s', point)
    log.debug('Point: %s', polygon)

    maxLat = polygon[0]['lat']
    minLat = polygon[0]['lat']
    maxLon = polygon[0]['lon']
    minLon = polygon[0]['lon']
    log.debug(
        'Default Max/Min Lat and Lon: %s/%s, %s/%s',
        maxLat, minLat, maxLon, minLon)

    for coords in polygon:
        maxLat = max(coords['lat'], maxLat)
        minLat = min(coords['lat'], minLat)
        maxLon = max(coords['lon'], maxLon)
        minLon = min(coords['lon'], minLon)
    log.debug(
        'Max/Min Lat and Lon: %s/%s, %s/%s',
        maxLat, minLat, maxLon, minLon)

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


def geofence_results(results):
    results_geofenced = []
    startTime = time.time()
    for result in results:
        point = {'lat': result[0], 'lon': result[1]}
        for geofence in geofence_data:
            if pointInPolygon(point, geofence_data[geofence]['polygon']):
                results_geofenced.append(result)

    endTime = time.time()
    elapsedTime = endTime - startTime
    log.info('Geofenced cells in %s s', elapsedTime)
    log.debug(
        'Geofenced results: \n\r{}'.format(
        pprint.PrettyPrinter(indent=4).pformat(results_geofenced)))

    return results_geofenced
