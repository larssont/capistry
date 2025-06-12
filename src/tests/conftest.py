# src/tests/conftest.py

import os

from hypothesis import HealthCheck, Verbosity, settings

settings.register_profile("long", max_examples=1000)
settings.register_profile(
    "ci", max_examples=250, suppress_health_check=(HealthCheck.too_slow, HealthCheck.data_too_large)
)
settings.register_profile("fast", max_examples=25)
settings.register_profile("debug", max_examples=10, verbosity=Verbosity.verbose)

settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "default"))
