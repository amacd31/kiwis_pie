from collections import namedtuple
QueryOption = namedtuple('QueryOption', ['wildcard', 'list'])

import pandas as pd
import re
import requests

import logging
logger = logging.getLogger(__name__)

class KIWIS(object):
    def __init__(self, server_url):
        self.server_url = server_url
        self.default_args = {
            'service': 'kisters',
            'type': 'QueryServices',
            'format': 'json',
        }

        gen_kiwis_method(
            self.__class__,
            'getStationList',
            {
                'station_no': QueryOption(True, True),
                'station_id': QueryOption(False, True),
                'station_name': QueryOption(True, True),
                'catchment_no': QueryOption(False, True),
                'catchment_id': QueryOption(False, True),
                'catchment_name': QueryOption(True, True),
                'site_no': QueryOption(False, True),
                'site_id': QueryOption(False, True),
                'site_name': QueryOption(False, True),
                'stationgroup_id': QueryOption(False, False),
                'parametertype_id': QueryOption(False, True),
                'parametertype_name': QueryOption(True, True),
                'stationparameter_name': QueryOption(True, True),
            },
            [
                'station_no',
                'station_id',
                'station_name',
                'catchment_no',
                'catchment_id',
                'catchment_name',
                'station_latitude',
                'station_longitude',
                'station_carteasting',
                'station_cartnorthing',
                'site_no',
                'site_id',
                'site_name',
                'parametertype_id',
                'parametertype_name',
                'stationparameter_name',
                'object_type',
                'station_georefsystem',
                'station_longname',
                'custom_attributes',
            ]
        )

def gen_kiwis_method(cls, method_name, available_query_options, available_return_fields):

    start_snake = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', method_name)
    snake_name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', start_snake).lower()

    def kiwis_method(self, return_fields = None, **kwargs):
        """
        """

        for query_key in kwargs.keys():
            if query_key not in available_query_options.keys():
                raise ValueError(query_key)

        for return_key in return_fields:
            if return_key not in available_return_fields:
                raise ValueError(return_key)

        params = self.default_args.copy()
        params.update(kwargs)
        params['request'] = 'getStationList'
        if return_fields is not None:
            params['returnfields'] = ','.join(return_fields)
        r = requests.get(self.server_url, params = params)

        json_data = r.json()
        return pd.DataFrame(json_data[1:], columns = json_data[0])

    setattr(cls, snake_name, kiwis_method)
