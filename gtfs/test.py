import unittest
import identify_major_transit_stops
from datetime import datetime


def _time(hour=0, minute=0, second=0):
    return datetime(
        year=1970, month=1, day=1,
        hour=hour, minute=minute, second=second).timetuple()


class Test(unittest.TestCase):
    def test_are_times_close(self):
        self.assertTrue(identify_major_transit_stops._are_times_close([
            _time(hour=3, minute=0),
            _time(hour=3, minute=10),
            _time(hour=3, minute=20),
            _time(hour=3, minute=30),
        ]))

    def test_are_times_not_close_beginning(self):
        self.assertFalse(identify_major_transit_stops._are_times_close([
            _time(hour=3, minute=0),
            _time(hour=3, minute=20),
            _time(hour=3, minute=30),
            _time(hour=3, minute=40),
        ]))

    def test_are_times_not_close_end(self):
        self.assertFalse(identify_major_transit_stops._are_times_close([
            _time(hour=3, minute=0),
            _time(hour=3, minute=10),
            _time(hour=3, minute=20),
            _time(hour=3, minute=40),
        ]))

    def test_merged_routes(self):
        merged = sorted(identify_major_transit_stops.merged_routes(
            {'agency_id': 'SFMTA'},
            [
                {
                    'route_type': '3',
                    'route_id': 0,
                    'route_short_name': '5',
                },
                {
                    'route_type': '3',
                    'route_id': 1,
                    'route_short_name': '5R',
                },
                {
                    'route_type': '3',
                    'route_id': 2,
                    'route_short_name': '44',
                },
            ]
        ))
        self.assertEqual(merged[0], (3, {2}, {'44'}))
        self.assertEqual(merged[1], (3, {0, 1}, {'5', '5R'}))

    def test_merged_stops(self):
        merged = sorted(identify_major_transit_stops.merged_stops([
            {
                'stop_id': 0,
                'stop_name': '24th St & Mission St',
                'stop_lat': '-1',
                'stop_lon': '5',
            },
            {
                'stop_id': 1,
                'stop_name': 'Mission St & 24th St',
                'stop_lat': '1',
                'stop_lon': '3',
            },
            {
                'stop_id': 2,
                'stop_name': 'Bryant St & 24th St',
                'stop_lat': '7',
                'stop_lon': '9',
            },
        ]))
        self.assertEqual(merged[0], ([0, 1], 0, 4, '24th St & Mission St'))
        self.assertEqual(merged[1], ([2], 7, 9, 'Bryant St & 24th St'))


if __name__ == '__main__':
    unittest.main()
