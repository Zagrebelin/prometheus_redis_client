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
