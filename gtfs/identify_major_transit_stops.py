import csv
from os.path import join
from collections import defaultdict, namedtuple
from time import strptime
import argparse


BUS_ROUTE_TYPE = 3
FERRY_ROUTE_TYPE = 4

EIGHT_AM_START = '08:'
FIVE_PM_START = '17:'

merged_stop_fields = ['stop_ids', 'stop_lat', 'stop_lon', 'stop_name']
MergedStop = namedtuple('MergedStop', merged_stop_fields)
MergedRoute = namedtuple('MergedRoute', [
    'route_type', 'route_ids', 'route_short_names'])


class CSVRow(object):
    def __init__(self, column_to_index, data):
        self.column_to_index = column_to_index
        self.data = data

    def __getitem__(self, key):
        return self.data[self.column_to_index[key]]

    def __repr__(self):
        return repr({
            column: self.data[index]
            for column, index in self.column_to_index.iteritems()
        })


def csv_rows(filename):
    with open(filename, 'rb') as stop_times:
        reader = csv.reader(stop_times)
        columns = next(reader)
        column_to_index = {
            column: index
            for index, column in enumerate(columns)
        }
        for data in reader:
            yield CSVRow(column_to_index, data)


def write_merged_stops(stops, filename):
    with open(filename, 'wb') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(merged_stop_fields)
        for stop in stops:
            writer.writerow(stop)


def index_by(items, fn):
    result = {}
    for item in items:
        key = fn(item)
        assert key not in result, 'duplicate key {}'.format(key)
        result[key] = item
    return result


def group_by(items, fn):
    result = {}
    for item in items:
        result.setdefault(fn(item), []).append(item)
    return result


def avg(items):
    if not items:
        return float('nan')
    return sum(items) / len(items)


def merged_routes(agency, routes):
    '''
    This method will merge similar bus routes together. for instance, SFMTA's
    5 and 5R are merged in this method. This feels appropriate because the 5R
    tends to have a subset of the 5's stops.

    Interestingly, the combined bus route may have better time coverage and
    might satisfy frequency constraints better than either individual route
    would have.
    '''

    duplicated_routes_by_short_name = []
    if agency['agency_id'] == 'SFMTA':
        import sfmta
        duplicated_routes_by_short_name = sfmta.duplicated_routes

    short_name_to_key = {
        short_name: key
        for key in duplicated_routes_by_short_name
        for short_name in key
    }

    def _key(route):
        return short_name_to_key.get(route['route_short_name']) or\
            route['route_id']

    return [
        MergedRoute(
            int(route_group[0]['route_type']),
            frozenset([route['route_id'] for route in route_group]),
            frozenset([route['route_short_name'] for route in route_group]),
        )
        for key, route_group in group_by(routes, _key).iteritems()
    ]


def merged_stops(stops):
    # this key will group stops of similar intersections, like:
    # > 24th St & Mission St
    # > Mission St & 24th St
    # This feels like a proper way to implement the definition in the proposal
    # > a site containing ... the intersection of two or more major bus routes
    def _cross_street_key(stop):
        bits = stop['stop_name'].split('&')
        return frozenset(bit.strip() for bit in bits)

    stops_by_cross = group_by(stops, _cross_street_key)

    return [
        MergedStop(
            [stop['stop_id'] for stop in shared_cross_stops],
            avg([float(stop['stop_lat']) for stop in shared_cross_stops]),
            avg([float(stop['stop_lon']) for stop in shared_cross_stops]),
            shared_cross_stops[0]['stop_name'],
        )
        for shared_cross_stops in stops_by_cross.values()
    ]


def _are_times_close(times):
    '''
    `times` is a list of times that are all in the same hour. This function
    returns true when all the times are close enough together.
    '''
    times = sorted(times)
    FIFTEEN_MINUTES_IN_SECONDS = 15 * 60
    for time1, time2 in zip(times[:-1], times[1:]):
        time2sec = time2.tm_min * 60 + time2.tm_sec
        time1sec = time1.tm_min * 60 + time1.tm_sec
        if time2sec - time1sec > FIFTEEN_MINUTES_IN_SECONDS:
            return False
    return True


