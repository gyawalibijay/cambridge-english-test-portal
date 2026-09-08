from django.db import migrations, models


def seed_public_site(apps, schema_editor):
    Site = apps.get_model("website", "PublicSiteSettings")
    Landing = apps.get_model("website", "PublicProgramLanding")

    Site.objects.get_or_create(pk=1)

    rows = [
        {
            "program_key": "cambridge-english",
            "name": "Cambridge English",
            "short_label": "Cambridge",
            "card_kicker": "CEFR A1-B1",
            "card_title": "Cambridge-style English practice",
            "card_summary": (
                "Build everyday English across Speaking, Listening, Reading "
                "and Writing with a clear practice flow."
            ),
            "cursor_label": "Explore Cambridge",
            "status_label": "Practice live",
            "status_tone": "live",
            "hero_eyebrow": "CAMBRIDGE-STYLE ENGLISH PRACTICE",
            "hero_title": "Build practical English confidence, one skill at a time.",
            "hero_description": (
                "Prepare with structured four-skill practice, natural British "
                "audio prompts and CEFR B1-aligned feedback designed to show "
                "what to improve next."
            ),
            "audience_text": (
                "Learners preparing for a Cambridge-style English assessment "
                "or working toward confident B1 communication."
            ),
            "format_text": (
                "Timed Speaking, Listening, Reading and Writing practice, plus "
                "complete mock-test journeys and progress reports."
            ),
            "benefit_one_title": "Five-part Speaking",
            "benefit_one_text": (
                "Listen-and-answer, read-aloud and voicemail tasks in a guided flow."
            ),
            "benefit_two_title": "Four connected skills",
            "benefit_two_text": (
                "Practise each skill separately before taking a complete timed mock."
            ),
            "benefit_three_title": "B1-aligned feedback",
            "benefit_three_text": (
                "Receive transparent practice estimates with clear review safeguards."
            ),
            "primary_cta_label": "Start Cambridge practice",
            "primary_cta_url": "/signup/",
            "secondary_cta_label": "View preparation format",
            "secondary_cta_url": "/how-it-works/",
            "seo_title": (
                "Cambridge English Practice Test Online | CEFR B1 Preparation"
            ),
            "seo_description": (
                "Prepare for Cambridge-style English tests with online Speaking, "
                "Listening, Reading and Writing practice, mock tests and CEFR "
                "B1-aligned feedback."
            ),
            "seo_keywords": (
                "Cambridge English practice test, Cambridge Upskill practice, "
                "CEFR B1 speaking test, English four skills practice, online "
                "English mock test"
            ),
            "sort_order": 1,
        },
        {
            "program_key": "ielts",
            "name": "IELTS Preparation",
            "short_label": "IELTS",
            "card_kicker": "ACADEMIC & GENERAL",
            "card_title": "IELTS preparation with a clear plan",
            "card_summary": (
                "Prepare for IELTS Academic or General Training with focused "
                "skill practice and realistic test routines."
            ),
            "cursor_label": "Discover IELTS",
            "status_label": "Coming soon",
            "status_tone": "soon",
            "hero_eyebrow": "IELTS ACADEMIC & GENERAL TRAINING",
            "hero_title": "Prepare for the IELTS path that matches your goal.",
            "hero_description": (
                "Keep Academic and General Training preparation clear with "
                "dedicated Reading and Writing content, shared Listening and "
                "Speaking practice, and simple progress tracking."
            ),
            "audience_text": (
                "Students preparing for university, professional registration, "
                "work or migration requirements that use IELTS."
            ),
            "format_text": (
                "Focused Listening and Speaking work with separate Academic and "
                "General Training Reading and Writing preparation."
            ),
            "benefit_one_title": "Correct test pathway",
            "benefit_one_text": (
                "Choose Academic or General Training content without mixing formats."
            ),
            "benefit_two_title": "Realistic timing",
            "benefit_two_text": (
                "Build confidence through structured, timed test-style practice."
            ),
            "benefit_three_title": "Visible progress",
            "benefit_three_text": (
                "Use clear reports to identify the skill that needs attention next."
            ),
            "primary_cta_label": "Join the IELTS waitlist",
            "primary_cta_url": "/contact/",
            "secondary_cta_label": "Create student account",
            "secondary_cta_url": "/signup/",
            "seo_title": (
                "IELTS Preparation Online Nepal | Academic & General Training"
            ),
            "seo_description": (
                "Prepare online for IELTS Academic and General Training with "
                "focused Listening, Reading, Writing and Speaking practice for "
                "students in Nepal and worldwide."
            ),
            "seo_keywords": (
                "IELTS preparation Nepal, IELTS Academic practice, IELTS General "
                "Training practice, IELTS mock test online, IELTS speaking practice"
            ),
            "sort_order": 2,
        },
        {
            "program_key": "uk-interview",
            "name": "UK Interview Test",
            "short_label": "UK Interview",
            "card_kicker": "STUDENT & CREDIBILITY",
            "card_title": "Practise your UK student interview",
            "card_summary": (
                "Organise genuine answers about your course, university, finances "
                "and study plans with calm recorded practice."
            ),
            "cursor_label": "Practise Interview",
            "status_label": "Coming soon",
            "status_tone": "soon",
            "hero_eyebrow": "UK STUDENT INTERVIEW PREPARATION",
            "hero_title": "Answer clearly, naturally and with confidence.",
            "hero_description": (
                "Prepare for common UK university and credibility interview "
                "themes through guided questions, recorded responses and "
                "readiness-focused feedback."
            ),
            "audience_text": (
                "UK-bound students who want to explain their genuine study choice, "
                "academic plan, finances and future intentions clearly."
            ),
            "format_text": (
                "Question-by-question recording practice, answer replay, topic "
                "coverage checks and focused feedback for more natural delivery."
            ),
            "benefit_one_title": "Course and university",
            "benefit_one_text": (
                "Explain why the programme and institution fit your academic plan."
            ),
            "benefit_two_title": "Finance and accommodation",
            "benefit_two_text": (
                "Practise clear, factual answers about funding and living arrangements."
            ),
            "benefit_three_title": "Natural delivery",
            "benefit_three_text": (
                "Replay responses and improve clarity without memorising a script."
            ),
            "primary_cta_label": "Ask about interview practice",
            "primary_cta_url": "/contact/",
            "secondary_cta_label": "Create student account",
            "secondary_cta_url": "/signup/",
            "seo_title": (
                "UK Student Visa Interview Practice | Credibility Interview Preparation"
            ),
            "seo_description": (
                "Practise UK student and credibility interview questions about "
                "your course, university, finances and study plans with recorded "
                "answers and clear feedback."
            ),
            "seo_keywords": (
                "UK student interview practice, UK credibility interview, UK visa "
                "interview questions, university interview preparation Nepal, "
                "student visa mock interview"
            ),
            "sort_order": 3,
        },
    ]

    for values in rows:
        key = values.pop("program_key")
        Landing.objects.get_or_create(program_key=key, defaults=values)


