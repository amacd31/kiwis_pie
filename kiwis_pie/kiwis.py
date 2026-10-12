import collections
try:
    from collections.abc import Iterable
except ImportError:
    from collections import Iterable

QueryOption = collections.namedtuple('QueryOption', ['wildcard', 'list', 'parser'])

import pandas as pd
import pytz
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
    """
        Exception for when the KiWIS service responds with an error.
    """
    pass

class NoDataError(Exception):
    """
        Exception for when there was no data returned by the KiWIS service.
    """
    pass

class KIWIS(object):
    """
        Provides access to the KiWIS API at a specified end point.

        :param server_url: The URL to the KiWIS server.
        :type server_url: string
        :param strict_mode: Perform validation on query options passed as
            kwargs and the return_fields list if True. Otherwise pass
            through to the KiWIS API which may result in a 500 error if the
            query option/return field isn't valid. Default: True
        :type strict_mode: boolean
        :param verify_ssl: (optional) Passed through to
            [requests](https://requests.readthedocs.io/en/latest/api/#requests.request).
            Either a boolean, in which case it controls whether we verify the
            server’s TLS certificate, or a string, in which case it must be a
            path to a CA bundle to use. Defaults to True.
        :type verify_ssl: boolean | str
        :param headers: HTTP headers to pass along with the `GET` request to the KiWIS server.
        :type headers: dict[str, Any]
    """

    __method_args = {}
    __return_args = {}

    def __init__(self, server_url, strict_mode=True, verify_ssl=True, headers=None):
        self.server_url = server_url
        self.__default_args = {
            'service': 'kisters',
            'type': 'QueryServices',
            'format': 'json',
        }

        self.strict_mode = strict_mode
        self.verify_ssl = verify_ssl
        self.headers = headers

def __parse_date(input_dt):
    return pd.to_datetime(input_dt).strftime('%Y-%m-%d')

