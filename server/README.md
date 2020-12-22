Tide Clock: Server-side code
=====

This generates images for the tide clock micropython client.
It is also starting to graph the data back from the client with RRDtool.

Overview
--------

This fetches tide data from the UK Hydrographic Office and weather information from the Met Office.
It uses this to create an image for a client embedded board to download and display.
The tide data is also parsed to work out when to tell the client board to wake up next for more data.

Data is kept in XML as some terrible sort of database.
Additionally some is exported to JSON for the client to parse with minimal overhead.

Requirements
------------

```
apt install librrd-dev python3-pip
pip3 install --user -r requirements.txt
```

Design
------

TODO

TODO
----

* Looks like the UKHO is being replaced, where's their data format going?
* MetOffice say they're changing their data format too, but have delayed until 2019 or something
