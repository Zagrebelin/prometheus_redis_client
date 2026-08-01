import time
import threading

from redis import StrictRedis


class Refresher(object):

    default_refresh_period = 30

    def __init__(self, refresh_period: float = default_refresh_period, timeout_granule=1):
        self._refresh_functions_lock = threading.Lock()
        self._start_thread_lock = threading.Lock()
        self.refresh_period = refresh_period
        self.timeout_granule = timeout_granule
        self._clean()

    def _clean(self):
        self._refresh_functions = []
        self._refresh_enable = False
        self._refresh_cycle_thread = threading.Thread(target=self.refresh_cycle)
        self._should_be_close = False

    def add_refresh_function(self, func: callable):
        with self._refresh_functions_lock:
            self._refresh_functions.append(func)
        self.start_if_not()

    def start_if_not(self):
        with self._start_thread_lock:
            if self._refresh_enable:
                return
            self._refresh_cycle_thread.start()
            self._refresh_enable = True

    def cleanup_and_stop(self):
        self._should_be_close = True
        if self._refresh_enable:
            self._refresh_cycle_thread.join()
        self._clean()

    def refresh_cycle(self):
        """Check `close` flag every `timeout_granule` and refresh after `refresh_period`."""
        current_time_passed = 0
        while True:
            current_time_passed += self.timeout_granule
            if self._should_be_close:
                return
            if current_time_passed >= self.refresh_period:
                current_time_passed = 0
                with self._refresh_functions_lock:

                    for refresh_func in self._refresh_functions:
                        refresh_func()
            time.sleep(self.timeout_granule)


class MetricFamily(object):
    """A single metric family and its samples (mirrors metrics_core.Metric)."""

    def __init__(self, name, documentation, type, samples):
        self.name = name
        self.documentation = documentation
        self.type = type
        self.samples = samples

    def output(self) -> str:
        doc = "# HELP {name} {doc}\n# TYPE {name} {type}".format(
            name=self.name,
            doc=self.documentation,
            type=self.type,
        )
        return "\n".join([doc] + sorted(s.output() for s in self.samples))


class Registry(object):

    def __init__(self, redis: StrictRedis = None, refresher: Refresher = None):
        self._metrics = []
        self.redis = None
        self.refresher = refresher or Refresher()
        self.set_redis(redis)

    def collect(self, names=None):
        """Yield metric families from the metrics in the registry."""
        metrics = list(self._metrics)
        for metric in metrics:
            if names is not None and metric.name not in names:
                continue
            yield MetricFamily(
                name=metric.name,
                documentation=metric.documentation,
                type=metric.type,
                samples=metric.collect(),
            )

    def output(self, names=None) -> str:
        return "\n".join(family.output() for family in self.collect(names=names))

    def get_sample_value(self, name, labels=None):
        """Return the sample value, or None if not found.

        Intended for use in unittests, mirrors prometheus_client.
        """
        labels = labels or {}
        for family in self.collect():
            for sample in family.samples:
                if sample.name == name and (sample.labels or {}) == labels:
                    return float(sample.value)
        return None

    def add_metric(self, *metrics, fail_on_doubles=True):
        already_added = set([
            m.name for m in self._metrics
        ])
        new_metrics = set([
            m.name for m in metrics
        ])
        doubles = already_added.intersection(new_metrics)
        if doubles and fail_on_doubles:
            raise ValueError("Metrics {} already added".format(
                ", ".join(doubles),
            ))

        for m in metrics:
            if m.name not in already_added:
                self._metrics.append(m)

    def set_redis(self, redis):
        self.redis = redis

    def set_refresher(self, refresher: Refresher):
        self.refresher = refresher

    def cleanup_and_stop(self):
        if self.refresher:
            self.refresher.cleanup_and_stop()
        for metric in self._metrics:
            metric.cleanup()
        self._metrics = []


REGISTRY = Registry()
