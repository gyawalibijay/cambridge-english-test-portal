import re

from django.shortcuts import redirect

from assessments.models import MockTest
from attempts.models import TestAttempt

from .services import has_program_access


class ProgramAccessMiddleware:
    """
    Back-end access gate for paid exam/course packages.

    The current student Practice, Mock Test and Learn areas belong to the
    Cambridge program. Future program-specific routes can use /practice/program/<code>/
    and are automatically checked against ProgramEntitlement.
    """

    PROGRAM_PATHS = {
        "/practice/": "cambridge-general",
        "/practice/cambridge/": "cambridge-general",
        "/mock-tests/": "cambridge-general",
        "/learn/": "cambridge-general",
    }

    FINAL_PRACTICE_PATTERN = re.compile(
        r"^/practice/(reading|writing|listening|speaking)/?$"
    )
    TEST_PATTERN = re.compile(r"^/practice/test/([^/]+)/")
    PROGRAM_PATTERN = re.compile(r"^/practice/program/([^/]+)/")
    ATTEMPT_PATTERN = re.compile(r"^/attempt/(\d+)/")

    def __init__(self, get_response):
        self.get_response = get_response

    def _required_program(self, path):
        if path in self.PROGRAM_PATHS:
            return self.PROGRAM_PATHS[path]

        if self.FINAL_PRACTICE_PATTERN.match(path):
            return "cambridge-general"

        match = self.PROGRAM_PATTERN.match(path)
        if match:
            return match.group(1)

        match = self.TEST_PATTERN.match(path)
        if match:
            slug = match.group(1)
            test = (
                MockTest.objects
                .filter(slug=slug)
                .select_related("program")
                .first()
            )
            return test.program.code if test else None

        match = self.ATTEMPT_PATTERN.match(path)
        if match:
            attempt = (
                TestAttempt.objects
                .filter(pk=int(match.group(1)))
                .select_related("mock_test__program")
                .first()
            )
            return attempt.mock_test.program.code if attempt else None

        return None

    def __call__(self, request):
        user = request.user

        if (
            not getattr(user, "is_authenticated", False)
            or user.is_superuser
            or user.is_staff
            or getattr(user, "role", "") in {"admin", "evaluator"}
        ):
            return self.get_response(request)

        program_code = self._required_program(request.path)
        if not program_code:
            return self.get_response(request)

        from assessments.models import Program

        program = Program.objects.filter(code=program_code).first()
        if program and not has_program_access(user, program):
            return redirect(f"/store/?locked={program.code}")

        return self.get_response(request)
