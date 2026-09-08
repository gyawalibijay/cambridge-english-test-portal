from django.test import TestCase
from django.urls import reverse

from .models import PublicProgramLanding, PublicSiteSettings


class PublicHomeTests(TestCase):
    def setUp(self):
        PublicSiteSettings.load()
        defaults = {
            "short_label": "Test",
            "card_kicker": "FOCUSED",
            "card_title": "Test preparation",
            "card_summary": "Focused practice.",
            "hero_eyebrow": "TEST",
            "hero_title": "Prepare for the test.",
            "hero_description": "Focused test preparation.",
            "audience_text": "Students.",
            "format_text": "Practice.",
            "benefit_one_title": "One",
            "benefit_one_text": "One.",
            "benefit_two_title": "Two",
            "benefit_two_text": "Two.",
            "benefit_three_title": "Three",
            "benefit_three_text": "Three.",
            "seo_title": "Test",
            "seo_description": "Test preparation.",
            "seo_keywords": "test",
        }
        for order, key in enumerate(("cambridge-english", "ielts", "uk-interview"), 1):
            PublicProgramLanding.objects.update_or_create(
                program_key=key,
                defaults={**defaults, "name": key, "sort_order": order},
            )

    def test_home_contains_three_program_choices(self):
        response = self.client.get(reverse("website:home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["landing_programs"]), 3)

    def test_each_focused_landing_page_resolves(self):
        for name in (
            "website:cambridge_landing",
            "website:ielts_landing",
            "website:uk_interview_landing",
        ):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
