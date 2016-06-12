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
            'getTimeseriesList',
            {
                'station_no': QueryOption(True, True),
                'station_id': QueryOption(False, True),
                'station_name': QueryOption(True, True),
                'ts_id': QueryOption(False, True),
                'ts_path': QueryOption(True, True),
                'ts_name': QueryOption(True, True),
                'ts_shortname': QueryOption(True, True),
                'ts_type_id': QueryOption(False, True),
                'parametertype_id': QueryOption(False, True),
                'parametertype_name': QueryOption(True, True),
                'stationparameter_name': QueryOption(True, True),
                'stationparameter_no': QueryOption(False, True),
                'ts_unitname': QueryOption(True, True),
                'timeseriesgroup_id': QueryOption(False, False),
                'fulltext': QueryOption(True, False),
            },
            [
                'station_no',
                'station_id',
                'station_name',
                'station_latitude',
                'station_longitude',
                'station_carteasting',
                'station_cartnorthing',
                'station_georefsystem',
                'station_longname',
                'ts_id',
                'ts_name',
                'ts_shortname',
                'ts_pat',
                'parametertype_id',
                'parametertype_name',
                'stationparameter_name',
                'stationparameter_longname',
                'ts_unitname',
                'ts_unitsymbol',
                'ts_unitname_abs',
                'ts_unitsymbol_abs',
                'coverage',
                'ts_density',
                'datacart',
            ]
        )

        gen_kiwis_method(
            self.__class__,
            'getTimeseriesValues',
            {
                'ts_id': QueryOption(False, True),
                'timeseriesgroup_id': QueryOption(False, True),
                'ts_path': QueryOption(True, True),
                'from': QueryOption(None, None),
                'to': QueryOption(None, None),
                'period': QueryOption(None, None),
            },
            [
                'Timestamp',
                'Value',
                'Interpolation Type',
                'Quality Code',
                'Aggregation',
                'Accuracy',
                'Absolute Value',
                'AV Interpolation',
                'Type',
                'AV Quality Code',
                'Runoff Value',
                'RV Interpolation',
                'Type',
                'RV Quality Code',
            ]
        )

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
        params['request'] = method_name
        if return_fields is not None:
            params['returnfields'] = ','.join(return_fields)
        r = requests.get(self.server_url, params = params)
        logger.debug(r.url)

        json_data = r.json()
        if method_name in ['getStationList', 'getTimeseriesList']:
            return pd.DataFrame(json_data[1:], columns = json_data[0])
        elif method_name in ['getTimeseriesValues']:
            return pd.DataFrame(json_data[0]['data'], columns = json_data[0]['columns'].split(','))
        else:
            raise NotImplementedError("Method '{0}' has no return implemented.".format(method_name))

    setattr(cls, snake_name, kiwis_method)
