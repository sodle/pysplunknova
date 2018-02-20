# ~*~ coding: utf-8 ~*~

"""
splunknova.client
~~~~~~~~~~~~~~~~~

This module implements the Splunk Nova client
"""

import requests
from six.moves.urllib.parse import urljoin, urlencode
from six import iteritems


NOVA_BASE_URL = 'https://api.splunknova.com/'


def handle_http_error(e):
    error_text = '{} {} - {}'.format(e.response.status_code, e.response.reason, e.response.text)
    if e.response.status_code < 500:
        raise ValueError(error_text)
    else:
        raise RuntimeError(error_text)


class Client(object):
    _events_client = None
    _metrics_client = None

    def __init__(self, client_id, client_secret, version='1'):
        """Client object for interfacing with Splunk Nova's :class:`events <EventsClient>` and :class:`metrics <MetricsClient>` APIs

        :param client_id: Splunk Nova Client ID
        :param client_secret: Splunk Nova Client Secret
        :param version: (optional, default 1) Splunk Nova API Version
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.version = version

    @property
    def _base_url(self):
        return urljoin(NOVA_BASE_URL, 'v{}/'.format(self.version))

    @property
    def events(self):
        if self._events_client is None:
            self._events_client = EventsClient(self.client_id, self.client_secret, self._base_url)
        return self._events_client

    @property
    def metrics(self):
        if self._metrics_client is None:
            self._metrics_client = ''
        return self._metrics_client


class EventsClient(object):
    def __init__(self, client_id, client_secret, base_url):
        """Client object for Splunk Nova's events API

        :param client_id: Splunk Nova Client ID
        :param client_secret: Splunk Nova Client Secret
        :param base_url: Splunk Nova API base URL
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url

    @property
    def _ingest_url(self):
        return urljoin(self.base_url, 'events')

    def ingest(self, events):
        """Send JSON events to Project Nova

        Nova requires each event to have "entity" and "source" properties. Optional fields include "time", along with
        the properties that define your event.

        See http://petstore.swagger.io/?url=https%3A%2F%2Fapi.splunknova.com%2Fswagger.json#/Ingest/events

        :param events: List of events as dicts
        :return: dict response from Nova request
        :rtype: dict
        """
        try:
            r = requests.post(self._ingest_url, json=events, auth=(self.client_id, self.client_secret))
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            handle_http_error(e)

    @property
    def _search_url(self):
        return urljoin(self.base_url, 'events')

    def search(self, terms, earliest=None, latest=None):
        """Prepare a search, in the form of an `EventSearch <EventSearch>` object, to search events.

        :param terms: Space-separated Splunk search terms
        :param earliest: (optional) Splunk timespec (e.g. "-7d", "-4h@h", etc.)
        :param latest: (optional) Splunk timespec
        :return: The prepared search object
        :rtype: EventSearch
        """
        return EventSearch(self._search_url, terms, self.client_id, self.client_secret, earliest, latest)