def __gen_kiwis_method(cls, method_name, available_query_options, available_return_fields):

    start_snake = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', method_name)
    snake_name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', start_snake).lower()

    if 'format' not in available_query_options:
        available_query_options['format'] = QueryOption(False, False, None)

    cls._KIWIS__method_args[method_name] = available_query_options
    cls._KIWIS__return_args[method_name] = available_return_fields
    def kiwis_method(self, return_fields = None, keep_tz=False, verify = True, **kwargs):

        if self.strict_mode:
            for query_key in kwargs.keys():
                if query_key not in self._KIWIS__method_args[method_name].keys():
                    raise ValueError(query_key)

                if (self._KIWIS__method_args[method_name][query_key].list and
                        isinstance(kwargs[query_key], Iterable) and
                        not isinstance(kwargs[query_key], basestring)):
                    kwargs[query_key] = ','.join(kwargs[query_key])

                if self._KIWIS__method_args[method_name][query_key].parser is not None:
                    kwargs[query_key] = self._KIWIS__method_args[method_name][query_key].parser(kwargs[query_key])

            if return_fields is not None:
                for return_key in return_fields:
                    if return_key not in self._KIWIS__return_args[method_name]:
                        raise ValueError(return_key)

        params = self._KIWIS__default_args.copy()
        if method_name in ['getGraph', 'getStationGraph']:
            params['format'] = 'png'
            if 'format' in kwargs and kwargs['format'].lower() not in ['png', 'jpg']:
                raise ValueError("Format for {0} must be 'png' or 'jpg', not '{1}'".format(method_name, kwargs['format']))
        params.update(kwargs)
        params['request'] = method_name
        if return_fields is not None:
            params['returnfields'] = ','.join(return_fields)

        r = requests.get(self.server_url, params = params, verify = self.verify_ssl, headers=self.headers)
        logger.debug(r.url)
        logger.debug(r.status_code)
        r.raise_for_status() #raise error if service returns an error, i.e. 404, 500 etc.

        if method_name in ['getGraph', 'getStationGraph']:
            return r.content

        try:
            json_data = r.json()
        except ValueError:
            return r.text

        if isinstance(json_data, dict) and 'type' in json_data.keys() and json_data['type'] == 'error':
            raise KIWISError(
                'KIWIS returned an error:\n\tCode: {0}\n\tMessage: "{1}"'.format(
                    json_data.get('code'),
                    json_data.get('message')
                )
            )

        if json_data is None or json_data == "No matches." or (isinstance(json_data, list) and len(json_data) > 0 and json_data[0] == "No matches."):
            raise NoDataError()

        req_format = str(params.get('format', '')).lower()
        if req_format == 'geojson' or (isinstance(json_data, dict) and json_data.get('type') in ['FeatureCollection', 'Feature']):
            return json_data

        if method_name in [
                'getGroupList',
                'getSiteList',
                'getStationList',
                'getParameterList',
                'getParameterTypeList',
                'getCatchmentList',
                'getRiverList',
                'getStationLithology',
                'getStationCasing',
                'getTimeseriesList',
                'getTimeseriesTypeList',
                'getGraphTemplateList',
                'getReleaseStateClasses',
                'getTimeseriesChanges',
                'getTimeseriesComments',
            ]:
            if isinstance(json_data, list) and len(json_data) > 0 and isinstance(json_data[0], list):
                return pd.DataFrame(json_data[1:], columns = json_data[0])
            return json_data
        elif method_name in ['getTimeseriesValues']:
            if isinstance(json_data, list) and len(json_data) > 0 and isinstance(json_data[0], dict) and 'data' in json_data[0] and 'columns' in json_data[0]:
                df = pd.DataFrame(json_data[0]['data'], columns = json_data[0]['columns'].split(','))
                if 'Timestamp' in df.columns:
                    df.set_index('Timestamp', inplace = True)
                    if keep_tz:
                        hour_offset, minute_offset = map(int, df.index[0].split('+')[1].split(':'))
                        logger.debug('Using timezone offset %d hour(s) and %d minute(s)', hour_offset, minute_offset)
                        df.index = pd.to_datetime(df.index).tz_localize('UTC').tz_convert(pytz.FixedOffset(hour_offset*60+minute_offset))
                    else:
                        df.index = pd.to_datetime(df.index)
                return df
            return json_data
        elif method_name in [
                'getCatchmentHierarchy',
                'getStandardRemarkTypeList',
                'getRatingCurveList',
                'getTimeseriesValueLayer',
                'getColorClassifications',
                'getQualityCodes',
                'getTimeseriesReleaseStateList',
                'getTimeseriesEnsembleValues',
                'checkValueLimit',
            ]:
            return json_data
        else:
            raise NotImplementedError("Method '{0}' has no return implemented.".format(method_name))

    docstring = {}
    docstring['doc_intro'] = "Python method to query the '{0}' KiWIS method.".format(method_name)

    docstring['doc_intro'] += "\n\nKeyword arguments are those available in the 'Query field' name list below. "
    docstring['doc_intro'] += "That is the keywords match the Queryfield names used by KiWIS."

    docstring['doc_intro'] += "\n\n:param keep_tz: "
    docstring['doc_intro'] += "Set to true to prevent the series datetimes from being converted to UTC."
    docstring['doc_intro'] += " This optional argument only applies when the returned data includes data with timestamps."
    docstring['doc_intro'] += "\n:type keep_tz: boolean"

    docstring['return_fields'] = ":type return_fields: list(string)\n:param return_fields: Optional keyword argument, which is a list made up from the following available fields:\n\n * {0}.".format(',\n * '.join(available_return_fields))

    doc_map = {
        True: 'yes',
        False: 'no',
        None: 'n/a',
    }

    option_list = [['Queryfield name', r'\* as wildcard', 'accepts list']]
    for option_name, option_details in available_query_options.items():
        option_list.append(
            [
                option_name,
                doc_map[option_details.wildcard],
                doc_map[option_details.list],
            ]
        )

    docstring['query_option_table'] = ":param kwargs: Queryfield name for keyword argument. Refer to table:\n\n"
    docstring['query_option_table'] += tabulate(option_list, headers = 'firstrow', tablefmt = 'rst')

    docstring['returns'] = ":return: Pandas DataFrame with columns based on the default return from KiWIS or based on the return_fields specified.\n"
    docstring['returns'] += ":rtype: pandas.DataFrame"

    kiwis_method.__doc__ = "{doc_intro}\n\n{return_fields}\n\n{query_option_table}\n\n{returns}".format(**docstring)

    setattr(cls, snake_name, kiwis_method)

