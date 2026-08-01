import os

from django.http import HttpResponse
from django.views import View

from prometheus_redis_client import REGISTRY


class PrometheusDjangoView(View):
    multiprocess_mode: bool = "PROMETHEUS_MULTIPROC_DIR" in os.environ or "prometheus_multiproc_dir" in os.environ
    registry = None

    def get(self, request, *args, **kwargs):
        if self.registry is None:
            self.registry = REGISTRY
        names = request.GET.getlist("name[]") or None
        output = self.registry.output(names=names)
        return HttpResponse(output, content_type="text/plain; charset=utf-8")

    def options(self, request, *args, **kwargs):
        return HttpResponse(
            status=200,
            headers={"Allow": "OPTIONS,GET"},
        )
