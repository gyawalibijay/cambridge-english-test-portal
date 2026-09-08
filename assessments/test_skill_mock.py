from io import StringIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from assessments.models import MockTest, Program, TestSection, TestPart
from assessments.skill_mock_data import SKILLS, SLUGS
from attempts.models import StudentResponse, TestAttempt
from commerce.models import ProgramEntitlement
from question_bank.models import PartQuestion, Question


class SkillMockTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media = TemporaryDirectory(prefix="mock-v29-test-")
        cls.media_override = override_settings(MEDIA_ROOT=cls.media.name)
        cls.media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.media_override.disable()
        cls.media.cleanup()

    @classmethod
    def setUpTestData(cls):
        cls.program, _ = Program.objects.get_or_create(code="cambridge-general", defaults={"name": "Cambridge"})
        call_command("install_skill_mocks", stdout=StringIO())
        cls.user = get_user_model().objects.create_user(username="mock-student", password="test-only")
        cls.other = get_user_model().objects.create_user(username="another-student", password="test-only")
        for user in (cls.user, cls.other):
            ProgramEntitlement.objects.create(user=user, program=cls.program)

    def setUp(self):
        self.client.force_login(self.user)

    def start(self, skill="reading"):
        response = self.client.post(reverse("assessments:start_test", args=[SLUGS[skill]]))
        self.assertEqual(response.status_code, 302)
        attempt = TestAttempt.objects.filter(user=self.user, status="in_progress").latest("pk")
        return attempt

    def item(self, attempt):
        return attempt.attempt_questions.filter(response__isnull=True).order_by("order").first()

    def answer(self, attempt, item=None, **data):
        item = item or self.item(attempt)
        if not data:
            if item.question.question_type == "single_choice":
                data = {"option": item.question.options.get(is_correct=True).pk}
            else:
                data = {"text": item.question.acceptable_answers.first().answer_text}
        return self.client.post(reverse("attempts:submit_objective_response", args=[attempt.pk, item.pk]), data)

    def test_hub_contains_four_actionable_skills_without_sets_or_full_mock(self):
        response = self.client.get("/mock-tests/")
        self.assertTemplateUsed(response, "skill_mock/hub.html")
        for skill in SKILLS:
            self.assertContains(response, reverse("assessments:test_detail", args=[SLUGS[skill]]))
        self.assertNotContains(response, "Cambridge Full Mock")
        self.assertNotContains(response, "Set 1")
        self.assertContains(response, "practice-mock-blue-v29.css")
        self.assertEqual(Question.objects.count(), 26)

    def test_all_four_skills_open_working_question_runners(self):
        for skill, runner, count in (("reading", "objective", 6), ("listening", "objective", 5),
                                     ("speaking", "speaking", 13), ("writing", "writing", 2)):
            detail = self.client.get(reverse("assessments:test_detail", args=[SLUGS[skill]]))
            self.assertContains(detail, f"Start {skill} mock")
            attempt = self.start(skill)
            self.assertEqual(attempt.attempt_questions.count(), count)
            page = self.client.get(reverse("attempts:dispatch", args=[attempt.pk]), follow=True)
            self.assertEqual(page.status_code, 200)
            self.assertTemplateUsed(page, f"attempts/{runner}_runner.html")
            self.assertContains(page, "practice-mock-blue-v29.css")
            if skill == "listening":
                self.assertContains(page, "<audio")
                self.assertNotContains(page, self.item(attempt).question.stimulus.transcript)
            attempt.status = "cancelled"
            attempt.save(update_fields=["status"])

    def test_one_active_mock_across_skills_and_repeated_clicks(self):
        first = self.start()
        self.answer(first)
        self.start()
        self.start("writing")
        self.assertEqual(TestAttempt.objects.filter(user=self.user).count(), 1)
        self.assertEqual(StudentResponse.objects.count(), 1)
        response = self.client.get("/mock-tests/")
        self.assertContains(response, "Resume your test")
        self.assertEqual(response.content.count(b'aria-disabled="true"'), 3)

    def test_get_requests_do_not_restart_or_create_attempts(self):
        self.client.get(reverse("assessments:test_detail", args=[SLUGS["reading"]]) + "?restart=1")
        self.assertFalse(TestAttempt.objects.exists())
        attempt = self.start()
        self.answer(attempt)
        self.client.get(reverse("assessments:test_detail", args=[SLUGS["reading"]]) + "?restart=1")
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "in_progress")
        self.assertEqual(StudentResponse.objects.count(), 1)
        self.assertEqual(self.client.get(reverse("assessments:start_test", args=[SLUGS["reading"]])).status_code, 405)

    def test_finishes_one_test_with_score_no_automatic_next_set(self):
        attempt = self.start()
        for _ in range(6):
            response = self.answer(attempt)
        self.assertRedirects(response, reverse("attempts:complete", args=[attempt.pk]))
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "completed")
        self.assertEqual(attempt.overall_score, 6)
        self.assertEqual(TestAttempt.objects.count(), 1)
        page = self.client.get(response.url)
        self.assertContains(page, "Test finished")
        self.assertNotContains(page, "Take Speaking Again")
        self.assertNotContains(page, "Next set")
        self.start("listening")
        self.assertEqual(TestAttempt.objects.count(), 2)

    def test_duplicate_and_out_of_order_answers_do_not_skip_or_change_answers(self):
        attempt = self.start()
        first = self.item(attempt)
        future = attempt.attempt_questions.last()
        self.answer(attempt, future)
        self.assertFalse(StudentResponse.objects.exists())
        self.answer(attempt, first)
        self.answer(attempt, first, option="not-an-option")
        self.assertEqual(StudentResponse.objects.count(), 1)
        self.assertEqual(StudentResponse.objects.get().final_score, 1)

    def test_blank_and_foreign_options_are_rejected(self):
        attempt = self.start()
        item = self.item(attempt)
        other = attempt.attempt_questions.exclude(pk=item.pk).filter(question__question_type="single_choice").first()
        for value in ("", "invalid", str(other.question.options.first().pk)):
            self.assertEqual(self.answer(attempt, option=value).status_code, 400)
        self.assertFalse(StudentResponse.objects.exists())

    def test_unavailable_content_is_not_advertised_as_ready(self):
        test = MockTest.objects.get(slug=SLUGS["reading"])
        part = test.sections.first().parts.first()
        Question.objects.filter(part_assignments__part=part).update(is_active=False)
        page = self.client.get("/mock-tests/")
        self.assertNotContains(page, f'aria-label="Start Reading mock test"')
        response = self.client.post(reverse("assessments:start_test", args=[test.slug]))
        self.assertEqual(response.status_code, 409)
        self.assertFalse(TestAttempt.objects.exists())

    def test_seed_and_check_are_idempotent_preserve_edits_and_attempts(self):
        attempt = self.start()
        question = Question.objects.filter(skill="reading").first()
        question.prompt_text = "Instructor correction"
        question.save(update_fields=["prompt_text"])
        before = (MockTest.objects.count(), Question.objects.count(), PartQuestion.objects.count())
        call_command("install_skill_mocks", stdout=StringIO())
        call_command("install_skill_mocks", check=True, stdout=StringIO())
        self.assertEqual(before, (MockTest.objects.count(), Question.objects.count(), PartQuestion.objects.count()))
        question.refresh_from_db()
        self.assertEqual(question.prompt_text, "Instructor correction")
        self.assertTrue(TestAttempt.objects.filter(pk=attempt.pk).exists())

    def test_auth_entitlement_csrf_and_ownership_are_preserved(self):
        attempt = self.start()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("attempts:dispatch", args=[attempt.pk])).status_code, 404)
        ProgramEntitlement.objects.filter(user=self.other).update(is_active=False)
        for url in ("/mock-tests/", reverse("assessments:test_detail", args=[SLUGS["reading"]])):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn("/store/", response.url)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(reverse("assessments:start_test", args=[SLUGS["reading"]])).status_code, 403)
        self.client.logout()
        self.assertIn("login", self.client.get("/mock-tests/").url)

    @patch("grading.tasks.grade_writing_response.delay")
    def test_writing_saves_both_tasks_then_stops(self, enqueue):
        attempt = self.start("writing")
        for _ in range(2):
            item = self.item(attempt)
            url = reverse("attempts:submit_writing_response", args=[attempt.pk, item.pk])
            self.client.post(url, {"text_response": "too short"})
            self.assertEqual(self.item(attempt).pk, item.pk)
            response = self.client.post(url, {"text_response": "A useful daily habit helps me feel better. " * 12})
        self.assertEqual(enqueue.call_count, 2)
        self.assertRedirects(response, reverse("attempts:complete", args=[attempt.pk]))
        self.assertContains(self.client.get(response.url), "Submitted for review")
        self.assertEqual(TestAttempt.objects.count(), 1)

    @patch("attempts.score_integrity.analyze_response_audio", return_value={"ok": True})
    @patch("grading.tasks.grade_speaking_response.delay")
    def test_speaking_saves_recordings_then_stops(self, enqueue, quality):
        attempt = self.start("speaking")
        for _ in range(13):
            item = self.item(attempt)
            response = self.client.post(reverse("attempts:submit_speaking_response", args=[attempt.pk, item.pk]),
                {"audio": SimpleUploadedFile("voice.webm", b"test-recording", content_type="audio/webm"), "duration_seconds": "65"})
            self.assertEqual(response.status_code, 200)
        self.assertEqual(enqueue.call_count, 13)
        self.assertEqual(response.json()["next_url"], reverse("attempts:complete", args=[attempt.pk]))
        self.assertContains(self.client.get(response.json()["next_url"]), "Submitted for review")
        self.assertEqual(TestAttempt.objects.count(), 1)

    def test_practice_routes_remain_practice_and_load_shared_blue_style(self):
        self.assertContains(self.client.get("/practice/"), "practice-mock-blue-v29.css")
        self.assertContains(self.client.get("/practice/listening/"), "practice-mock-blue-v29.css")
        test = MockTest.objects.create(program=self.program, slug="unchanged-practice", title="Practice", is_published=True)
        section = TestSection.objects.create(mock_test=test, title="Reading", skill="reading", order=1)
        part = TestPart.objects.create(section=section, title="Part 1", order=1)
        PartQuestion.objects.create(part=part, question=Question.objects.filter(skill="reading").first(), order=1)
        response = self.client.post(reverse("assessments:start_test", args=[test.slug]), {"skill": "reading", "part": 1})
        self.assertEqual(response.status_code, 302)
        attempt = TestAttempt.objects.get(mock_test=test)
        self.assertEqual(attempt.metadata["practice_mode"], "part_set")

    def test_listening_completes_and_wrong_answers_score_zero(self):
        attempt = self.start("listening")
        first = self.item(attempt)
        self.answer(attempt, option=first.question.options.filter(is_correct=False).first().pk)
        self.assertEqual(StudentResponse.objects.get().final_score, 0)
        for _ in range(4):
            response = self.answer(attempt)
        self.assertRedirects(response, reverse("attempts:complete", args=[attempt.pk]))
        attempt.refresh_from_db()
        self.assertEqual(attempt.overall_score, 4)
        self.assertEqual(TestAttempt.objects.count(), 1)

    @patch("grading.tasks.grade_writing_response.delay", side_effect=ConnectionError("Test broker unavailable"))
    def test_review_outage_preserves_answer_and_continues(self, enqueue):
        attempt = self.start("writing")
        item = self.item(attempt)
        with self.assertLogs("assessments.skill_mock", level="ERROR"):
            response = self.client.post(reverse("attempts:submit_writing_response", args=[attempt.pk, item.pk]),
                                        {"text_response": "A useful daily habit helps me feel better. " * 12})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(StudentResponse.objects.get().review_status, "pending")
        self.assertNotEqual(self.item(attempt).pk, item.pk)

    def test_wrong_endpoint_cannot_skip_objective_question(self):
        attempt = self.start()
        item = self.item(attempt)
        self.client.post(reverse("attempts:submit_writing_response", args=[attempt.pk, item.pk]), {"text_response": "wrong endpoint"})
        response = self.client.post(reverse("attempts:submit_speaking_response", args=[attempt.pk, item.pk]),
                                   {"audio": SimpleUploadedFile("sample.webm", b"sample")})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(StudentResponse.objects.exists())

    def test_readiness_check_detects_missing_audio(self):
        with patch("django.core.files.storage.FileSystemStorage.exists", return_value=False):
            with self.assertRaises(CommandError):
                call_command("install_skill_mocks", check=True, stdout=StringIO())