def major_transit_stops(basedir):
    '''
    http://www.dof.ca.gov/budgeting/trailer_bill_language/local_government/documents/707StreamliningAffordableHousingApprovals.pdf
    "Major Transit Stop" is defined by the proposal as follows (my notes in
    square brackets):
        - an existing rail transit station,
        - a ferry terminal served by either a bus or rail transit service, or
            - [not yet implemented]
        - the intersection of two or more major bus routes with
            - a service interval frequency of 15 minutes or less during the
            morning and afternoon peak weekday commute periods,
                - [we check 8-9am and 5-6pm on monday]
            - and offering weekend service.
                - [any weekend service qualifies]
    '''
    agency = next(csv_rows(join(basedir, 'agency.txt')))
    stops = list(csv_rows(join(basedir, 'stops.txt')))
    routes = merged_routes(agency, list(csv_rows(join(basedir, 'routes.txt'))))
    routes_by_id = {
        route_id: route
        for route in routes
        for route_id in route.route_ids
    }
    stop_times_by_stop_id = group_by(
        csv_rows(join(basedir, 'stop_times.txt')),
        lambda row: row['stop_id'])
    trips_by_id = index_by(
        csv_rows(join(basedir, 'trips.txt')),
        lambda row: row['trip_id'])
    calendar_by_service_id = index_by(
        csv_rows(join(basedir, 'calendar.txt')),
        lambda row: row['service_id'])

    def parse_time(time):
        return strptime(time, '%H:%M:%S')

    def is_major(merged_stop):
        stop_times = [
            stop_time
            for stop_id in merged_stop.stop_ids
            for stop_time in stop_times_by_stop_id.get(stop_id) or []
        ]
        eight_am = defaultdict(lambda: set())
        five_pm = defaultdict(lambda: set())
        weekend = {}

        # XXX AC transit has time gaps. worth checking here?
        def _frequent_rush_hour(time_strings):
            return _are_times_close(map(parse_time, time_strings))

        def _is_major_bus_route(route_ids):
            return weekend.get(route_ids) and\
                _frequent_rush_hour(eight_am[route_ids]) and\
                _frequent_rush_hour(five_pm[route_ids])

        for stop_time in stop_times:
            trip = trips_by_id[stop_time['trip_id']]
            route = routes_by_id[trip['route_id']]
            route_type = route.route_type
            if route_type == BUS_ROUTE_TYPE:
                calendar = calendar_by_service_id[trip['service_id']]
                is_weekend = bool(int(calendar['saturday'])) or\
                    bool(int(calendar['sunday']))
                if is_weekend:
                    weekend[route.route_ids] = True

                # XXX only checking monday out of superstition?
                if bool(int(calendar['monday'])):
                    hour = None
                    if stop_time['arrival_time'].startswith(EIGHT_AM_START):
                        hour = eight_am
                    elif stop_time['arrival_time'].startswith(FIVE_PM_START):
                        hour = five_pm
                    if hour is not None:
                        hour[route.route_ids].add(stop_time['arrival_time'])
            elif route_type == FERRY_ROUTE_TYPE:
                # XXX do this correctly
                return True
            else:
                return True

        return len([
            route_ids
            for route_ids in eight_am.keys()
            if _is_major_bus_route(route_ids)
        ]) >= 2

    return (
        merged_stop
        for merged_stop in merged_stops(stops)
        if is_major(merged_stop)
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Process GTFS to find major transit stops.')
    parser.add_argument('gtfs_dir', help='the directory of the unpacked GTFS.')
    parser.add_argument(
        '-o', '--output', dest='output',
        help='the path to write the major transit stops.')
    args = parser.parse_args()
    stops = major_transit_stops(args.gtfs_dir)
    write_merged_stops(stops, args.output)
