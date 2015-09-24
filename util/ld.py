# -*- coding: UTF-8 -*-
from __future__ import unicode_literals
__metaclass__ = type

from rdflib import Graph, ConjunctiveGraph, Literal, URIRef, Namespace, RDF, RDFS, OWL

from lddb.ld.keys import *
from lddb.ld.frame import autoframe


SDO = Namespace("http://schema.org/")
VS = Namespace("http://www.w3.org/2003/06/sw-vocab-status/ns#")


class Vocab:

    def __init__(self, vocab_source, vocab_uri=None, lang='en'):
        self.index = {}
        self.unstable_keys = set()

        label_key_items = []

        g = Graph().parse(vocab_source, format='turtle')
        default_ns = g.store.namespace('')
        if not vocab_uri and (default_ns, RDF.type, OWL.Ontology) in g:
            vocab_uri = default_ns

        get_key = lambda s: s.replace(vocab_uri, '')

        PREF_LABEL = URIRef(vocab_uri + 'prefLabel')
        BASE_LABEL = URIRef(vocab_uri + 'label')

        for s in set(g.subjects()):
            if not isinstance(s, URIRef):
                continue
            if not s.startswith(vocab_uri):
                continue

            key = get_key(s)

            label = None
            for label in g.objects(s, RDFS.label):
                if label.language == lang:
                    break
            if label:
                label = unicode(label)

            for domain in g.objects(s, RDFS.domain | SDO.domainIncludes):
                domain_key = get_key(domain)
                self.index.setdefault(domain_key, {}).setdefault(
                        'properties', []).append(key)

            term = {ID: unicode(s),'label': label, 'curie': key}

            if (s, RDF.type, OWL.ObjectProperty) in g:
                term[TYPE] = ID

            self.index.setdefault(key, {}).update(term)

            if (s, VS.term_status, Literal('unstable')) in g:
                self.unstable_keys.add(key)

            def distance_to(prop):
                return path_distance(g, s,
                    RDFS.subPropertyOf | OWL.equivalentProperty, prop)

            label_distance = distance_to(BASE_LABEL)

            if label_distance is not None:
                preflabel_distance = distance_to(PREF_LABEL)
                order = (preflabel_distance
                         if preflabel_distance is not None else -1,
                         label_distance)
                label_key_items.append((order, key))

        self.label_keys = [key for ldist, key in sorted(label_key_items, reverse=True)]

    def sortedkeys(self, item):
        typeprops = set()
        for itype in as_iterable(item.get(TYPE)):
            typedfn = self.index.get(itype)
            if typedfn:
                typeprops.update(typedfn.get('properties', []))

        label_keys_size = len(self.label_keys)
        def keykey(key):
            classdistance = 0 if typeprops and key in typeprops else 1
            if key.startswith('@'):
                importance_index = 0
            elif key in self.unstable_keys:
                importance_index = label_keys_size + 1
            else:
                try:
                    importance_index = self.label_keys.index(key)
                except ValueError:
                    importance_index = label_keys_size
            is_link = self.index[key].get(TYPE) == ID
            return (importance_index, is_link, classdistance, key)

        return sorted((key for key in item if key in self.index), key=keykey)

    def get_label_for(self, item):
        focus = item.get('focus')
        if focus:
            label = self.construct_label(focus)
            if label:
                return label
        return self.labelgetter(item)

    def construct_label(self, item):
        has = item.__contains__
        v = lambda k: " ".join(as_iterable(item.get(k, '')))
        vs = lambda *ks: [v(k) for k in ks if has(k)]

        types = set(as_iterable(item.get(TYPE)))

        if types & {'UniformWork', 'CreativeWork'}:
            label = self.labelgetter(item)
            attr = item.get('attributedTo')
            if attr:
                attr_label = self.construct_label(attr)
                if attr_label:
                    label = "%s (%s)" % (label, attr_label)
            return label

        if types & {'Person', 'Persona', 'Family', 'Organization', 'Meeting'}:
            return " ".join([
                    v('name') or ", ".join(vs('familyName', 'givenName')),
                    v('numeration'),
                    "(%s)" % v('personTitle') if has('personTitle') else "",
                    "%s-%s" % (v('birthYear'), v('deathYear'))
                    if (has('birthYear') or has('deathYear')) else ""])

    def labelgetter(self, item):
        for lkey in self.label_keys:
            label = item.get(lkey)
            if label:
                return label
        return ""


