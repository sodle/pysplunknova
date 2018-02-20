# pysplunknova
Python Client for Splunk Project Nova

Download from [PyPi](https://pypi.python.org/pypi/splunknova)

## The Client object
```python
from splunknova import Client
c = Client('client_id', 'client_secret')
```

## Send events to Splunk Nova
```python
c.events.ingest([
    {
        'source': 'webserver',
        'entity': 'mysite.com',
        'clientip': '123.32.34.64',
        'bytes': 45
    },
    # ...
])
```

## Search events in Splunk Nova
### Raw events
```python
# Get a page of events
c.events.search('*').events(index=0, count=10)

# Iterate over all events returned
for evt in c.events.search('*').iter_events():
    print(evt)
```
### Stats and timecharts
```python
c.events.search('source=webserver').stats('count by clientip')

c.events.search('source=webserver').timechart('sum(bytes)')
```
### Calculate fields
```python
c.events.search('source=webserver').eval('kb', 'bytes / 1024').stats('sum(kb)')

# Eval statements can be chained, à la Django QuerySets
c.events.search('source=triangles').eval('perimeter', 'side1 + side2 + side3').eval('longest_side', 'max(side1, side2, side3)')
```

## Metrics
TODO: Test and document metrics features
