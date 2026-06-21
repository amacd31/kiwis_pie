import importlib.resources

import pandas as pd
import unittest
import requests_mock

from io import StringIO

from kiwis_pie import KIWIS

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
        expected.equals(df)

