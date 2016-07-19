import collections
QueryOption = collections.namedtuple('QueryOption', ['wildcard', 'list', 'parser'])

import pandas as pd
import re
import requests
from tabulate import tabulate

import logging
logger = logging.getLogger(__name__)

try:
    basestring
except NameError:
    basestring = str

class KIWISError(Exception):
    pass

class NoDataError(Exception):
    pass

class KIWIS(object):
    def __init__(self, server_url):
        self.server_url = server_url
        self.__default_args = {
            'service': 'kisters',
            'type': 'QueryServices',
            'format': 'json',
        }

def __parse_date(input_dt):
    return pd.datetools.to_datetime(input_dt).strftime('%Y-%m-%d')

def __gen_kiwis_method(cls, method_name, available_query_options, available_return_fields):

    start_snake = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', method_name)
    snake_name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', start_snake).lower()

    def kiwis_method(self, return_fields = None, **kwargs):

        for query_key in kwargs.keys():
            if query_key not in available_query_options.keys():
                raise ValueError(query_key)

            if (available_query_options[query_key].list and
                    isinstance(kwargs[query_key], collections.Iterable) and
                    not isinstance(kwargs[query_key], basestring)):
                kwargs[query_key] = ','.join(kwargs[query_key])

            if available_query_options[query_key].parser is not None:
                kwargs[query_key] = available_query_options[query_key].parser(kwargs[query_key])

        if return_fields is not None:
            for return_key in return_fields:
                if return_key not in available_return_fields:
                    raise ValueError(return_key)

        params = self.__default_args.copy()
        params.update(kwargs)
        params['request'] = method_name
        if return_fields is not None:
            params['returnfields'] = ','.join(return_fields)
        r = requests.get(self.server_url, params = params)
        logger.debug(r.url)

        json_data = r.json()
        if type(json_data) is dict and 'type' in json_data.keys() and json_data['type'] == 'error':
            raise KIWISError(
                'KIWIS returned an error:\n\tCode: {0}\n\tMessage: "{1}"'.format(
                    json_data['code'],
                    json_data['message']
                )
            )

        if json_data is None or json_data[0] == "No matches.":
            raise NoDataError()

        if method_name in ['getSiteList', 'getStationList', 'getTimeseriesList']:
            return pd.DataFrame(json_data[1:], columns = json_data[0])
        elif method_name in ['getTimeseriesValues']:
            df = pd.DataFrame(json_data[0]['data'], columns = json_data[0]['columns'].split(','))
            if 'Timestamp' in df.columns:
                df.set_index('Timestamp', inplace = True)
                df.index = pd.to_datetime(df.index)
            return df
        else:
            raise NotImplementedError("Method '{0}' has no return implemented.".format(method_name))

    docstring = {}
    docstring['doc_intro'] = "Python method to query the '{0}' KiWIS method.".format(snake_name)

    docstring['return_fields'] = "Takes the return_fields keyword argument, which is a list made up from the following available fields:\n\t{0}.".format(',\n\t'.join(available_return_fields))

    doc_map = {
        True: 'yes',
        False: 'no',
        None: 'n/a',
    }

    option_list = [['Queryfield name', '\* as wildcard', 'accepts list']]
    for option_name, option_details in available_query_options.items():
        option_list.append(
            [
                option_name,
                doc_map[option_details.wildcard],
                doc_map[option_details.list],
            ]
        )

    docstring['query_option_table'] = tabulate(option_list, headers = 'firstrow', tablefmt = 'rst')

    kiwis_method.__doc__ = "{doc_intro}\n\n{query_option_table}\n\n{return_fields}".format(**docstring)

    setattr(cls, snake_name, kiwis_method)

__gen_kiwis_method(
    KIWIS,
    'getTimeseriesList',
    {
        'station_no': QueryOption(True, True, None),
        'station_id': QueryOption(False, True, None),
        'station_name': QueryOption(True, True, None),
        'ts_id': QueryOption(False, True, None),
        'ts_path': QueryOption(True, True, None),
        'ts_name': QueryOption(True, True, None),
        'ts_shortname': QueryOption(True, True, None),
        'ts_type_id': QueryOption(False, True, None),
        'parametertype_id': QueryOption(False, True, None),
        'parametertype_name': QueryOption(True, True, None),
        'stationparameter_name': QueryOption(True, True, None),
        'stationparameter_no': QueryOption(False, True, None),
        'ts_unitname': QueryOption(True, True, None),
        'timeseriesgroup_id': QueryOption(False, False, None),
        'fulltext': QueryOption(True, False, None),
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

__gen_kiwis_method(
    KIWIS,
    'getTimeseriesValues',
    {
        'ts_id': QueryOption(False, True, None),
        'timeseriesgroup_id': QueryOption(False, True, None),
        'ts_path': QueryOption(True, True, None),
        'from': QueryOption(None, None, __parse_date),
        'to': QueryOption(None, None, __parse_date),
        'period': QueryOption(None, None, None),
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

__gen_kiwis_method(
    KIWIS,
    'getStationList',
    {
        'station_no': QueryOption(True, True, None),
        'station_id': QueryOption(False, True, None),
        'station_name': QueryOption(True, True, None),
        'catchment_no': QueryOption(False, True, None),
        'catchment_id': QueryOption(False, True, None),
        'catchment_name': QueryOption(True, True, None),
        'site_no': QueryOption(False, True, None),
        'site_id': QueryOption(False, True, None),
        'site_name': QueryOption(False, True, None),
        'stationgroup_id': QueryOption(False, False, None),
        'parametertype_id': QueryOption(False, True, None),
        'parametertype_name': QueryOption(True, True, None),
        'stationparameter_name': QueryOption(True, True, None),
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

__gen_kiwis_method(
    KIWIS,
    'getSiteList',
    {
        'site_no': QueryOption(False, True, None),
        'site_id': QueryOption(False, True, None),
        'site_name': QueryOption(False, True, None),
        'parametertype_id': QueryOption(False, True, None),
        'parametertype_name': QueryOption(True, True, None),
        'stationparameter_name': QueryOption(True, True, None),
        'bbox': QueryOption(None, None, None),
    },
    [
        'site_no',
        'site_id',
        'site_name',
        'site_latitude',
        'site_longitude',
        'site_carteasting',
        'site_cartnorthing',
        'site_type_name',
        'site_type_shortname',
        'parametertype_id',
        'parametertype_name',
        'stationparameter_name',
        'site_georefsystem',
        'custom_attributes',
    ]
)
