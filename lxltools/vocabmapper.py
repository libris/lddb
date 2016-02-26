from rdflib import *
import json


def make_term_map(graph):
    mapping = {}

    def add(s_term, o_term):
        if o_term in mapping:
            v = mapping[o_term]
            if not isinstance(v, list):
                v = [v]
            v.append(s_term)
            s_term = v
        mapping[o_term] = s_term

    def term_pairs(ppath):
        for s, o in graph.subject_objects(ppath):
            if any(isinstance(t, BNode) for t in (s, o)):
                continue
            s_term = graph.qname(s)
            o_term = graph.qname(o)
            if ':' in s_term:
                continue
            if ':' not in o_term:
                continue
            yield s_term, o_term

    for s_term, o_term in term_pairs(OWL.equivalentClass | OWL.equivalentProperty):
        #assert o_term not in mapping
        add(s_term, o_term)

    for s_term, o_term in term_pairs(RDFS.subPropertyOf | RDFS.subClassOf):
        if o_term in mapping:
            continue
        add(s_term, o_term)

    ctx = {pfx or "@vocab": iri for pfx, iri in graph.namespaces()}
    ctx["mapping"] = None
    return {"@context": ctx, "mapping": mapping}
 


def remap(mapping, o):
    if isinstance(o, dict):
        for k, v in o.items():
            new_k = mapping.get(k)
            if new_k:
                del o[k]
                if isinstance(new_k, list):
                    new_k = new_k[0]
                o[new_k] = v
            #if ':' in k: print k, new_k, v
            if k == '@type':
                if isinstance(v, list):
                    vs = o[k] = []
                    for item in v:
                        new_v = mapping.get(item, item)
                        if isinstance(new_v, list):
                            vs += new_v
                        else:
                            vs.append(new_v)
                else:
                    o[k] = mapping.get(v, v)
            remap(mapping, v)
    elif isinstance(o, list):
        for item in o:
            remap(mapping, item)


def autoframe(data):
    if '@graph' not in data:
        return data
    datamap = {o['@id']: o for o in data.pop('@graph')}
    for o in datamap.values():
        for k, v in o.items():
            if isinstance(v, dict):
                ref = v.get('@id')
                if ref and ref in datamap:
                    ro = o[k] = datamap.pop(ref)
                    if ref.startswith('_:'):
                        del ro['@id']
    out = datamap.values()
    return out[0] if len(out) == 1 else out


if __name__ == '__main__':
    import sys
    args = sys.argv[1:]

    def json_dump(o):
        print json.dumps(o, indent=2, separators=(',', ': '),
                sort_keys=True, ensure_ascii=False).encode('utf-8')

    if len(args) == 1:
        vocab_fpath = args[0]
        graph = Graph().parse(vocab_fpath, format='turtle')
        term_map = make_term_map(graph)
        json_dump(term_map)
    else:
        map_fpath, fpath = args
        with open(map_fpath) as fp:
            mapping = json.load(fp)['mapping']
        if fpath.endswith('.ttl'):
            graph = Graph().parse(fpath, format='turtle')
            #remapped = remap(mapping, graph.serialize(format='json-ld-object'))
            from rdflib_jsonld.serializer import from_rdf
            data = from_rdf(graph, auto_compact=True)
        else:
            if fpath == '-':
                data = json.load(sys.stdin)
            else:
                with open(fpath) as fp:
                    data = json.load(fp)
        remap(mapping, data)
        del data['@context']
        data = autoframe(data)
        json_dump(data)
