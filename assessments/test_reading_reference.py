from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import resolve, reverse
from django.utils import timezone

from assessments.models import MockTest, Program, TestPart, TestSection
from assessments.reading_reference_data import SLUG
from attempts.models import AttemptQuestion, StudentResponse, TestAttempt
from question_bank.models import AcceptableAnswer, PartQuestion, Question, QuestionOption, Stimulus


class ReadingReferenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.program = Program.objects.create(code="cambridge-general", name="Cambridge")
        cls.legacy_test = MockTest.objects.create(program=cls.program, title="Existing sample", slug="existing-reading", is_published=True)
        cls.original_question = Question.objects.create(program=cls.program, title="Do not overwrite", skill="reading", question_type="short_answer", prompt_text="Original sample")
        call_command("install_reading_reference", publish=True, stdout=StringIO())
        cls.test = MockTest.objects.get(slug=SLUG)
        cls.user = get_user_model().objects.create_user(username="reader", password="test-only", is_staff=True)
        cls.other = get_user_model().objects.create_user(username="other", password="test-only", is_staff=True)

    def setUp(self):
        self.client.force_login(self.user)

    def start_part(self, number=1):
        response = self.client.post(reverse("assessments:reading_start", args=[number]))
        self.assertEqual(response.status_code, 302)
        return TestAttempt.objects.filter(user=self.user, status="in_progress").latest("pk")

    def next_item(self, attempt):
        return attempt.attempt_questions.filter(response__isnull=True).order_by("order").first()

    def submit(self, attempt, **data):
        return self.client.post(reverse("assessments:reading_answer", args=[attempt.pk]), data)

    def test_correct_routes_and_templates(self):
        self.assertEqual(resolve("/practice/reading/").url_name, "reading_parts")
        response = self.client.get("/practice/reading/")
        self.assertTemplateUsed(response, "reading_reference/parts.html")
        self.assertContains(response, "Reading Part 5")
        self.assertEqual(response.content.count(b"Not available"), 2)
        response = self.client.get(reverse("assessments:reading_intro", args=[1]))
        self.assertContains(response, "You will read 4 short texts.")
        self.assertContains(response, "START TEST")
        self.assertNotContains(response, "sectionTimer")

    def test_missing_material_not_fabricated(self):
        self.assertEqual(self.test.sections.get().parts.get(order=2).question_count, 3)
        response = self.client.get(reverse("assessments:reading_intro", args=[2]))
        self.assertContains(response, "You will read 3 short sentences.")
        response = self.client.post(reverse("assessments:reading_start", args=[4]))
        self.assertRedirects(response, reverse("assessments:reading_parts"))
        self.assertFalse(TestAttempt.objects.exists())

    def test_import_idempotent_and_preserves_admin_edits(self):
        before = (MockTest.objects.count(), Question.objects.count(), Stimulus.objects.count())
        q = self.test.sections.get().parts.get(order=1).question_assignments.first().question
        q.prompt_text = "Admin correction"
        q.save(update_fields=["prompt_text"])
        call_command("install_reading_reference", publish=True, stdout=StringIO())
        self.assertEqual(before, (MockTest.objects.count(), Question.objects.count(), Stimulus.objects.count()))
        q.refresh_from_db()
        self.assertEqual(q.prompt_text, "Admin correction")
        self.original_question.refresh_from_db()
        self.assertEqual(self.original_question.prompt_text, "Original sample")
        self.legacy_test.refresh_from_db()
        self.assertTrue(self.legacy_test.is_published)

    def test_progress_stays_in_same_part(self):
        attempt = self.start_part()
        deadline = attempt.metadata["reading_deadline"]
        for number in range(1, 5):
            page = self.client.get(reverse("assessments:reading_runner", args=[attempt.pk]))
            self.assertContains(page, f"{number}/4")
            self.assertNotContains(page, "is_correct")
            self.assertNotContains(page, "MutationObserver")
            item = self.next_item(attempt)
            answer = item.question.options.get(is_correct=True)
            response = self.submit(attempt, item=item.pk, option=answer.pk)
        self.assertRedirects(response, reverse("assessments:reading_intro", args=[1]))
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "completed")
        self.assertEqual(attempt.overall_score, 4)
        self.assertEqual(attempt.metadata["reading_deadline"], deadline)
        self.assertContains(self.client.get("/practice/reading/"), 'aria-label="Completed"')

    def test_mcq_and_typed_parts(self):
        for part_number, count in ((2, 3), (3, 4)):
            attempt = self.start_part(part_number)
            for index in range(count):
                item = self.next_item(attempt)
                if part_number == 2:
                    response = self.submit(attempt, item=item.pk, option=item.question.options.get(is_correct=True).pk)
                else:
                    answer = item.question.acceptable_answers.first().answer_text
                    response = self.submit(attempt, item=item.pk, text="  " + answer.upper() + "  ")
            attempt.refresh_from_db()
            self.assertEqual(attempt.overall_score, count)
        self.assertRedirects(response, reverse("assessments:reading_intro", args=[3]))

    def test_wrong_answer_marks_zero_not_positive(self):
        attempt = self.start_part()
        item = self.next_item(attempt)
        self.submit(attempt, item=item.pk, option=item.question.options.filter(is_correct=False).first().pk)
        self.assertEqual(item.response.final_score, 0)

    def test_blank_text_rejected_without_advancing(self):
        attempt = self.start_part(3)
        item = self.next_item(attempt)
        response = self.submit(attempt, item=item.pk, text="   ")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.next_item(attempt).pk, item.pk)
        self.assertFalse(StudentResponse.objects.exists())

    def test_invalid_or_foreign_option_is_not_saved(self):
        attempt = self.start_part()
        item = self.next_item(attempt)
        foreign = attempt.attempt_questions.last().question.options.first()
        for option in [foreign.pk, "bad", "9" * 200, "١", ""]:
            response = self.submit(attempt, item=item.pk, option=option)
            self.assertEqual(response.status_code, 400)
        self.assertFalse(StudentResponse.objects.exists())

    def test_duplicate_submit_and_future_item_do_not_skip(self):
        attempt = self.start_part()
        first = self.next_item(attempt)
        last = attempt.attempt_questions.last()
        self.submit(attempt, item=last.pk, option=last.question.options.first().pk)
        self.assertFalse(StudentResponse.objects.exists())
        selected = first.question.options.get(is_correct=True).pk
        for _ in range(2):
            self.submit(attempt, item=first.pk, option=selected)
        self.assertEqual(StudentResponse.objects.count(), 1)
        self.assertEqual(self.next_item(attempt).order, 2)

    def test_start_duplicate_resume_and_restart(self):
        original = self.start_part()
        self.start_part()
        self.assertEqual(TestAttempt.objects.count(), 1)
        response = self.client.get(reverse("assessments:reading_intro", args=[1]))
        self.assertContains(response, "Resume test")
        self.client.post(reverse("assessments:reading_start", args=[1]), {"restart": "1", "resume_attempt": original.pk})
        original.refresh_from_db()
        self.assertEqual(original.status, "cancelled")
        self.assertEqual(TestAttempt.objects.count(), 2)
        self.assertEqual(AttemptQuestion.objects.filter(attempt=original).count(), 4)

    def test_clock_excludes_instruction_time_and_survives_refresh(self):
        self.client.get(reverse("assessments:reading_intro", args=[1]))
        self.assertFalse(TestAttempt.objects.exists())
        attempt = self.start_part()
        deadline = attempt.metadata["reading_deadline"]
        with patch("assessments.reading_reference.timezone.now", return_value=timezone.now() + timedelta(seconds=50)):
            for _ in range(2):
                page = self.client.get(reverse("assessments:reading_runner", args=[attempt.pk]))
                self.assertContains(page, "04:10")
                self.assertEqual(page.context["total"], 4)
        attempt.refresh_from_db()
        self.assertEqual(attempt.metadata["reading_deadline"], deadline)

    def test_expiry_server_enforced_even_without_javascript(self):
        attempt = self.start_part()
        item = self.next_item(attempt)
        attempt.metadata["reading_deadline"] = timezone.now().timestamp() - 1
        attempt.save(update_fields=["metadata"])
        self.submit(attempt, item=item.pk, option=item.question.options.get(is_correct=True).pk)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "completed")
        self.assertEqual(attempt.overall_score, 0)
        self.assertEqual(StudentResponse.objects.count(), 4)
        self.assertTrue(attempt.metadata["reading_timed_out"])

    def test_expire_endpoint_early_call_and_saved_answer(self):
        attempt = self.start_part()
        url = reverse("assessments:reading_expire", args=[attempt.pk])
        self.client.post(url)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "in_progress")
        first = self.next_item(attempt)
        self.submit(attempt, item=first.pk, option=first.question.options.get(is_correct=True).pk)
        attempt.metadata["reading_deadline"] = timezone.now().timestamp() - 1
        attempt.save(update_fields=["metadata"])
        self.client.post(url)
        self.client.post(url)
        attempt.refresh_from_db()
        self.assertEqual(attempt.overall_score, 1)
        self.assertEqual(StudentResponse.objects.count(), 4)

    def test_other_user_cannot_view_or_submit_even_if_staff(self):
        attempt = self.start_part()
        self.client.force_login(self.other)
        for route in ("reading_runner", "reading_answer", "reading_expire"):
            method = self.client.get if route == "reading_runner" else self.client.post
            self.assertEqual(method(reverse("assessments:" + route, args=[attempt.pk])).status_code, 404)

    def test_package_access_login_and_csrf(self):
        self.client.logout()
        self.assertEqual(self.client.get("/practice/reading/").status_code, 302)
        self.other.is_staff = False
        self.other.save()
        self.client.force_login(self.other)
        self.assertRedirects(self.client.post(reverse("assessments:reading_start", args=[1])), "/store/?locked=cambridge-general", fetch_redirect_response=False)
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.user)
        self.assertEqual(secure.post(reverse("assessments:reading_start", args=[1])).status_code, 403)

    def test_generic_dashboard_resume_uses_reading_owner(self):
        attempt = self.start_part()
        for name in ("dispatch", "objective_runner"):
            response = self.client.get(reverse("attempts:" + name, args=[attempt.pk]))
            self.assertRedirects(response, reverse("assessments:reading_runner", args=[attempt.pk]))
        first = self.next_item(attempt)
        # Generic old endpoint cannot bypass the new deadline/input validation.
        response = self.client.post(reverse("attempts:submit_objective_response", args=[attempt.pk, first.pk]), {"option": "invalid"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(StudentResponse.objects.exists())

    def test_test_builder_links_use_reading_intro(self):
        response = self.client.get(f"/practice/test/{SLUG}/?part=3")
        self.assertRedirects(response, reverse("assessments:reading_intro", args=[3]))
        self.assertEqual(self.client.get(f"/practice/test/{SLUG}/?part=oops").status_code, 404)
        self.client.post(f"/practice/test/{SLUG}/start/", {"part": "3"})
        self.assertEqual(TestAttempt.objects.get().metadata["practice_part"], 3)

    def test_other_skills_keep_their_routes(self):
        for skill, qtype, expected in (("speaking", "recorded_response", "speaking_runner"), ("listening", "single_choice", "objective_runner"), ("writing", "long_text", "writing_runner")):
            section = TestSection.objects.create(mock_test=self.legacy_test, title=skill, skill=skill, order={"speaking": 1, "listening": 2, "writing": 3}[skill])
            part = TestPart.objects.create(section=section, title=skill, order=1)
            question = Question.objects.create(program=self.program, title=skill, skill=skill, question_type=qtype)
            attempt = TestAttempt.objects.create(user=self.user, mock_test=self.legacy_test)
            AttemptQuestion.objects.create(attempt=attempt, part=part, question=question, order=1)
            response = self.client.get(reverse("attempts:dispatch", args=[attempt.pk]))
            self.assertRedirects(response, reverse("attempts:" + expected, args=[attempt.pk]), fetch_redirect_response=False)

    def add_set(self, part_number, set_number, count=4):
        """Synthetic fixtures in the test database only; never published/imported."""
        part = self.test.sections.get().parts.get(order=part_number)
        ids = []
        for index in range(count):
            question = Question.objects.create(
                program=self.program, title=f"TEST ONLY P{part_number} S{set_number} Q{index}",
                skill="reading", question_type="gap_fill" if part_number == 3 else "single_choice",
                prompt_text="TEST FIXTURE: choose or write the correct answer", default_points=1,
            )
            if part_number == 3:
                AcceptableAnswer.objects.create(question=question, answer_text="test")
            else:
                QuestionOption.objects.create(question=question, text="Fixture correct", order=1, is_correct=True)
                QuestionOption.objects.create(question=question, text="Fixture incorrect", order=2, is_correct=False)
            PartQuestion.objects.create(part=part, question=question, order=(set_number - 1) * 4 + index + 1)
            ids.append(question.pk)
        return set(ids)

    def finish_set(self, attempt):
        response = None
        while (item := self.next_item(attempt)) is not None:
            data = {"item": item.pk}
            if item.question.question_type == "single_choice":
                data["option"] = item.question.options.get(is_correct=True).pk
            else:
                data["text"] = item.question.acceptable_answers.first().answer_text
            response = self.submit(attempt, **data)
        return response

    def test_sequential_sets_never_change_part_or_reuse_questions(self):
        second_ids = self.add_set(1, 2)
        third_ids = self.add_set(1, 3)
        first = self.start_part(1)
        self.assertContains(self.client.get(reverse("assessments:reading_runner", args=[first.pk])), "Reading Part 1 · Set 1")
        response = self.finish_set(first)
        self.assertRedirects(response, reverse("assessments:reading_intro", args=[1]))
        page = self.client.get(response.url)
        self.assertContains(page, "Set 2")
        self.assertNotContains(page, "Reading Part 2")
        self.assertNotContains(self.client.get("/practice/reading/"), 'aria-label="Completed"')
        second = self.start_part(1)
        self.assertEqual(second.metadata["practice_part"], 1)
        self.assertEqual(second.metadata["practice_set"], 2)
        self.assertEqual(set(second.attempt_questions.values_list("question_id", flat=True)), second_ids)
        self.assertTrue(second_ids.isdisjoint(first.attempt_questions.values_list("question_id", flat=True)))
        page = self.client.get(reverse("assessments:reading_runner", args=[second.pk]))
        self.assertContains(page, "1/4")
        self.assertContains(page, "05:00")
        self.assertContains(page, "Reading Part 1 · Set 2")
        self.finish_set(second)
        third = self.start_part(1)
        self.assertEqual(third.metadata["practice_set"], 3)
        self.assertEqual(set(third.attempt_questions.values_list("question_id", flat=True)), third_ids)
        self.finish_set(third)
        self.assertContains(self.client.get("/practice/reading/"), 'aria-label="Completed"')

    def test_no_set_selector_outside_or_inside_and_tampering_ignored(self):
        self.add_set(1, 2)
        page = self.client.get("/practice/reading/")
        for text in ("Set 1", "Set 2", "?set=", 'name="set"', "<select"):
            self.assertNotContains(page, text)
        page = self.client.get(reverse("assessments:reading_intro", args=[1]) + "?set=99")
        self.assertContains(page, "Set 1")
        self.assertNotContains(page, "Set 99")
        self.client.post(reverse("assessments:reading_start", args=[1]), {"set": 99, "practice_set": 99})
        first = TestAttempt.objects.get()
        self.assertEqual(first.metadata["practice_set"], 1)
        self.finish_set(first)
        self.client.post(reverse("assessments:reading_start", args=[1]), {"set": 99, "practice_set": 99})
        second = TestAttempt.objects.get(status="in_progress")
        self.assertEqual(second.metadata["practice_set"], 2)

    def test_no_future_questions_does_not_create_fake_set(self):
        first = self.start_part(1)
        self.finish_set(first)
        page = self.client.get(reverse("assessments:reading_intro", args=[1]))
        self.assertTemplateUsed(page, "reading_reference/sets_complete.html")
        self.assertContains(page, "Set 1 completed")
        self.assertContains(page, "No further sets")
        self.assertNotContains(page, "Reading Part 2")
        self.client.post(reverse("assessments:reading_start", args=[1]), {"set": 2})
        self.assertEqual(TestAttempt.objects.count(), 1)
        self.assertFalse(TestAttempt.objects.filter(status="in_progress").exists())

    def test_new_set_becomes_available_after_existing_set_was_completed(self):
        first = self.start_part(1)
        self.finish_set(first)
        self.assertContains(self.client.get("/practice/reading/"), 'aria-label="Completed"')
        self.add_set(1, 2)
        self.assertContains(self.client.get(reverse("assessments:reading_intro", args=[1])), "Set 2")
        self.assertNotContains(self.client.get("/practice/reading/"), 'aria-label="Completed"')
        second = self.start_part(1)
        self.assertEqual(second.metadata["practice_set"], 2)

    def test_partial_first_set_does_not_shift_second_set(self):
        second_ids = self.add_set(2, 2)
        first = self.start_part(2)
        self.assertEqual(first.attempt_questions.count(), 3)
        self.finish_set(first)
        second = self.start_part(2)
        self.assertEqual(second.metadata["practice_set"], 2)
        self.assertEqual(set(second.attempt_questions.values_list("question_id", flat=True)), second_ids)
        part = self.test.sections.get().parts.get(order=2)
        first_question = part.question_assignments.get(order=1).question
        first_question.is_active = False
        first_question.save()
        self.assertEqual(second.attempt_questions.count(), 4)

    def test_missing_middle_set_is_not_skipped(self):
        self.add_set(1, 3)
        self.finish_set(self.start_part(1))
        page = self.client.get(reverse("assessments:reading_intro", args=[1]))
        self.assertTemplateUsed(page, "reading_reference/sets_complete.html")
        self.client.post(reverse("assessments:reading_start", args=[1]), {"set": 3})
        self.assertEqual(TestAttempt.objects.count(), 1)

    def test_timeout_advances_set_within_same_part(self):
        self.add_set(3, 2)
        first = self.start_part(3)
        first.metadata["reading_deadline"] = timezone.now().timestamp() - 1
        first.save(update_fields=["metadata"])
        response = self.client.post(reverse("assessments:reading_expire", args=[first.pk]))
        self.assertRedirects(response, reverse("assessments:reading_intro", args=[3]))
        self.assertContains(self.client.get(response.url), "Set 2")
        second = self.start_part(3)
        self.assertEqual(second.metadata["practice_set"], 2)
        self.assertEqual(second.attempt_questions.count(), 4)

    def test_second_set_resume_and_stale_restart_preserve_current_attempt(self):
        self.add_set(1, 2)
        self.finish_set(self.start_part(1))
        second = self.start_part(1)
        page = self.client.get(reverse("assessments:reading_intro", args=[1]))
        self.assertContains(page, "Reading Part 1 · Set 2")
        url = reverse("assessments:reading_start", args=[1])
        data = {"restart": "1", "resume_attempt": second.pk, "set": "88"}
        response = self.client.post(url, data)
        newer = TestAttempt.objects.get(status="in_progress")
        self.assertEqual(newer.metadata["practice_set"], 2)
        response2 = self.client.post(url, data)
        self.assertEqual(response2.url, response.url)
        self.assertEqual(TestAttempt.objects.count(), 3)
        second.refresh_from_db()
        self.assertEqual(second.status, "cancelled")

    def test_explicit_practise_again_keeps_same_set_number(self):
        first = self.start_part(1)
        self.finish_set(first)
        data = {"restart": "1", "repeat_from": first.pk, "set": "123"}
        url = reverse("assessments:reading_start", args=[1])
        self.client.post(url, data)
        repeated = TestAttempt.objects.get(status="in_progress")
        self.assertEqual(repeated.metadata["practice_set"], 1)
        self.client.post(url, data)
        self.assertEqual(TestAttempt.objects.count(), 2)
        self.assertEqual(TestAttempt.objects.get(status="in_progress").pk, repeated.pk)

    def test_other_user_progress_is_independent(self):
        self.add_set(1, 2)
        self.finish_set(self.start_part(1))
        self.client.force_login(self.other)
        response = self.client.post(reverse("assessments:reading_start", args=[1]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TestAttempt.objects.get(user=self.other).metadata["practice_set"], 1)
