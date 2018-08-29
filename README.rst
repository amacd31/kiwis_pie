Kiwis Pie
===============
Python library for querying WISKI via KiWIS (KISTERS Web Interoperability Solution). See: http://www.kisters.net/NA/products/wiski/options/web-services/

.. image:: https://raw.githubusercontent.com/amacd31/kiwis_pie/master/kiwis_and_pie.jpg

Dependencies
------------
Requires the Python libraries requests, pandas and tabulate.

Installation
------------

Install from PyPI:

::

 pip install kiwis-pie

or install directly from github:

::

 pip install git+https://github.com/amacd31/kiwis_pie.git

Usage
-----
Example fetching some data from the KiWIS service that backs: http://kna.kisters.net/sjr/kiwidgets/tests/SanJoaquinRiver/

::

 from datetime import date
 from kiwis_pie import KIWIS
 k = KIWIS('http://kna.kisters.net/grassland/KiWIS')

 # Get station ID for 'SAN JOAQUIN RIVER NEAR PATTERSON'
 station_id = k.get_station_list(station_name = 'SAN JOAQUIN RIVER NEAR PATTERSON').station_id.values[0]

 # Get timeseries ID for 3-Hourly streamflow (Q) at SAN JOAQUIN RIVER NEAR PATTERSON
 ts_id = k.get_timeseries_list(station_id = station_id, parametertype_name = 'Q', ts_name = '3-Hourly').ts_id.values[0]

 # Read one day of 3-Hourly flow data for SAN JOAQUIN RIVER NEAR PATTERSON
 k.get_timeseries_values(ts_id = ts_id, to = date(2016,1,1), **{'from': date(2016,1,1)})

Example using the KiWIS service that backs the Australian Bureau of Meteorology's Water Data Online service: http://www.bom.gov.au/waterdata/

::

 from datetime import date
 from kiwis_pie import KIWIS
 k = KIWIS('http://www.bom.gov.au/waterdata/services')

 # Get station ID for 'Cotter River at Gingera'
 station_id = k.get_station_list(station_name = 'Cotter R. at Gingera').station_id.values[0]

 # Get timeseries ID for daily mean streamflow (Q) at Cotter River at Gingera
 ts_id = k.get_timeseries_list(station_id = station_id, ts_name = 'DMQaQc.Merged.DailyMean.24HR', parametertype_name = 'Water Course Discharge').ts_id.values[0]

 # Read 31 days of daily water course discharge data for Cotter River at Gingera
 k.get_timeseries_values(ts_id = ts_id, to = date(2016,1,31), **{'from': date(2016,1,1)})

 # Optionally use the `keep_tz` option to return in local timezone instead of UTC
 k.get_timeseries_values(ts_id = ts_id, to = date(2016,1,31), **{'from': date(2016,1,1)}, keep_tz=True)

Documentation
-------------
The methods on the KIWIS class all have docstrings detailing the keyword arguments they take.
Rendered documentation is available on Read the Docs: http://kiwis-pie.readthedocs.io/en/latest/
