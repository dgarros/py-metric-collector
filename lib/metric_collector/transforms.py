# custom transform functions for raw data that cannot be directly parsed

def arista_interface_queues(data):
    new = {'ingressVoqCounters': []}
    for k, v in data['ingressVoqCounters']['interfaces'].items():
        for tc, data in v['trafficClasses'].items():
            item = {'interface': k}
            item['trafficClass'] = tc
            item.update(data)
            new['ingressVoqCounters'].append(item)
    return new


def arista_interface_transceiver(data):
    new = {'interfaces': []}
    for k, v in data['interfaces'].items():
        item = {'interface': k}
        item.update(v)
        new['interfaces'].append(item)
    return new