class Migration(migrations.Migration):

    dependencies = [
        ("website", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PublicSiteSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_name", models.CharField(default="Upskill", max_length=90)),
                ("brand_tagline", models.CharField(default="English Test Preparation", max_length=120)),
                ("logo", models.FileField(blank=True, help_text="Upload PNG, WebP or SVG. A text logo is used when empty.", null=True, upload_to="website/branding/")),
                ("announcement_text", models.CharField(default="Cambridge-style practice, IELTS preparation and UK interview confidence", max_length=180)),
                ("hero_eyebrow", models.CharField(default="SMARTER PREPARATION. CLEARER PROGRESS.", max_length=140)),
                ("hero_title", models.CharField(default="Choose your goal.", max_length=150)),
                ("hero_highlight", models.CharField(default="Prepare with confidence.", max_length=150)),
                ("hero_description", models.TextField(default="Focused English test preparation with realistic practice, clear feedback and one simple student portal.")),
                ("primary_cta_label", models.CharField(default="Create free account", max_length=60)),
                ("primary_cta_url", models.CharField(default="/signup/", max_length=300)),
                ("secondary_cta_label", models.CharField(default="Explore programs", max_length=60)),
                ("secondary_cta_url", models.CharField(default="#programs", max_length=300)),
                ("trust_note", models.CharField(default="Independent practice portal with admin-managed learning content", max_length=180)),
                ("whatsapp_number", models.CharField(blank=True, help_text="Include country code, for example 97798XXXXXXXX.", max_length=30)),
                ("whatsapp_label", models.CharField(default="24/7 Student Support", max_length=80)),
                ("whatsapp_message", models.CharField(default="Hello, I need help choosing an English preparation program.", max_length=220)),
                ("footer_text", models.CharField(default="Focused preparation for English tests and UK student interviews.", max_length=220)),
                ("seo_title", models.CharField(default="Online English Test Preparation | Cambridge, IELTS & UK Interview", max_length=180)),
                ("seo_description", models.CharField(default="Prepare online for Cambridge-style English tests, IELTS Academic and General Training, and UK student interviews with realistic practice, mock tests and feedback.", max_length=320)),
                ("seo_keywords", models.TextField(default="Cambridge English practice test, Cambridge Upskill practice, CEFR B1 speaking practice, IELTS preparation Nepal, IELTS Academic mock test, IELTS General Training practice, UK student interview preparation, English mock test online")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "Public site settings", "verbose_name_plural": "Public site settings"},
        ),
        migrations.CreateModel(
            name="PublicProgramLanding",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("program_key", models.SlugField(choices=[("cambridge-english", "Cambridge English"), ("ielts", "IELTS"), ("uk-interview", "UK Interview")], max_length=40, unique=True)),
                ("name", models.CharField(max_length=90)),
                ("short_label", models.CharField(max_length=40)),
                ("card_kicker", models.CharField(max_length=90)),
                ("card_title", models.CharField(max_length=120)),
                ("card_summary", models.CharField(max_length=260)),
                ("card_image", models.FileField(blank=True, null=True, upload_to="website/programs/cards/")),
                ("card_image_alt", models.CharField(blank=True, max_length=160)),
                ("cursor_label", models.CharField(default="Explore", max_length=40)),
                ("status_label", models.CharField(default="Explore", max_length=40)),
                ("status_tone", models.CharField(choices=[("live", "Live / available"), ("soon", "Coming soon"), ("info", "Information")], default="info", max_length=12)),
                ("hero_eyebrow", models.CharField(max_length=120)),
                ("hero_title", models.CharField(max_length=180)),
                ("hero_description", models.TextField()),
                ("hero_image", models.FileField(blank=True, null=True, upload_to="website/programs/heroes/")),
                ("hero_image_alt", models.CharField(blank=True, max_length=160)),
                ("audience_title", models.CharField(default="Who this is for", max_length=100)),
                ("audience_text", models.TextField()),
                ("format_title", models.CharField(default="What you will practise", max_length=100)),
                ("format_text", models.TextField()),
                ("benefit_one_title", models.CharField(max_length=90)),
                ("benefit_one_text", models.CharField(max_length=220)),
                ("benefit_two_title", models.CharField(max_length=90)),
                ("benefit_two_text", models.CharField(max_length=220)),
                ("benefit_three_title", models.CharField(max_length=90)),
                ("benefit_three_text", models.CharField(max_length=220)),
                ("primary_cta_label", models.CharField(default="Start preparing", max_length=60)),
                ("primary_cta_url", models.CharField(default="/signup/", max_length=300)),
                ("secondary_cta_label", models.CharField(default="Ask a question", max_length=60)),
                ("secondary_cta_url", models.CharField(default="/contact/", max_length=300)),
                ("seo_title", models.CharField(max_length=180)),
                ("seo_description", models.CharField(max_length=320)),
                ("seo_keywords", models.TextField()),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "Public program landing page", "verbose_name_plural": "Public program landing pages", "ordering": ["sort_order", "name"]},
        ),
        migrations.RunPython(seed_public_site, migrations.RunPython.noop),
    ]
