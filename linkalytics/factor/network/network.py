import itertools
import collections

from elasticsearch import Elasticsearch
from flask import jsonify

import networkx as nx

from ... environment import cfg
from ... utils import memoize

class MetaConfigInjection(type):
    """
    This metaclass implements the Singleton design pattern in order
    to perform dependency injection of pre-configured
    elasticsearch instances bound  as attributes to cls.instance
    """
    instance = None
    def __call__(cls, *args, **kwargs):

        hosts = cfg['cdr_elastic_search']['hosts']
        index = cfg['cdr_elastic_search']['index']

        if not cls.instance:
            cls.instance = super().__call__(*args, **kwargs)
            cls.es       = Elasticsearch([hosts + index],
                                         port=443,
                                         use_ssl=False,
                                         verify_certs=False,
                                         timeout=160,
            )
        return cls.instance

class propertycache:
    """
    Custom property decorator which maintiains
    intermediate results.
    """
    def __init__(self, func):
        self.func = func
        self.name = func.__name__

    def __get__(self, obj, type=None):
        result = self.func(obj)
        self.cachevalue(obj, result)
        return result

    def cachevalue(self, obj, value):
        setattr(obj, self.name, value)

class Node:
    """
    Custom parametric data type.

    Has more consistent hashing behavior than integers
    and strings when used as keys to dictionaries.

    Example
    -------
    >>> hash(Node(500)) == hash(Node('500'))
    True

    >>> hash(500) == hash('500')
    False
    """
    def __init__(self, _id):
        self._id = _id

    def __repr__(self):
        return '<V|{id}|>'.format(
            clsname=self.__class__.__name__,
            id=self.id)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return self.id == other.id

    @property
    def id(self):
        return str(self._id)

class Messenger(metaclass=MetaConfigInjection):

    def __init__(self, size=500):
        """
        :param url: str
            Fully qualified url to an elasticsearch instance
        :param size: int
            Size limit to set on elasticsearch query
        """
        self.size = size

    def __repr__(self):
        return '{clsname}("{url}", size={size})'.format(
            clsname=self.__class__.__name__,
            url='<Elasticsearch URL>',
            size=self.size,
        )

    @memoize
    def available(self, ad_id):
        """
        Get's the available factors for a particular ad

        :param ad_id: str
            Unique ad identifier

        :return: factors
        :rtype : list
        """
        accumulator = lambda x,y: x|y
        payload = {
                "size": self.size,
                "query": {
                    "match_phrase": {
                        "_id": ad_id
                    }
                }
            }
        results = self.es.search(body=payload)
        keys    = [set(i['_source'].keys()) for i in results['hits']['hits']]

        return list(reduce(accumulator, keys, set()))

    def lookup(self, ad_id, field):
        """
        Get data from ad_id

        :param ad_id: str
            String to be queried
        """
        payload = {
            "size": self.size,
            "query": {
                "ids": {
                    "values": [ad_id]
                }
            }
        }
        results = self.es.search(body=payload)
        return [
            i['_source'][field] for i in results['hits']['hits']
                if field in i['_source']
        ]
    def reverse_lookup(self, field, field_value):
        """
        Get ad_id from a specific field and search term

        :param field_value: str
            String to be queried
        """
        payload = {
            "size": self.size,
            "query": {
                "match_phrase": {
                    field: field_value
                }
            }
        }
        results = self.es.search(body=payload)
        if not results['hits']['total']:
            payload = {
                "size": self.size,
                "query": {
                    "match_phrase": {
                        "_all": field_value
                    }
                }
            }
            results = self.es.search(body=payload)

        return [
            hit['_id'] for hit in results['hits']['hits']
        ]

    def suggest(self, ad_id, field):
        """
        The suggest function suggests other ad_ids that share this
        field with the input ad_id.
        """
        suggestions = {}
        field_values = self.lookup(ad_id, field)

        for value in field_values:
            ads = set(self.reverse_lookup(field, value))

            # To prevent cycles
            ads.discard(ad_id)
            suggestions[value] = list(ads)

        return suggestions

class FactorNetwork:
    """
    Factor Network Constructor
    ==========================
    Manager class for initializing and
    handling state in a factor network
    """
    def __init__(self, Messenger=Messenger, **kwargs):
        """
        :param Messenger:
            A class constructor following the suggestion
            interface
        :param kwargs:
            Keyword arguments fed into constructor
            to initialize local network object
        """
        self.messenger = Messenger()
        self.G         = nx.Graph(**kwargs)

    def __repr__(self):
        nodes  = nx.number_of_nodes(self.G)
        edges  = nx.number_of_edges(self.G)
        return '{nm}(nodes={nodes}, edges={edges})'.format(
            nm=self.__class__.__name__,
            nodes=nodes,
            edges=edges,
        )

    def get_graph(self, node, factor, **kwargs):
        """
        Create the networkx graph representation

        :param node: str
            Document ID of the root node
        :param factor: str
            A type of factor to query
        :param kwargs:
            Keyword arguments fed into constructor
            to initialize local network object
        """
        G, node = nx.Graph(**kwargs), str(node)
        G.add_node(node)

        message = self.messenger.suggest(node, factor)

        for value, keys in message.items():
            edgelist = itertools.zip_longest([node], keys, fillvalue=node)
            metadata = {'value': value, 'factor': factor}
            G.add_edges_from(edgelist, **metadata)

        return G

    def register_node(self, node, factor):
        node = str(node)
        self.G = nx.compose(self.G, self.get_graph(node, factor))

    def to_dict(self):
        """
        Serialize graph edges back into JSON
        """
        d = collections.defaultdict(list)
        for leaf, node in nx.edges(self.G):
            d[node].append(leaf)

        return dict(d)

    def show(self):
        nx.draw_networkx(self.G,
                         pos=nx.layout.fruchterman_reingold_layout(self.G),
                         with_labels=False,
                         node_size=100,
        )


def run(node):
    _id, factor = node.get('id'), node.get('factor')
    network = FactorNetwork()
    network.register_node(_id, factor)

    return network.to_dict()