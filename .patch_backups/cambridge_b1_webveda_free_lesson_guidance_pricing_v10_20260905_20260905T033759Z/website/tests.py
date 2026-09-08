from collections import Counter
from html.parser import HTMLParser

from django.test import TestCase
from django.urls import reverse

from .models import PublicProgramLanding, PublicSiteSettings


class LandingMarkupAudit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.fragments = []
        self.empty_links = []
        self.controls = []
        self.h1_count = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.append(attributes["id"])
        if tag == "h1":
            self.h1_count += 1
        if tag == "a" and "href" in attributes:
            href = attributes["href"].strip()
            if href.startswith("#") and len(href) > 1:
                self.fragments.append(href[1:])
            if not href or href == "#":
                self.empty_links.append(href)
        if "aria-controls" in attributes:
            self.controls.append(attributes["aria-controls"])


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
        self.assertContains(response, "Daily 2-hour live class")
        self.assertContains(response, "Israel Caregiver G to G candidates")
        self.assertContains(response, "b1x-whatsapp")
        self.assertContains(response, "b1x-mid-cta")
        self.assertContains(response, "data-b1-sticky-cta")
        self.assertContains(response, "b1-hero-studio-v2.webp")
        self.assertContains(response, "b1x-hero-person-mobile")
        self.assertContains(response, "b1x-hero-features")
        self.assertContains(response, "Step-by-Step")
        self.assertContains(response, "Real Exam-Style")
        self.assertContains(response, "AI + Personal")
        self.assertNotContains(response, "b1x-hero-levels")
        self.assertContains(response, "Message From Your")
        self.assertContains(response, "1,000+ Learners")
        self.assertContains(response, "Become a Arya Member")
        self.assertContains(response, "THE COMPLETE B1 SYSTEM")
        self.assertContains(response, "Recorded Lessons")
        self.assertContains(response, "Real Exam Practice")
        self.assertContains(response, "Weekly Feedback")
        self.assertContains(response, "Recorded Lessons, Mock Tests &amp; Weekly Feedback")
        self.assertContains(response, "Get Everything You Need for B1")
        self.assertContains(response, "Exclusive Cambridge")
        self.assertContains(response, "Upskill B1 Preparation")
        self.assertContains(response, "Cambridge Upskill English Test")
        self.assertContains(response, "What is the Upskill test and CEFR?")
        self.assertContains(response, "Bonus Grammar + Caregiver Support")
        self.assertContains(response, "Practice The Exam")
        self.assertContains(response, "Before You Face The Exam")
        self.assertContains(response, "500+ Questions")
        self.assertContains(response, "Mock Result Certificate")
        self.assertContains(response, "b1-mock-portal-reference.jpeg")
        self.assertContains(response, "The B1 Ready Promise")
        self.assertContains(response, "Unlimited Mock Practice")
        self.assertContains(response, "Live Feedback Every Week")
        self.assertContains(response, "Speaking B1")
        self.assertContains(response, "Stop Guessing")
        self.assertContains(response, "Don’t Just Practise")
        self.assertContains(response, "Step-by-Step B1 Course")
        self.assertContains(response, "14-Day Refund Policy")
        self.assertContains(response, "Class continuation promise")
        self.assertContains(response, "A complete")
        self.assertContains(response, "Get Feedback")
        self.assertNotContains(response, "Real preparation problems")
        self.assertNotContains(response, 'class="b1x-truth"')
        self.assertNotContains(response, '<section class="b1x-coach">')
        self.assertNotContains(response, "Independent preparation and mock testing platform")
        self.assertNotContains(response, "IELTS")
        self.assertNotContains(response, "UKVI")

    def test_main_home_has_root_canonical_url(self):
        response = self.client.get(reverse("public_home"))
        self.assertContains(response, '<link rel="canonical" href="http://testserver/">')

    def test_landing_markup_has_valid_local_targets(self):
        response = self.client.get(reverse("public_home"))
        audit = LandingMarkupAudit()
        audit.feed(response.content.decode())
        id_counts = Counter(audit.ids)

        self.assertEqual(audit.h1_count, 1)
        self.assertEqual([key for key, count in id_counts.items() if count > 1], [])
        self.assertEqual(set(audit.fragments) - set(audit.ids), set())
        self.assertEqual(set(audit.controls) - set(audit.ids), set())
        self.assertEqual(audit.empty_links, [])

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
