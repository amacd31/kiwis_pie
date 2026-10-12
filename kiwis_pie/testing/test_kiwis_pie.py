import datetime
import importlib.resources
import json
from io import StringIO
import unittest
import pandas as pd
import requests_mock

from kiwis_pie import KIWIS, KIWISError, NoDataError


class KIWISTest(unittest.TestCase):

    def setUp(self):
        self.k = KIWIS('http://www.bom.gov.au/waterdata/services')

    @requests_mock.mock()
    def test_get_parameter_list(self, m):
        test_data = importlib.resources.files(__package__).joinpath("test_data")
        response = test_data.joinpath("bom_parameter_list.request").read_bytes().decode('UTF-8')

        m.get(
            'http://www.bom.gov.au/waterdata/services?station_no=410730&type=QueryServices&service=kisters&format=json&request=getParameterList',
            text = response
        )

        expected = pd.read_csv(
            StringIO(test_data.joinpath("bom_parameter_list.csv").read_text())
        )

        df = self.k.get_parameter_list(station_no = '410730')
        self.assertEqual(len(df), 7)
        self.assertIn('station_name', df.columns)
        self.assertEqual(set(df['stationparameter_name']), set(expected['stationparameter_name']))

    def test_all_requests_present(self):
        expected_methods = [
            'get_group_list',
            'get_site_list',
            'get_station_list',
            'get_parameter_list',
            'get_parameter_type_list',
            'get_catchment_list',
            'get_catchment_hierarchy',
            'get_river_list',
            'get_standard_remark_type_list',
            'get_rating_curve_list',
            'get_station_lithology',
            'get_station_casing',
            'get_timeseries_list',
            'get_timeseries_type_list',
            'get_timeseries_values',
            'get_timeseries_value_layer',
            'get_graph_template_list',
            'get_graph',
            'get_station_graph',
            'get_color_classifications',
            'get_quality_codes',
            'get_release_state_classes',
            'get_timeseries_release_state_list',
            'get_timeseries_ensemble_values',
            'get_timeseries_changes',
            'get_timeseries_comments',
            'check_value_limit',
        ]
        for method_name in expected_methods:
            self.assertTrue(hasattr(self.k, method_name), f"Missing method: {method_name}")

    @requests_mock.mock()
    def test_get_group_list(self, m):
        mock_response = [
            ["group_name", "group_id", "group_type"],
            ["Group A", "1", "station"],
            ["Group B", "2", "timeseries"]
        ]
        m.get(
            'http://www.bom.gov.au/waterdata/services?service=kisters&type=QueryServices&format=json&request=getGroupList',
            text=json.dumps(mock_response)
        )
        df = self.k.get_group_list()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 2)
        self.assertListEqual(list(df.columns), ["group_name", "group_id", "group_type"])

    @requests_mock.mock()
    def test_get_catchment_hierarchy(self, m):
        mock_response = {"catchment_id": 123, "name": "Main Catchment", "children": []}
        m.get(
            'http://www.bom.gov.au/waterdata/services?catchment_id=123&service=kisters&type=QueryServices&format=json&request=getCatchmentHierarchy',
            text=json.dumps(mock_response)
        )
        res = self.k.get_catchment_hierarchy(catchment_id="123")
        self.assertEqual(res, mock_response)

    @requests_mock.mock()
    def test_get_timeseries_values(self, m):
        mock_response = [{
            "columns": "Timestamp,Value,Quality Code",
            "data": [
                ["2023-01-01 00:00:00+10:00", 12.5, "100"],
                ["2023-01-01 01:00:00+10:00", 13.0, "100"]
            ]
        }]
        m.get(
            'http://www.bom.gov.au/waterdata/services?ts_id=123&from=2023-01-01&to=2023-01-02&service=kisters&type=QueryServices&format=json&request=getTimeseriesValues',
            text=json.dumps(mock_response)
        )
        df = self.k.get_timeseries_values(
            ts_id="123",
            **{'from': datetime.date(2023, 1, 1), 'to': datetime.date(2023, 1, 2)}
        )
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 2)
        self.assertIn('Value', df.columns)

    @requests_mock.mock()
    def test_get_graph(self, m):
        fake_png = b'\x89PNG\r\n\x1a\nfakecontent'
        fake_jpg = b'\xff\xd8\xfffakecontent'
        m.get(
            'http://www.bom.gov.au/waterdata/services?ts_id=123&service=kisters&type=QueryServices&format=png&request=getGraph',
            content=fake_png
        )
        m.get(
            'http://www.bom.gov.au/waterdata/services?ts_id=123&format=jpg&service=kisters&type=QueryServices&request=getGraph',
            content=fake_jpg
        )
        # Default format is png
        res = self.k.get_graph(ts_id="123")
        self.assertEqual(res, fake_png)

        # Explicit format jpg
        res_jpg = self.k.get_graph(ts_id="123", format="jpg")
        self.assertEqual(res_jpg, fake_jpg)

        # Invalid format json raises ValueError
        with self.assertRaises(ValueError):
            self.k.get_graph(ts_id="123", format="json")

    @requests_mock.mock()
    def test_get_station_graph(self, m):
        fake_png = b'\x89PNG\r\n\x1a\nfakecontent'
        fake_jpg = b'\xff\xd8\xfffakecontent'
        m.get(
            'http://www.bom.gov.au/waterdata/services?station_id=123&template=default&service=kisters&type=QueryServices&format=png&request=getStationGraph',
            content=fake_png
        )
        m.get(
            'http://www.bom.gov.au/waterdata/services?station_id=123&template=default&format=jpg&service=kisters&type=QueryServices&request=getStationGraph',
            content=fake_jpg
        )
        # Default format is png
        res = self.k.get_station_graph(station_id="123", template="default")
        self.assertEqual(res, fake_png)

        # Explicit format jpg
        res_jpg = self.k.get_station_graph(station_id="123", template="default", format="jpg")
        self.assertEqual(res_jpg, fake_jpg)

        # Invalid format json raises ValueError
        with self.assertRaises(ValueError):
            self.k.get_station_graph(station_id="123", template="default", format="json")

    @requests_mock.mock()
    def test_kiwis_error(self, m):
        m.get(
            'http://www.bom.gov.au/waterdata/services?service=kisters&type=QueryServices&format=json&request=getSiteList',
            text=json.dumps({"type": "error", "code": "500", "message": "Internal Server Error"})
        )
        with self.assertRaises(KIWISError):
            self.k.get_site_list()

    @requests_mock.mock()
    def test_no_data_error(self, m):
        m.get(
            'http://www.bom.gov.au/waterdata/services?service=kisters&type=QueryServices&format=json&request=getSiteList',
            text=json.dumps(["No matches."])
        )
        with self.assertRaises(NoDataError):
            self.k.get_site_list()

    def test_strict_mode_validation(self):
        with self.assertRaises(ValueError):
            self.k.get_site_list(invalid_parameter_foo="bar")

        with self.assertRaises(ValueError):
            self.k.get_site_list(return_fields=["invalid_return_field_foo"])

    @requests_mock.mock()
    def test_list_query_option(self, m):
        mock_response = [["site_no", "site_id"], ["1", "101"], ["2", "102"]]
        m.get(
            'http://www.bom.gov.au/waterdata/services?site_no=1%2C2&service=kisters&type=QueryServices&format=json&request=getSiteList',
            text=json.dumps(mock_response)
        )
        df = self.k.get_site_list(site_no=['1', '2'])
        self.assertEqual(len(df), 2)

    @requests_mock.mock()
    def test_get_station_list_geojson(self, m):
        geojson_response = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [148.834, -35.53]
                    },
                    "properties": {
                        "station_name": "Cotter R. at Gingera",
                        "station_no": "410730"
                    }
                }
            ]
        }
        m.get(
            'http://www.bom.gov.au/waterdata/services?station_name=Cotter+R.+at+Gingera&format=geojson&service=kisters&type=QueryServices&request=getStationList',
            text=json.dumps(geojson_response)
        )
        res = self.k.get_station_list(station_name='Cotter R. at Gingera', format='geojson')
        self.assertIsInstance(res, dict)
        self.assertEqual(res['type'], 'FeatureCollection')
        self.assertEqual(len(res['features']), 1)
        self.assertEqual(res['features'][0]['properties']['station_name'], 'Cotter R. at Gingera')

    @requests_mock.mock()
    def test_get_timeseries_value_layer_geojson(self, m):
        geojson_response = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [148.834, -35.53]
                    },
                    "properties": {
                        "ts_id": "12345",
                        "value": 24.5
                    }
                }
            ]
        }
        m.get(
            'http://www.bom.gov.au/waterdata/services?ts_id=12345&format=geojson&service=kisters&type=QueryServices&request=getTimeseriesValueLayer',
            text=json.dumps(geojson_response)
        )
        res = self.k.get_timeseries_value_layer(ts_id='12345', format='geojson')
        self.assertIsInstance(res, dict)
        self.assertEqual(res['type'], 'FeatureCollection')
        self.assertEqual(res['features'][0]['properties']['value'], 24.5)

    @requests_mock.mock()
    def test_get_site_list_geojson(self, m):
        geojson_response = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-122.5, 38.3]
                    },
                    "properties": {
                        "site_name": "Santa Rosa Plain",
                        "site_no": "SRP"
                    }
                }
            ]
        }
        m.get(
            'http://www.bom.gov.au/waterdata/services?site_no=SRP&format=geojson&service=kisters&type=QueryServices&request=getSiteList',
            text=json.dumps(geojson_response)
        )
        res = self.k.get_site_list(site_no='SRP', format='geojson')
        self.assertIsInstance(res, dict)
        self.assertEqual(res['type'], 'FeatureCollection')
        self.assertEqual(res['features'][0]['properties']['site_no'], 'SRP')

    @requests_mock.mock()
    def test_non_json_format_fallback(self, m):
        csv_response = "station_name,station_no\nCotter R.,410730\n"
        m.get(
            'http://www.bom.gov.au/waterdata/services?format=csv&service=kisters&type=QueryServices&request=getStationList',
            text=csv_response
        )
        res = self.k.get_station_list(format='csv')
        self.assertEqual(res, csv_response)