class View:

    def __init__(self, vocab, storage):
        self.vocab = vocab
        self.storage = storage
        self.rev_limit = 4000
        self.chip_keys = {ID, TYPE} | set(self.vocab.label_keys)

    def get_record_data(self, item_id):
        if item_id[0] != '/':
            item_id = '/' + item_id
        record = self.storage.get_record(item_id)
        return record.data if record else None

    def find_record_ids(self, item_id):
        record_ids = self.storage.find_record_ids(item_id)
        return list(record_ids)

    def find_same_as(self, item_id):
        # TODO: only get identifier
        records = self.storage.find_by_relation('sameAs', item_id, limit=1)
        if records:
            return records[0].identifier

    def get_type_count(self):
        return [(self.vocab.index[rtype], count)
                for rtype, count in self.storage.get_type_count()
                if isinstance(rtype, str)
                if rtype in self.vocab.index]

    def get_decorated_data(self, data, add_references=False):
        if GRAPH in data:
            root = data
            main_id = data[GRAPH][0][ID]
        elif 'descriptions' in data:
            descriptions = data['descriptions']
            entry = descriptions.get('entry')
            items = descriptions.get('items')
            quoted = descriptions.get('quoted')

            graph = []
            if entry:
                _cleanup(entry)
                graph.append(entry)
            if items:
                graph += items
                graph.append(entry)
            if quoted:
                graph += [dict(ngraph[GRAPH], quotedFromGraph={ID: ngraph.get(ID)})
                        for ngraph in quoted]

            main_item = entry if entry else items[0] if items else None
            main_id = main_item.get(ID) if main_item else None

            if add_references:
                graph += self._get_references_to(main_item)

            root = {GRAPH: graph}

        else:
            return data

        return autoframe(root, main_id) or data

    def getlabel(self, item):
        # TODO: cache label...
        return self.vocab.get_label_for(item) or ",".join(v for k, v in item.items()
                if k[0] != '@' and isinstance(v, unicode)) or item[ID]
                #or getlabel(self.get_chip(item[ID]))

    def to_chip(self, item, *keep_refs):
        return {k: v for k, v in item.items()
                if k in self.chip_keys or has_ref(v, *keep_refs)}

    def _get_references_to(self, item):
        references = []
        # TODO: send choice of id:s to find_by_quotation?
        same_as = item.get('sameAs') if item else None
        item_id = item[ID]
        quoted_id = same_as[0].get(ID) if same_as else item_id
        for quoting in self.storage.find_by_quotation(quoted_id, limit=200):
            qdesc = quoting.data['descriptions']
            _fix_refs(item_id, quoted_id, qdesc)
            references.append(self.to_chip(qdesc['entry'], item_id, quoted_id))
            for it in qdesc['items']:
                references.append(self.to_chip(it, item_id, quoted_id))

        return references


# FIXME: quoted id:s are temporary and should be replaced with canonical id (or
# *at least* sameAs id) in stored data
def _fix_refs(real_id, ref_id, descriptions):
    entry = descriptions.get('entry')
    items = descriptions.get('items') or []
    quoted = descriptions.get('quoted') or []

    alias_map = {}
    for quote in quoted:
        item = quote[GRAPH]
        alias = item[ID]
        if alias == ref_id:
            alias_map[alias] = real_id
        else:
            for same_as in as_iterable(item.get('sameAs')):
                if same_as[ID] == ref_id:
                    alias_map[alias] = real_id

    _fix_ref(entry, alias_map)
    for item in items:
        _fix_ref(item, alias_map)

def _fix_ref(item, alias_map):
    for vs in item.values():
        for v in as_iterable(vs):
            if isinstance(v, dict):
                mapped = alias_map.get(v.get(ID))
                if mapped:
                    v[ID] = mapped


# TODO: work as much as possible into initial conversion, rest into filtered view
def _cleanup(item):
    itype = item[TYPE]
    if isinstance(itype, list):
        try:
            itype.remove('Concept')
        except ValueError:
            pass
        if len(itype) == 1:
            item[TYPE] = itype[0]
    if 'prefLabel_en' in item and 'prefLabel' not in item:
        item['prefLabel'] = item['prefLabel_en']
    return item

def as_iterable(vs):
    """
    >>> list(as_iterable(None))
    []
    >>> list(as_iterable([1]))
    [1]
    >>> list(as_iterable(1))
    [1]
    """
    if vs is None:
        return
    if isinstance(vs, list):
        for v in vs:
            yield v
    else:
        yield vs

def has_ref(vs, *refs):
    """
    >>> has_ref({ID: '/item'}, '/item')
    True
    >>> has_ref({ID: '/other'}, '/item')
    False
    >>> has_ref({ID: '/other'}, '/item', '/other')
    True
    >>> has_ref([{ID: '/item'}], '/item')
    True
    """
    for v in as_iterable(vs):
        if isinstance(v, dict) and v.get(ID) in refs:
            return True
    return False

def path_distance(g, s, p, base):
    """
    >>> ns = Namespace("urn:x-ns:")
    >>> g = Graph()
    >>> subpropof = RDFS.subPropertyOf
    >>> g.add((ns.name, subpropof, ns.label))
    >>> g.add((ns.title, subpropof, ns.name))
    >>> g.add((ns.notation, subpropof, ns.title))
    >>> g.add((ns.notation, subpropof, ns.name))

    >>> path_distance(g, ns.comment, subpropof, ns.label)
    >>> path_distance(g, ns.label, subpropof, ns.label)
    0
    >>> path_distance(g, ns.name, subpropof, ns.label)
    1
    >>> path_distance(g, ns.title, subpropof, ns.label)
    2
    >>> path_distance(g, ns.notation, subpropof, ns.label)
    2
    """
    if s == base:
        return 0
    def find_path(s, distance=1):
        shortest = None
        for o in g.objects(s, p):
            if o == base:
                return distance
            else:
                candidate = find_path(o, distance+1)
                if shortest is None or (candidate is not None
                        and candidate < shortest):
                    shortest = candidate
        return shortest
    return find_path(s)


if __name__ == '__main__':
    import doctest
    doctest.testmod()
