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
                lat, lon = (line.strip()).split(",")
                LatLon = {'lat': lat, 'lon': lon}
                geofence_data[i]['polygon'].append(LatLon)
            else:
                j = j + 1
                log.debug('New value for key %d', i)
                lat, lon = (line.strip()).split(",")
                LatLon = {'lat': lat, 'lon': lon}
                geofence_data[i]['polygon'].append(LatLon)

        log.info('Loaded %d geofence data for %d coordinates.', len(
            geofence_data), j)
        log.debug(pprint.PrettyPrinter(indent=4).pformat(geofence_data))

    return geofence_data
