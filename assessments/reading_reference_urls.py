from django.urls import path

from . import reading_reference as reading


urlpatterns = [
    path("reading/", reading.parts, name="reading_parts"),
    path("reading/part/<int:part_number>/", reading.intro, name="reading_intro"),
    path("reading/part/<int:part_number>/start/", reading.start, name="reading_start"),
    path("reading/attempt/<int:attempt_id>/", reading.runner, name="reading_runner"),
    path("reading/attempt/<int:attempt_id>/answer/", reading.answer, name="reading_answer"),
    path("reading/attempt/<int:attempt_id>/expire/", reading.expire, name="reading_expire"),
    # Existing dashboard/test-builder links also reach the same Reading owner.
    path("test/cambridge-reading-reference-practice/", reading.test_intro),
    path("test/cambridge-reading-reference-practice/start/", reading.test_start),
]
