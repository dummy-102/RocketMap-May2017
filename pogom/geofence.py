#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import pprint

log = logging.getLogger(__name__)


def parse_geofences(geofence_file):
    geofence_data = {}
    name = ''
    i = 0
    j = 0
    log.info('Looking for possible geofence areas')

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
                log.info('Found geofence for %s', name)
                continue

            if i not in geofence_data:
                j = j + 1
                log.debug('New key: %d', i)
                log.debug('New value for key %d', i)
                geofence_data[i] = {}
                geofence_data[i]['name'] = name
                geofence_data[i]['polygon'] = []
                lat, lon = line.strip().split(",")
                LatLon = {'lat': float(lat), 'lon': float(lon)}
                geofence_data[i]['polygon'].append(LatLon)
            else:
                j = j + 1
                log.debug('New value for key %d', i)
                lat, lon = (line.strip()).split(",")
                LatLon = {'lat': float(lat), 'lon': float(lon)}
                geofence_data[i]['polygon'].append(LatLon)

        log.info('Loaded %d geofence data for %d coordinates.', len(
            geofence_data), j)
        log.debug(pprint.PrettyPrinter(indent=4).pformat(geofence_data))

    return geofence_data


def pointInPolygon(point, polygon):
    log.info('Point: %s', point)
    log.debug('Point: %s', polygon)

    maxLat = polygon[0]['lat']
    minLat = polygon[0]['lat']
    maxLon = polygon[0]['lon']
    minLon = polygon[0]['lon']
    log.info(
        'Default Max/Min Lat and Lon: %s/%s, %s/%s',
        maxLat, minLat, maxLon, minLon)

    for coords in polygon:
        maxLat = max(coords['lat'], maxLat)
        minLat = min(coords['lat'], minLat)
        maxLon = max(coords['lon'], maxLon)
        minLon = min(coords['lon'], minLon)
    log.info(
        'Max/Min Lat and Lon: %s/%s, %s/%s',
        maxLat, minLat, maxLon, minLon)

    log.info('Start Quickcheck')
    if ((point['lat'] > maxLat) or (point['lat'] < minLat) or
            (point['lon'] > maxLon) or (point['lon'] < minLon)):
        return False

    log.info('Start Check')

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
