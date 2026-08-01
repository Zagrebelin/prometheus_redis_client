import pytest

import prometheus_redis_client as prom
from .helpers import MetricEnvironment


class TestNameBuilding(object):

    def test_counter_without_namespace(self):
        with MetricEnvironment():
            assert prom.Counter("foo", "doc").name == "foo_total"
            assert prom.Counter("foo_total", "doc").name == "foo_total"

    def test_namespace_subsystem_unit(self):
        with MetricEnvironment():
            counter = prom.Counter(
                "requests", "doc",
                namespace="app", subsystem="http", unit="seconds",
            )
            assert counter.name == "app_http_requests_seconds_total"

            gauge = prom.Gauge(
                "requests", "doc",
                namespace="app", subsystem="http", unit="seconds",
            )
            assert gauge.name == "app_http_requests_seconds"

            summary = prom.Summary(
                "requests", "doc",
                namespace="app", subsystem="http", unit="seconds",
            )
            assert summary.name == "app_http_requests_seconds"

            histogram = prom.Histogram(
                "requests", "doc",
                namespace="app", subsystem="http", unit="seconds",
            )
            assert histogram.name == "app_http_requests_seconds"

            common_gauge = prom.CommonGauge(
                "requests", "doc",
                namespace="app", subsystem="http", unit="seconds",
            )
            assert common_gauge.name == "app_http_requests_seconds"

    def test_unit_not_duplicated(self):
        with MetricEnvironment():
            gauge = prom.Gauge("requests_seconds", "doc", unit="seconds")
            assert gauge.name == "requests_seconds"

    def test_invalid_name(self):
        with MetricEnvironment():
            with pytest.raises(ValueError):
                prom.Counter("", "doc")
            with pytest.raises(ValueError):
                prom.Gauge("bad name", "doc")

    def test_positional_labelnames(self):
        with MetricEnvironment():
            counter = prom.Counter("c", "doc", ["host", "url"])
            assert counter.labelnames == ["host", "url"]


class TestCompatParams(object):

    def test_counter_extra_kwargs_ignored(self):
        with MetricEnvironment():
            counter = prom.Counter("c", "doc", _labelvalues=None)
            assert counter.name == "c_total"

    def test_gauge_multiprocess_mode_accepted(self):
        with MetricEnvironment():
            gauge = prom.Gauge("g", "doc", multiprocess_mode="max")
            assert gauge.name == "g"

    def test_histogram_default_buckets(self):
        with MetricEnvironment() as redis:
            histogram = prom.Histogram("h", "doc")
            histogram.observe(0.5)

            output = prom.REGISTRY.output()
            assert output.startswith(
                "# HELP h doc\n"
                "# TYPE h histogram\n"
            )
            assert "h_bucket{le=\"0.5\"} 1" in output
            assert "h_sum 0.5" in output
            assert "h_count 1" in output
            assert len(redis.keys("h_bucket:*")) == 7

    def test_common_gauge_expire_after_extra_kwargs(self):
        with MetricEnvironment():
            common_gauge = prom.CommonGauge(
                "cg", "doc", namespace="app", expire=5,
            )
            assert common_gauge.name == "app_cg"
            assert common_gauge._expire == 5