class EventSearch(object):
    transforms = []

    def __init__(self, base_url, search, client_id, client_secret, earliest=None, latest=None):
        """An interface for searching events, inspired by Django's QuerySets.

        This class is returned by the `search <Client.search>` method of `Client <Client>` objects, so you'll never need to
        instantiate it yourself.

        Basic searching - get all events:
        >>> client = Client('id', 'secret')
        >>> client.events.search('*').events()
        Returns a list of matching events.

        Stats or Timechart commands:
        >>> client.events.search('source=webserver').timechart('count')
        >>> client.events.search('source=webserver').stats('count by clientip')
        Returns aggregated statistics

        Eval commands can be chained to cleanly calculate multiple fields
        >>> client.events.search('entity=nas').eval('gb', 'kb / 1024 / 1024').eval('path', 'dirname + filename').events()

        :param base_url:
        :param search:
        :param client_id:
        :param client_secret:
        :param earliest:
        :param latest:
        """
        self.base_url = base_url
        self.search = search
        self.earliest = earliest
        self.latest = latest
        self.client_id = client_id
        self.client_secret = client_secret

    def eval(self, field, transform):
        """Calculate a field from the values of others. Can be chained to eval multiple fields like so:

        >>> client = Client('id', 'secret')
        >>> client.events.search('entity=nas').eval('gb', 'kb / 1024 / 1024').eval('path', 'dirname + filename').events()

        :param field: Name of field to calculate
        :param transform: Splunk eval string to calculate the field
        :return: The search object, in order to allow chaining
        :rtype: EventSearch
        """
        self.transforms.append('{}={}'.format(field, transform))
        return self

    def _encode_transforms(self):
        transforms_str = ' '.join(['eval'] + self.transforms)
        return transforms_str

    def _search(self, index=0, count=10, stats_string=None, timechart_string=None):
        time_string = ''
        if self.earliest is not None:
            time_string += 'earliest_time={} '.format(self.earliest)
        if self.latest is not None:
            time_string += 'latest_time={} '.format(self.latest)
        search = {
            'keywords': time_string + self.search,
            'index': index,
            'count': count
        }
        if len(self.transforms) > 0:
            search['transform'] = self._encode_transforms()
        if stats_string is not None:
            search['report'] = 'stats ' + stats_string
        elif timechart_string is not None:
            search['report'] = 'timechart ' + timechart_string
        query = urlencode(search)
        uri = '{}?{}'.format(self.base_url, query)
        try:
            r = requests.get(uri, auth=(self.client_id, self.client_secret))
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            handle_http_error(e)

    def events(self, index=0, count=10):
        """Return a list of the events matched by the search

        :param index: Offset of first event to return (default 0)
        :param count: Number of events to return (default 10, may be limited by Splunk Nova server)
        :return: List of matching events
        :rtype: list
        """
        return self._search(index=index, count=count)['events']

    def iter_events(self):
        """Generator equivalent of the `events <EventSearch.events>` function, so that you don't have
        to manually re-request subsequent pages

        :return: iterator over all events matched by the search
        """
        i = 0
        events = self.events(index=i, count=10)
        while len(events) > 0:
            for event in events:
                yield event
            i += 10
            events = self.events(index=i, count=10)

    def stats(self, stats_string):
        """Aggregate search results on a Splunk stats command

        :param stats_string: Splunk stats command to run
        :return: dict with stat results
        :rtype: dict
        """
        return self._search(stats_string=stats_string)['events']

    def timechart(self, timechart_string):
        """Aggregate search results on a Splunk timechart command

        :param timechart_string: Splunk timechart command to run
        :return: dict with stat results
        :rtype: dict
        """
        return self._search(timechart_string=timechart_string)['events']


class MetricsClient(object):
    def __init__(self, client_id, client_secret, base_url):
        """Client object for Splunk Nova's metrics API

        :param client_id: Splunk Nova Client ID
        :param client_secret: Splunk Nova Client Secret
        :param base_url: Splunk Nova API base URL
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url

    @property
    def _ingest_url(self):
        return urljoin(self.base_url, 'metrics')

    def _ingest(self, metrics, schema='collectd'):
        url = '{}?type={}'.format(self._ingest_url, schema)
        try:
            r = requests.post(url, json=metrics, auth=(self.client_id, self.client_secret))
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            handle_http_error(e)

    # def ingest_collectd(self, metrics):
    #     """Ingest metrics using the collectd schema
    #
    #     :param metrics: JSON object containing collectd metrics
    #     :return: dict response from Nova request
    #     :rtype: dict
    #     """
    #     return self._ingest(metrics)

    def ingest_custom(self, metrics):
        """Ingest metrics using a custom schema

        See http://petstore.swagger.io/?url=https%3A%2F%2Fapi.splunknova.com%2Fswagger.json#/Ingest/post_metrics

        :param metrics: JSON object containing collectd metrics
        :return: dict response from Nova request
        :rtype: dict
        """
        return self._ingest(metrics, schema='custom')

    @property
    def _describe_url(self):
        return urljoin(self.base_url, 'metrics')

    def describe(self):
        """List available metrics

        :return: List of available metrics
        :rtype: list
        """
        try:
            r = requests.get(self._describe_url)
            r.raise_for_status()
            return r.json()['metrics']
        except requests.HTTPError as e:
            handle_http_error(e)
        except KeyError:
            raise RuntimeError('Splunk Nova returned an invalid response.')

    @property
    def _describe_metric_url(self):
        return urljoin(self.base_url, 'metrics/')

    def describe_metric(self, name):
        """List available metrics and aggregation functions for a metric

        :param name: Name of metric to query
        :return: Tuple of two lists - available aggregations and available dimensions
        :rtype: tuple
        """
        url = urljoin(self._describe_metric_url, name)
        try:
            r = requests.get(url)
            r.raise_for_status()
            r_json = r.json()
            return r_json['aggregations'], r_json['dimensions']
        except requests.HTTPError as e:
            handle_http_error(e)
        except KeyError:
            raise RuntimeError('Splunk Nova returned an invalid response.')