__gen_kiwis_method(
    KIWIS,
    'getGroupList',
    {
        'group_name': QueryOption(True, True, None),
        'group_type': QueryOption(False, False, None),
        'group_purpose': QueryOption(True, True, None),
        'csvdiv': QueryOption(None, None, None),
        'ca_group_returnfields': QueryOption(None, None, None),
        'addlinks': QueryOption(None, None, None),
        'includeprivate': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
    },
    [
        'group_name',
        'group_id',
        'group_type',
        'group_remark',
        'group_purpose',
        'group_private',
        'ca_group',
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getSiteList',
    {
        'site_no': QueryOption(True, True, None),
        'site_id': QueryOption(False, True, None),
        'site_uuid': QueryOption(False, True, None),
        'site_name': QueryOption(True, True, None),
        'parametertype_id': QueryOption(False, True, None),
        'parametertype_name': QueryOption(True, True, None),
        'stationparameter_name': QueryOption(True, True, None),
        'bbox': QueryOption(False, False, None),
        'csvdiv': QueryOption(None, None, None),
        'crs': QueryOption(None, None, None),
        'ca_site_returnfields': QueryOption(None, None, None),
        'custattr_returnfields': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
        'addlinks': QueryOption(None, None, None),
        'orderby': QueryOption(None, None, None),
    },
    [
        'site_no',
        'site_id',
        'site_uuid',
        'site_name',
        'site_longname',
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
        'site_area_wkt',
        'site_area_wkt_org',
        'ca_site',
        'custom_attributes',
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getStationList',
    {
        'station_no': QueryOption(True, True, None),
        'station_id': QueryOption(False, True, None),
        'station_uuid': QueryOption(False, True, None),
        'station_name': QueryOption(True, True, None),
        'catchment_no': QueryOption(False, True, None),
        'catchment_id': QueryOption(False, True, None),
        'catchment_name': QueryOption(True, True, None),
        'site_no': QueryOption(True, True, None),
        'site_id': QueryOption(False, True, None),
        'site_uuid': QueryOption(False, True, None),
        'site_name': QueryOption(True, True, None),
        'stationgroup_id': QueryOption(False, False, None),
        'parametertype_id': QueryOption(False, True, None),
        'parametertype_name': QueryOption(True, True, None),
        'parametertype_shortname': QueryOption(True, True, None),
        'stationparameter_name': QueryOption(True, True, None),
        'stationparameter_no': QueryOption(True, True, None),
        'object_type': QueryOption(True, True, None),
        'object_type_shortname': QueryOption(True, True, None),
        'bbox': QueryOption(False, False, None),
        'fulltext': QueryOption(True, False, None),
        'custattrfilter': QueryOption(True, False, None),
        'csvdiv': QueryOption(None, None, None),
        'crs': QueryOption(None, None, None),
        'ca_site_returnfields': QueryOption(None, None, None),
        'ca_sta_returnfields': QueryOption(None, None, None),
        'custattr_returnfields': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
        'flatten': QueryOption(None, None, None),
        'addlinks': QueryOption(None, None, None),
        'orderby': QueryOption(None, None, None),
    },
    [
        'station_no',
        'station_id',
        'station_uuid',
        'station_name',
        'catchment_no',
        'catchment_id',
        'catchment_name',
        'station_latitude',
        'station_longitude',
        'station_carteasting',
        'station_cartnorthing',
        'station_local_x',
        'station_local_y',
        'station_timezone',
        'station_utcoffset',
        'station_posmethod',
        'site_no',
        'site_id',
        'site_uuid',
        'site_name',
        'site_longname',
        'parametertype_id',
        'parametertype_name',
        'parametertype_shortname',
        'stationparameter_name',
        'stationparameter_no',
        'stationparameter_id',
        'parametertype_longname',
        'object_type',
        'object_type_shortname',
        'station_georefsystem',
        'station_longname',
        'station_area_wkt',
        'station_area_wkt_org',
        'river_id',
        'river_name',
        'area_id',
        'area_name',
        'ca_site',
        'ca_sta',
        'custom_attributes',
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getParameterList',
    {
        'station_no': QueryOption(False, True, None),
        'station_id': QueryOption(False, True, None),
        'station_name': QueryOption(True, True, None),
        'site_no': QueryOption(False, True, None),
        'site_id': QueryOption(False, True, None),
        'site_name': QueryOption(True, True, None),
        'stationparameter_id': QueryOption(False, True, None),
        'stationparameter_no': QueryOption(False, True, None),
        'stationparameter_name': QueryOption(True, True, None),
        'stationparameter_longname': QueryOption(True, True, None),
        'parametertype_id': QueryOption(False, True, None),
        'parametertype_name': QueryOption(True, True, None),
        'parametertype_longname': QueryOption(True, True, None),
        'parametergroup_id': QueryOption(False, False, None),
        'csvdiv': QueryOption(None, None, None),
        'ca_par_returnfields': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
        'orderby': QueryOption(None, None, None),
    },
    [
        'station_no',
        'station_id',
        'station_name',
        'site_no',
        'site_id',
        'site_name',
        'stationparameter_id',
        'stationparameter_name',
        'stationparameter_no',
        'stationparameter_longname',
        'parametertype_id',
        'parametertype_name',
        'parametertype_longname',
        'parametertype_shortunitname',
        'parametertype_unitname',
        'ca_par',
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getParameterTypeList',
    {
        'parametertype_id': QueryOption(False, True, None),
        'parametertype_name': QueryOption(True, True, None),
        'csvdiv': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
    },
    [
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getCatchmentList',
    {
        'catchment_no': QueryOption(False, True, None),
        'catchment_id': QueryOption(False, True, None),
        'catchment_name': QueryOption(True, True, None),
        'catchment_parent_id': QueryOption(False, True, None),
        'csvdiv': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
        'addlinks': QueryOption(None, None, None),
    },
    [
        'catchment_no',
        'catchment_id',
        'catchment_name',
        'catchment_parent_id',
        'catchment_size',
        'catchment_area_wkt',
        'catchment_area_wkt_org',
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getCatchmentHierarchy',
    {
        'catchment_no': QueryOption(False, False, None),
        'catchment_id': QueryOption(False, False, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
    },
    [
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getRiverList',
    {
        'river_id': QueryOption(False, True, None),
        'river_no': QueryOption(True, True, None),
        'river_name': QueryOption(True, True, None),
        'catchment_no': QueryOption(True, True, None),
        'catchment_id': QueryOption(False, True, None),
        'catchment_name': QueryOption(True, True, None),
        'region_id': QueryOption(False, True, None),
        'region_no': QueryOption(True, True, None),
        'region_name': QueryOption(True, True, None),
        'wtotype_id': QueryOption(False, True, None),
        'wtotype_name': QueryOption(True, True, None),
        'wto_altnumber': QueryOption(True, True, None),
        'csvdiv': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
    },
    [
        'river_no',
        'river_id',
        'river_name',
        'river_longname',
        'catchment_no',
        'catchment_id',
        'catchment_name',
        'region_id',
        'region_no',
        'region_name',
        'wtotype_id',
        'wtotype_name',
        'wto_altnumber',
        'wto_order',
        'wto_sequence',
        'wto_confluencedistance',
        'wto_length',
        'wto_area_wkt',
        'wto_area_wkt_org',
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getStandardRemarkTypeList',
    {
        'shortname': QueryOption(False, False, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
    },
    [
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getRatingCurveList',
    {
        'station_id': QueryOption(False, True, None),
        'stationgroup_id': QueryOption(False, False, None),
        'source': QueryOption(False, True, None),
        'target': QueryOption(False, True, None),
        'from': QueryOption(False, False, __parse_date),
        'to': QueryOption(False, False, __parse_date),
        'period': QueryOption(False, False, None),
        'name': QueryOption(False, False, None),
        'group': QueryOption(False, False, None),
        'stepsize': QueryOption(None, None, None),
        'steps': QueryOption(None, None, None),
        'includeratingtable': QueryOption(None, None, None),
        'eta': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
    },
    [
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getStationLithology',
    {
        'station_id': QueryOption(False, False, None),
        'includefillings': QueryOption(None, None, None),
        'order': QueryOption(None, None, None),
        'csvdiv': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
    },
    [
        'lithology_id',
        'color',
        'consistency',
        'depth_from',
        'depth_to',
        'pricomp_color',
        'pricomp_label',
        'pricomp_pricode',
        'pricomp_seccode',
        'pricomp_priname',
        'pricomp_secname',
        'seccomp_color',
        'seccomp_label',
        'seccomp_pricode',
        'seccomp_seccode',
        'seccomp_priname',
        'seccomp_secname',
        'remark',
        'all',
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getStationCasing',
    {
        'station_id': QueryOption(False, False, None),
        'order': QueryOption(None, None, None),
        'csvdiv': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
    },
    [
        'casing_id',
        'casing_material',
        'casing_type',
        'int_diameter',
        'int_diameter_unit',
        'casing_from',
        'casing_to',
        'casing_fromto_unit',
        'casing_depth',
        'casing_depth_unit',
        'perf_interval',
        'all',
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getGroupList',
    {
        'group_name': QueryOption(True, True, None),
        'group_type': QueryOption(False, False, None),
        'group_purpose': QueryOption(True, True, None),
        'csvdiv': QueryOption(None, None, None),
        'ca_group_returnfields': QueryOption(None, None, None),
        'addlinks': QueryOption(None, None, None),
        'includeprivate': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
    },
    [
        'group_name',
        'group_id',
        'group_type',
        'group_remark',
        'group_purpose',
        'group_private',
        'ca_group',
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getSiteList',
    {
        'site_no': QueryOption(True, True, None),
        'site_id': QueryOption(False, True, None),
        'site_uuid': QueryOption(False, True, None),
        'site_name': QueryOption(True, True, None),
        'parametertype_id': QueryOption(False, True, None),
        'parametertype_name': QueryOption(True, True, None),
        'stationparameter_name': QueryOption(True, True, None),
        'bbox': QueryOption(False, False, None),
        'csvdiv': QueryOption(None, None, None),
        'crs': QueryOption(None, None, None),
        'ca_site_returnfields': QueryOption(None, None, None),
        'custattr_returnfields': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
        'addlinks': QueryOption(None, None, None),
        'orderby': QueryOption(None, None, None),
    },
    [
        'site_no',
        'site_id',
        'site_uuid',
        'site_name',
        'site_longname',
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
        'site_area_wkt',
        'site_area_wkt_org',
        'ca_site',
        'custom_attributes',
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getStationList',
    {
        'station_no': QueryOption(True, True, None),
        'station_id': QueryOption(False, True, None),
        'station_uuid': QueryOption(False, True, None),
        'station_name': QueryOption(True, True, None),
        'catchment_no': QueryOption(False, True, None),
        'catchment_id': QueryOption(False, True, None),
        'catchment_name': QueryOption(True, True, None),
        'site_no': QueryOption(True, True, None),
        'site_id': QueryOption(False, True, None),
        'site_uuid': QueryOption(False, True, None),
        'site_name': QueryOption(True, True, None),
        'stationgroup_id': QueryOption(False, False, None),
        'parametertype_id': QueryOption(False, True, None),
        'parametertype_name': QueryOption(True, True, None),
        'parametertype_shortname': QueryOption(True, True, None),
        'stationparameter_name': QueryOption(True, True, None),
        'stationparameter_no': QueryOption(True, True, None),
        'object_type': QueryOption(True, True, None),
        'object_type_shortname': QueryOption(True, True, None),
        'bbox': QueryOption(False, False, None),
        'fulltext': QueryOption(True, False, None),
        'custattrfilter': QueryOption(True, False, None),
        'csvdiv': QueryOption(None, None, None),
        'crs': QueryOption(None, None, None),
        'ca_site_returnfields': QueryOption(None, None, None),
        'ca_sta_returnfields': QueryOption(None, None, None),
        'custattr_returnfields': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
        'flatten': QueryOption(None, None, None),
        'addlinks': QueryOption(None, None, None),
        'orderby': QueryOption(None, None, None),
    },
    [
        'station_no',
        'station_id',
        'station_uuid',
        'station_name',
        'catchment_no',
        'catchment_id',
        'catchment_name',
        'station_latitude',
        'station_longitude',
        'station_carteasting',
        'station_cartnorthing',
        'station_local_x',
        'station_local_y',
        'station_timezone',
        'station_utcoffset',
        'station_posmethod',
        'site_no',
        'site_id',
        'site_uuid',
        'site_name',
        'site_longname',
        'parametertype_id',
        'parametertype_name',
        'parametertype_shortname',
        'stationparameter_name',
        'stationparameter_no',
        'stationparameter_id',
        'parametertype_longname',
        'object_type',
        'object_type_shortname',
        'station_georefsystem',
        'station_longname',
        'station_area_wkt',
        'station_area_wkt_org',
        'river_id',
        'river_name',
        'area_id',
        'area_name',
        'ca_site',
        'ca_sta',
        'custom_attributes',
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getParameterList',
    {
        'station_no': QueryOption(False, True, None),
        'station_id': QueryOption(False, True, None),
        'station_name': QueryOption(True, True, None),
        'site_no': QueryOption(False, True, None),
        'site_id': QueryOption(False, True, None),
        'site_name': QueryOption(True, True, None),
        'stationparameter_id': QueryOption(False, True, None),
        'stationparameter_no': QueryOption(False, True, None),
        'stationparameter_name': QueryOption(True, True, None),
        'stationparameter_longname': QueryOption(True, True, None),
        'parametertype_id': QueryOption(False, True, None),
        'parametertype_name': QueryOption(True, True, None),
        'parametertype_longname': QueryOption(True, True, None),
        'parametergroup_id': QueryOption(False, False, None),
        'csvdiv': QueryOption(None, None, None),
        'ca_par_returnfields': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
        'orderby': QueryOption(None, None, None),
    },
    [
        'station_no',
        'station_id',
        'station_name',
        'site_no',
        'site_id',
        'site_name',
        'stationparameter_id',
        'stationparameter_name',
        'stationparameter_no',
        'stationparameter_longname',
        'parametertype_id',
        'parametertype_name',
        'parametertype_longname',
        'parametertype_shortunitname',
        'parametertype_unitname',
        'ca_par',
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getParameterTypeList',
    {
        'parametertype_id': QueryOption(False, True, None),
        'parametertype_name': QueryOption(True, True, None),
        'csvdiv': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
    },
    [
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getCatchmentList',
    {
        'catchment_no': QueryOption(False, True, None),
        'catchment_id': QueryOption(False, True, None),
        'catchment_name': QueryOption(True, True, None),
        'catchment_parent_id': QueryOption(False, True, None),
        'csvdiv': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
        'addlinks': QueryOption(None, None, None),
    },
    [
        'catchment_no',
        'catchment_id',
        'catchment_name',
        'catchment_parent_id',
        'catchment_size',
        'catchment_area_wkt',
        'catchment_area_wkt_org',
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getCatchmentHierarchy',
    {
        'catchment_no': QueryOption(False, False, None),
        'catchment_id': QueryOption(False, False, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
    },
    [
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getRiverList',
    {
        'river_id': QueryOption(False, True, None),
        'river_no': QueryOption(True, True, None),
        'river_name': QueryOption(True, True, None),
        'catchment_no': QueryOption(True, True, None),
        'catchment_id': QueryOption(False, True, None),
        'catchment_name': QueryOption(True, True, None),
        'region_id': QueryOption(False, True, None),
        'region_no': QueryOption(True, True, None),
        'region_name': QueryOption(True, True, None),
        'wtotype_id': QueryOption(False, True, None),
        'wtotype_name': QueryOption(True, True, None),
        'wto_altnumber': QueryOption(True, True, None),
        'csvdiv': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
    },
    [
        'river_no',
        'river_id',
        'river_name',
        'river_longname',
        'catchment_no',
        'catchment_id',
        'catchment_name',
        'region_id',
        'region_no',
        'region_name',
        'wtotype_id',
        'wtotype_name',
        'wto_altnumber',
        'wto_order',
        'wto_sequence',
        'wto_confluencedistance',
        'wto_length',
        'wto_area_wkt',
        'wto_area_wkt_org',
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getStandardRemarkTypeList',
    {
        'shortname': QueryOption(False, False, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
    },
    [
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getRatingCurveList',
    {
        'station_id': QueryOption(False, True, None),
        'stationgroup_id': QueryOption(False, False, None),
        'source': QueryOption(False, True, None),
        'target': QueryOption(False, True, None),
        'from': QueryOption(False, False, __parse_date),
        'to': QueryOption(False, False, __parse_date),
        'period': QueryOption(False, False, None),
        'name': QueryOption(False, False, None),
        'group': QueryOption(False, False, None),
        'stepsize': QueryOption(None, None, None),
        'steps': QueryOption(None, None, None),
        'includeratingtable': QueryOption(None, None, None),
        'eta': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
    },
    [
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getStationLithology',
    {
        'station_id': QueryOption(False, False, None),
        'includefillings': QueryOption(None, None, None),
        'order': QueryOption(None, None, None),
        'csvdiv': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
    },
    [
        'lithology_id',
        'color',
        'consistency',
        'depth_from',
        'depth_to',
        'pricomp_color',
        'pricomp_label',
        'pricomp_pricode',
        'pricomp_seccode',
        'pricomp_priname',
        'pricomp_secname',
        'seccomp_color',
        'seccomp_label',
        'seccomp_pricode',
        'seccomp_seccode',
        'seccomp_priname',
        'seccomp_secname',
        'remark',
        'all',
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getStationCasing',
    {
        'station_id': QueryOption(False, False, None),
        'order': QueryOption(None, None, None),
        'csvdiv': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
    },
    [
        'casing_id',
        'casing_material',
        'casing_type',
        'int_diameter',
        'int_diameter_unit',
        'casing_from',
        'casing_to',
        'casing_fromto_unit',
        'casing_depth',
        'casing_depth_unit',
        'perf_interval',
        'all',
    ]
)

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
        'timeseriesgroup_id': QueryOption(False, False, None),
        'stationgroup_id': QueryOption(False, False, None),
        'parametergroup_id': QueryOption(False, False, None),
        'fulltext': QueryOption(True, False, None),
        'csvdiv': QueryOption(None, None, None),
        'dateformat': QueryOption(None, None, None),
        'timezone': QueryOption(None, None, None),
        'ca_site_returnfields': QueryOption(None, None, None),
        'ca_sta_returnfields': QueryOption(None, None, None),
        'ca_par_returnfields': QueryOption(None, None, None),
        'ca_ts_returnfields': QueryOption(None, None, None),
        'addlinks': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
        'orderby': QueryOption(None, None, None),
    },
    [
        'station_no',
        'station_id',
        'station_name',
        'station_latitude',
        'station_longitude',
        'station_carteasting',
        'station_cartnorthing',
        'station_local_x',
        'station_local_y',
        'station_georefsystem',
        'station_longname',
        'ts_id',
        'ts_name',
        'ts_shortname',
        'ts_path',
        'ts_type_id',
        'ts_type_name',
        'parametertype_id',
        'parametertype_name',
        'stationparameter_name',
        'stationparameter_no',
        'stationparameter_longname',
        'ts_unitname',
        'ts_unitsymbol',
        'ts_unitname_abs',
        'ts_unitsymbol_abs',
        'site_no',
        'site_id',
        'site_name',
        'catchment_no',
        'catchment_id',
        'catchment_name',
        'coverage',
        'ts_density',
        'ts_exchange',
        'ts_spacing',
        'datacart',
        'ca_site',
        'ca_sta',
        'ca_par',
        'ca_ts',
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getTimeseriesTypeList',
    {
        'ts_type_id': QueryOption(False, True, None),
        'ts_shortname': QueryOption(True, True, None),
        'ts_name': QueryOption(True, True, None),
        'csvdiv': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
    },
    [
        'ts_type_id',
        'ts_type_name',
        'ts_name',
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getTimeseriesValues',
    {
        'ts_id': QueryOption(False, True, None),
        'ts_path': QueryOption(True, True, None),
        'timeseriesgroup_id': QueryOption(False, True, None),
        'from': QueryOption(False, False, __parse_date),
        'to': QueryOption(False, False, __parse_date),
        'period': QueryOption(False, False, None),
        'futureperiod': QueryOption(False, False, None),
        'changedsince': QueryOption(False, False, __parse_date),
        'csvdiv': QueryOption(None, None, None),
        'metadata': QueryOption(None, None, None),
        'md_returnfields': QueryOption(None, None, None),
        'ca_site_returnfields': QueryOption(None, None, None),
        'ca_sta_returnfields': QueryOption(None, None, None),
        'ca_par_returnfields': QueryOption(None, None, None),
        'ca_ts_returnfields': QueryOption(None, None, None),
        'custattr_md_returnfields': QueryOption(None, None, None),
        'dateformat': QueryOption(None, None, None),
        'timezone': QueryOption(None, None, None),
        'crs': QueryOption(None, None, None),
        'valueorder': QueryOption(None, None, None),
        'useprecision': QueryOption(None, None, None),
        'valuelocale': QueryOption(None, None, None),
        'valuesasstring': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
        'forcecontentdisposition': QueryOption(None, None, None),
        'getensembletimestampsonly': QueryOption(None, None, None),
        'sincefirstchange': QueryOption(None, None, None),
        'locationascolumns': QueryOption(None, None, None),
        'minquality': QueryOption(None, None, None),
        'maxquality': QueryOption(None, None, None),
        'qualitylist': QueryOption(None, None, None),
        'gapdetection': QueryOption(None, None, None),
        'enhanceborders': QueryOption(None, None, None),
        'commentlanguage': QueryOption(None, None, None),
        'excelsheetlabel': QueryOption(None, None, None),
        'usewiskiqualityformissings': QueryOption(None, None, None),
        'transformation': QueryOption(None, None, None),
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
        'Primary Value',
        'PV Interpolation Type',
        'PV Quality Code',
        'ca_sta',
        'ca_site',
        'Remark',
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getTimeseriesValueLayer',
    {
        'ts_id': QueryOption(False, True, None),
        'ts_path': QueryOption(True, True, None),
        'timeseriesgroup_id': QueryOption(False, True, None),
        'bbox': QueryOption(False, False, None),
        'stationparameter_no': QueryOption(True, True, None),
        'ts_shortname': QueryOption(True, True, None),
        'date': QueryOption(False, False, __parse_date),
        'valuecolumn': QueryOption(False, False, None),
        'site_no': QueryOption(False, True, None),
        'csvdiv': QueryOption(None, None, None),
        'metadata': QueryOption(None, None, None),
        'md_returnfields': QueryOption(None, None, None),
        'ca_site_returnfields': QueryOption(None, None, None),
        'ca_sta_returnfields': QueryOption(None, None, None),
        'ca_par_returnfields': QueryOption(None, None, None),
        'ca_ts_returnfields': QueryOption(None, None, None),
        'custattr_md_returnfields': QueryOption(None, None, None),
        'dateformat': QueryOption(None, None, None),
        'timezone': QueryOption(None, None, None),
        'crs': QueryOption(None, None, None),
        'orderby': QueryOption(None, None, None),
        'orderdir': QueryOption(None, None, None),
        'invalidperiod': QueryOption(None, None, None),
        'invalidvalue': QueryOption(None, None, None),
        'showemptytimeseries': QueryOption(None, None, None),
        'hidetsid': QueryOption(None, None, None),
        'useprecision': QueryOption(None, None, None),
        'valuelocale': QueryOption(None, None, None),
        'valuesasstring': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
    },
    [
        'ts_id',
        'timestamp',
        'ts_value',
        'req_timestamp',
        'occ_timestamp',
        'ts_intpol',
        'q_code',
        'q_code_name',
        'q_code_desc',
        'q_code_color',
        'occ_count',
        'sta_location',
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getGraphTemplateList',
    {
        'templategroup': QueryOption(False, True, None),
        'csvdiv': QueryOption(None, None, None),
    },
    [
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getGraph',
    {
        'ts_id': QueryOption(False, True, None),
        'ext_ts_id': QueryOption(False, True, None),
        'ts_path': QueryOption(False, True, None),
        'ext_ts_path': QueryOption(False, True, None),
        'from': QueryOption(False, False, __parse_date),
        'to': QueryOption(False, False, __parse_date),
        'period': QueryOption(False, False, None),
        'futureperiod': QueryOption(False, False, None),
        'width': QueryOption(False, False, None),
        'height': QueryOption(False, False, None),
        'template': QueryOption(False, False, None),
        'templategroup': QueryOption(False, False, None),
        'showgroups': QueryOption(False, True, None),
        'hidelegend': QueryOption(False, False, None),
        'overlayinterval': QueryOption(False, False, None),
        'overlayslices': QueryOption(False, True, None),
        'renderer': QueryOption(None, None, None),
        'timezone': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
        'forcecontentdisposition': QueryOption(None, None, None),
        'format': QueryOption(False, False, None),
    },
    [
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getStationGraph',
    {
        'station_id': QueryOption(False, True, None),
        'from': QueryOption(False, False, __parse_date),
        'to': QueryOption(False, False, __parse_date),
        'period': QueryOption(False, False, None),
        'futureperiod': QueryOption(False, False, None),
        'width': QueryOption(False, False, None),
        'height': QueryOption(False, False, None),
        'template': QueryOption(False, False, None),
        'templategroup': QueryOption(False, False, None),
        'showgroups': QueryOption(False, True, None),
        'hidelegend': QueryOption(False, False, None),
        'overlayinterval': QueryOption(False, False, None),
        'overlayslices': QueryOption(False, True, None),
        'timezone': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
        'forcecontentdisposition': QueryOption(None, None, None),
        'format': QueryOption(False, False, None),
    },
    [
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getColorClassifications',
    {
        'name': QueryOption(True, False, None),
        'parameterType': QueryOption(True, False, None),
        'classificationType': QueryOption(True, False, None),
    },
    [
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getQualityCodes',
    {
    },
    [
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getReleaseStateClasses',
    {
    },
    [
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getTimeseriesReleaseStateList',
    {
        'ts_id': QueryOption(False, True, None),
        'ts_path': QueryOption(False, True, None),
        'from': QueryOption(False, False, __parse_date),
        'to': QueryOption(False, False, __parse_date),
        'period': QueryOption(False, False, None),
        'futureperiod': QueryOption(False, False, None),
        'dateformat': QueryOption(None, None, None),
        'timezone': QueryOption(None, None, None),
    },
    [
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getTimeseriesEnsembleValues',
    {
        'ts_id': QueryOption(False, True, None),
        'ts_path': QueryOption(True, True, None),
        'timeseriesgroup_id': QueryOption(False, True, None),
        'from': QueryOption(False, False, __parse_date),
        'to': QueryOption(False, False, __parse_date),
        'period': QueryOption(False, False, None),
        'futureperiod': QueryOption(False, False, None),
        'ensembledispatchinfo': QueryOption(False, False, None),
        'dateformat': QueryOption(None, None, None),
        'timezone': QueryOption(None, None, None),
        'useprecision': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
    },
    [
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getTimeseriesChanges',
    {
        'ts_id': QueryOption(False, False, None),
        'ts_path': QueryOption(False, False, None),
        'changedsince': QueryOption(False, False, __parse_date),
        'dateformat': QueryOption(None, None, None),
        'timezone': QueryOption(None, None, None),
        'optimizechanges': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
    },
    [
    ]
)

__gen_kiwis_method(
    KIWIS,
    'getTimeseriesComments',
    {
        'ts_id': QueryOption(False, True, None),
        'ts_path': QueryOption(True, True, None),
        'comment_type': QueryOption(False, True, None),
        'from': QueryOption(False, False, __parse_date),
        'to': QueryOption(False, False, __parse_date),
        'period': QueryOption(False, False, None),
        'futureperiod': QueryOption(False, False, None),
        'csvdiv': QueryOption(None, None, None),
        'dateformat': QueryOption(None, None, None),
        'timezone': QueryOption(None, None, None),
        'downloadaszip': QueryOption(None, None, None),
        'downloadfilename': QueryOption(None, None, None),
        'commentlanguage': QueryOption(None, None, None),
    },
    [
        'ts_id',
        'from',
        'to',
        'comment_type',
        'std_remark_shortname',
        'std_remark_text',
        'comment',
    ]
)

__gen_kiwis_method(
    KIWIS,
    'checkValueLimit',
    {
        'ts_id': QueryOption(False, True, None),
        'ts_path': QueryOption(True, True, None),
        'timeseriesgroup_id': QueryOption(False, True, None),
        'from': QueryOption(False, False, __parse_date),
        'to': QueryOption(False, False, __parse_date),
        'period': QueryOption(False, False, None),
        'futureperiod': QueryOption(False, False, None),
    },
    [
    ]
)
