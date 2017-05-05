import os
import pandas as pd
import pkg_resources
import unittest
import requests_mock

from io import BytesIO, StringIO

from kiwis_pie import KIWIS

class KIWISTest(unittest.TestCase):

    def setUp(self):
        self.k = KIWIS('http://www.bom.gov.au/waterdata/services')

    @requests_mock.mock()
    def test_get_parameter_list(self, m):
        response = StringIO(BytesIO(pkg_resources.resource_string(__name__, 'test_data/bom_parameter_list.request')).read().decode('UTF-8')).read()

        m.get(
            'http://www.bom.gov.au/waterdata/services?station_no=410730&type=QueryServices&service=kisters&format=json&request=getParameterList',
            text = response
        )

        expected = pd.read_csv(
            pkg_resources.resource_stream(
                __name__,
                'test_data/bom_parameter_list.csv'
            )
        )

        df = self.k.get_parameter_list(station_no = '410730')
        expected.equals(df)

