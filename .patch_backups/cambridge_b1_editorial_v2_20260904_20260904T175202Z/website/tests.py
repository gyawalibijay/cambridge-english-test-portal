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

    def test_home_is_the_cambridge_b1_landing_page(self):
        response = self.client.get(reverse("website:home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "website/cambridge_b1_landing.html")
        self.assertEqual(response.context["landing"].program_key, "cambridge-english")
        self.assertContains(response, "B1 सम्भव छ")
        self.assertContains(response, "cambridge-b1-webveda.css")
        self.assertNotContains(response, "IELTS")
        self.assertNotContains(response, "UKVI")

    def test_main_home_has_root_canonical_url(self):
        response = self.client.get(reverse("public_home"))
        self.assertContains(response, '<link rel="canonical" href="http://testserver/">')

    def test_legacy_product_marketing_urls_redirect_to_main_home(self):
        for name in (
            "website:cambridge_landing",
            "website:ielts_landing",
            "website:uk_interview_landing",
        ):
            response = self.client.get(reverse(name))
            self.assertRedirects(
                response,
                reverse("public_home"),
                status_code=301,
                fetch_redirect_response=False,
            )

    def test_sitemap_only_promotes_cambridge_home(self):
        response = self.client.get(reverse("website:sitemap_xml"))
        self.assertContains(response, "http://testserver/")
        self.assertNotContains(response, "/cambridge-english/")
        self.assertNotContains(response, "/ielts/")
        self.assertNotContains(response, "/uk-interview/")
