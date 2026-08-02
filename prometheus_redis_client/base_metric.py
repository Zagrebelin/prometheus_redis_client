"""Module provide base Metric classes."""
import json
import base64
import logging
import re
from collections import namedtuple
from typing import List
from functools import partial, wraps

from prometheus_redis_client.registry import Registry, REGISTRY


METRIC_NAME_RE = re.compile(r'^[a-zA-Z_:][a-zA-Z0-9_:]*$')


def build_full_name(metric_type, name, namespace, subsystem, unit):
    """Compose full metric name like prometheus_client does."""
    if not name:
        raise ValueError('Metric name should not be empty')
    full_name = ''
    if namespace:
        full_name += namespace + '_'
    if subsystem:
        full_name += subsystem + '_'
    full_name += name
    if metric_type == 'counter' and full_name.endswith('_total'):
        full_name = full_name[:-6]  # Munge to OpenMetrics.
    if unit and not full_name.endswith("_" + unit):
        full_name += "_" + unit
    if not METRIC_NAME_RE.match(full_name):
        raise ValueError("invalid metric name " + full_name)
    return full_name


logger = logging.getLogger(__name__)


class BaseRepresentation(object):

    def output(self) -> str:
        raise NotImplementedError


class MetricRepresentation(
        namedtuple('MetricRepresentation', ['name', 'labels', 'value']),
        BaseRepresentation,
):

    def output(self) -> str:
        if self.labels is None:
            labels_str = ""
        else:
            labels_str = ",".join([
                '{key}=\"{val}\"'.format(
                    key=key,
                    val=self.labels[key]
                ) for key in sorted(self.labels.keys())
            ])
            if labels_str:
                labels_str = "{" + labels_str + "}"
        return "%(name)s%(labels)s %(value)s" % dict(
            name=self.name,
            labels=labels_str,
            value=self.value
        )


class DocRepresentation(BaseRepresentation):

    def __init__(self, name: str, type: str, documentation: str):
        self.doc = documentation
        self.name = name
        self.type = type

    def output(self):
        return "# HELP {name} {doc}\n# TYPE {name} {type}".format(
            doc=self.doc,
            name=self.name,
            type=self.type,
        )


class WithLabels(object):
    """Wrap functions and put 'labels' argument to it."""
    __slot__ = (
        "instance",
        "labels",
        "wrapped_functions_names",
    )

    def __init__(self, instance, labels: dict, wrapped_functions_names: List[str]):
        self.instance = instance
        self.labels = labels
        self.wrapped_functions_names = wrapped_functions_names

    def __getattr__(self, wrapped_function_name):
        if wrapped_function_name not in self.wrapped_functions_names:
            raise TypeError("Labels work with functions {} only".format(
                self.wrapped_functions_names,
            ))
        wrapped_function = getattr(self.instance, wrapped_function_name)
        return partial(wrapped_function, labels=self.labels)


class BaseMetric(object):
    """
    Proxy object for real work objects called 'minions'.
    Use as global representation on metric.
    """

    minion = None
    type = ''
    wrapped_functions_names = []

    def __init__(self, name: str,
                 documentation: str, labelnames: list=None,
                 namespace: str = '',
                 subsystem: str = '',
                 unit: str = '',
                 registry: Registry=REGISTRY,
                 _labelvalues: list=None,
                 **kwargs):
        self.documentation = documentation
        self.labelnames = labelnames or []
        self._observed = False
        self._name = build_full_name(
            self.type, name, namespace, subsystem, unit,
        )
        self.name = self._name
        if self.type == 'counter':
            self.name += '_total'
        self.registry = registry
        self.registry.add_metric(self, fail_on_doubles=False)

    def doc_string(self) -> DocRepresentation:
        return DocRepresentation(
            self.name,
            self.type,
            self.documentation,
        )

    def get_metric_group_key(self):
        return "{}_group".format(self.name)

    def get_metric_key(self, labels, suffix: str=None):
        return "{}{}:{}".format(
            self.name,
            suffix or "",
            self.pack_labels(labels).decode('utf-8'),
        )

    def parse_metric_key(self, key) -> (str, dict):
        return key.decode('utf-8').split(':', maxsplit=1)

    def pack_labels(self, labels: dict) -> bytes:
        return base64.b64encode(
            json.dumps(labels, sort_keys=True).encode('utf-8')
        )

    def unpack_labels(self, labels: str) -> dict:
        return json.loads(base64.b64decode(labels).decode('utf-8'))

    def _check_labels(self, labels):
        if set(labels.keys()) != set(self.labelnames):
            raise ValueError("Expect define all labels: {}. Got only: {}".format(
                ", ".join(self.labelnames),
                ", ".join(labels.keys())
            ))

    def labels(self, *args, **kwargs):
        labels = dict(zip(self.labelnames, args))
        labels.update(kwargs)
        self._check_labels(labels)
        return WithLabels(
            instance=self,
            labels=labels,
            wrapped_functions_names=self.wrapped_functions_names,
        )


def silent_wrapper(func):
    """Wrap function for process any Exception and write it to log."""
    @wraps(func)
    def silent_function(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.exception("Error while send metric to Redis. Function %s", func)

    return silent_function


def async_silent_wrapper(func):
    """Wrap function for process any Exception and write it to log."""
    @wraps(func)
    async def silent_function(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception:
            logger.exception("Error while send metric to Redis. Function %s", func)

    return silent_function