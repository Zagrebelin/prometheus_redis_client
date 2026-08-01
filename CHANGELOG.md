# Changelog


#### 0.8.0

* Metric constructors are drop-in compatible with `prometheus_client`:
  `namespace`, `subsystem`, `unit` params and full metric name building.
* `Counter` is always exported with `_total` suffix like `prometheus_client`.
* `Histogram` gets prometheus-client default buckets.
* Accept (and ignore) extra `prometheus_client` constructor params
  (`multiprocess_mode`, `_labelvalues`).
* Add `time()` (decorator + context manager, also via `labels().time()`)
  to `Summary` and `Histogram`, mirroring `prometheus_client.context_managers.Timer`.
* Add `PrometheusDjangoView` in `prometheus_redis_client.django`
  (Prometheus federation filter via `?name[]=` supported).
* Document method-level differences to be fixed later.


#### 0.7.0

* Move packaging from distutils to setuptools.
* Update tox to Python 3.12-3.14 and redis 4.6.
* Modernize test environment setup (PROMETHEUS_REDIS_URI).


#### 0.5.0

* Add `set` to Counter (@darkman66)

#### 0.4.0

* Add `inc` and `dec` to CommonGauge (@maxfrei)

#### 0.3.0

* Fix documentation
* Add expire for CommonGauge.

#### 0.2.0

* Add CommonGauge metric.
* Add timeit decorator for Summary and Histogram
* Start tests via tox in docker for python 3.5, 3.6, 3.7.


#### 0.1.0

* Metric Counter, Summary, Histogram and Gauge (per process).