class TestTime(object):

    def test_histogram_time_decorator(self):
        with MetricEnvironment():
            histogram = prom.Histogram("h", "doc")

            @histogram.time()
            def simple_func():
                import time
                time.sleep(0.01)
                return

            simple_func()

            output = prom.REGISTRY.output()
            assert "h_count 1" in output
            assert "h_sum 0.01" in output

    def test_histogram_time_with_labels_decorator(self):
        with MetricEnvironment():
            histogram = prom.Histogram(
                "h", "doc", labelnames=["host", "url"],
            )

            @histogram.labels(host="123.123.123.123", url="/home/").time()
            def simple_func():
                import time
                time.sleep(0.01)
                return

            simple_func()

            output = prom.REGISTRY.output()
            assert 'h_bucket{host="123.123.123.123",le="0.5",url="/home/"} 1' in output
            assert 'h_count{host="123.123.123.123",url="/home/"} 1' in output
            assert 'h_sum{host="123.123.123.123",url="/home/"} 0.01' in output

    def test_histogram_time_context_manager(self):
        with MetricEnvironment():
            histogram = prom.Histogram("h", "doc")

            with histogram.time():
                pass

            output = prom.REGISTRY.output()
            assert "h_count 1" in output

    def test_summary_time_decorator_with_labels(self):
        with MetricEnvironment():
            summary = prom.Summary(
                "s", "doc", labelnames=["host", "url"],
            )

            @summary.labels(host="123.123.123.123", url="/home/").time()
            def simple_func():
                import time
                time.sleep(0.01)
                return

            simple_func()

            output = prom.REGISTRY.output()
            assert 's_count{host="123.123.123.123",url="/home/"} 1' in output
            assert 's_sum{host="123.123.123.123",url="/home/"} 0.01' in output


class TestRegistryCollect(object):

    def test_collect_yields_families(self):
        with MetricEnvironment():
            counter = prom.Counter("c1", "doc")
            counter.inc(2)

            families = list(prom.REGISTRY.collect())
            assert len(families) == 1
            family = families[0]
            assert family.name == "c1_total"
            assert family.documentation == "doc"
            assert family.type == "counter"
            assert len(family.samples) == 1
            assert family.samples[0].name == "c1_total"
            assert family.samples[0].labels == {}
            assert family.samples[0].value == "2"

    def test_collect_with_labels(self):
        with MetricEnvironment():
            counter = prom.Counter(
                "c1", "doc", labelnames=["host", "url"],
            )
            counter.labels(host="123.123.123.123", url="/home/").inc(2)

            families = list(prom.REGISTRY.collect())
            sample = families[0].samples[0]
            assert sample.labels == {"host": "123.123.123.123", "url": "/home/"}
            assert sample.value == "2"

    def test_samples_tuple_compatible(self):
        with MetricEnvironment():
            counter = prom.Counter("c1", "doc", labelnames=["host"])
            counter.labels(host="a").inc(2)

            sample = list(prom.REGISTRY.collect())[0].samples[0]
            assert sample[0] == "c1_total"
            assert sample[1] == {"host": "a"}
            assert sample[2] == "2"
            assert tuple(sample) == ("c1_total", {"host": "a"}, "2")

    def test_collect_names_filter(self):
        with MetricEnvironment():
            prom.Counter("c1", "doc").inc(1)
            prom.Counter("c2", "doc").inc(1)

            families = list(prom.REGISTRY.collect(names=["c2_total"]))
            assert [f.name for f in families] == ["c2_total"]

            assert list(prom.REGISTRY.collect(names=[])) == []

    def test_output_unchanged_by_refactor(self):
        with MetricEnvironment():
            counter = prom.Counter("c1", "doc")
            counter.inc(2)

            assert prom.REGISTRY.output() == (
                "# HELP c1_total doc\n"
                "# TYPE c1_total counter\n"
                "c1_total 2"
            )

    def test_output_names_filter(self):
        with MetricEnvironment():
            prom.Counter("c1", "doc").inc(1)
            prom.Counter("c2", "doc").inc(1)

            output = prom.REGISTRY.output(names=["c2_total"])
            assert "c1_total" not in output
            assert "c2_total 1" in output

    def test_get_sample_value(self):
        with MetricEnvironment():
            counter = prom.Counter("c1", "doc", labelnames=["host"])
            counter.labels(host="a").inc(3)

            assert prom.REGISTRY.get_sample_value("c1_total", {"host": "a"}) == 3.0
            assert prom.REGISTRY.get_sample_value("c1_total", {"host": "b"}) is None
            assert prom.REGISTRY.get_sample_value("c1_total") is None
            assert prom.REGISTRY.get_sample_value("missing") is None
