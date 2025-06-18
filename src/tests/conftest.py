import os

from hypothesis import HealthCheck, Verbosity, settings

settings.register_profile(
    "ci", max_examples=500, suppress_health_check=(HealthCheck.too_slow, HealthCheck.data_too_large)
)
settings.register_profile("quick", max_examples=25)
settings.register_profile("debug", max_examples=10, verbosity=Verbosity.verbose)

settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "default"))
