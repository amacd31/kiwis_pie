Kiwis Pie
===============
Python library for querying WISKI via KiWIS (KISTERS Web Interoperability Solution). See: http://www.kisters.net/wiski-modules.html

.. image:: https://raw.githubusercontent.com/amacd31/kiwis_pie/master/kiwis_and_pie.jpg

Dependencies
------------
Requires the Python libraries requests, pandas and tabulate.

Usage
-----

::

 from kiwis_pie import KIWIS
 k = KIWIS('URL_TO_KIWIS_ENDPOINT_HERE')

 k.get_station_list()

