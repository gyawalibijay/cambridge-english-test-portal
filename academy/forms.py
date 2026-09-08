from django import forms
from django.utils.text import slugify

from .models import Course, CourseMaterial, TestMaterial
from .permissions import allowed_programs


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            "program",
            "title",
            "slug",
            "short_description",
            "description",
            "thumbnail",
            "sort_order",
            "is_published",
        ]
        widgets = {
            "program": forms.Select(
                attrs={"class": "pv2-input"}
            ),
            "title": forms.TextInput(
                attrs={"class": "pv2-input"}
            ),
            "slug": forms.TextInput(
                attrs={
                    "class": "pv2-input",
                    "placeholder": "auto-generated-if-empty",
                }
            ),
            "short_description": forms.TextInput(
                attrs={"class": "pv2-input"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "pv2-input",
                    "rows": 6,
                }
            ),
            "thumbnail": forms.ClearableFileInput(
                attrs={
                    "class": "pv2-input",
                    "accept": "image/*",
                }
            ),
            "sort_order": forms.NumberInput(
                attrs={"class": "pv2-input"}
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["program"].queryset = (
            allowed_programs(user)
            if user
            else self.fields["program"].queryset.none()
        )

    def clean_slug(self):
        slug = self.cleaned_data.get("slug")

        if slug:
            return slugify(slug)

        title = self.cleaned_data.get("title", "")
        return slugify(title)


class CourseMaterialForm(forms.ModelForm):
    class Meta:
        model = CourseMaterial
        fields = [
            "course",
            "skill",
            "material_type",
            "title",
            "description",
            "content_text",
            "file",
            "audio_file",
            "external_url",
            "sort_order",
            "is_published",
        ]
        widgets = {
            "course": forms.Select(
                attrs={"class": "pv2-input"}
            ),
            "skill": forms.Select(
                attrs={"class": "pv2-input"}
            ),
            "material_type": forms.Select(
                attrs={"class": "pv2-input"}
            ),
            "title": forms.TextInput(
                attrs={"class": "pv2-input"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "pv2-input",
                    "rows": 4,
                }
            ),
            "content_text": forms.Textarea(
                attrs={
                    "class": "pv2-input",
                    "rows": 8,
                }
            ),
            "file": forms.ClearableFileInput(
                attrs={"class": "pv2-input"}
            ),
            "audio_file": forms.ClearableFileInput(
                attrs={
                    "class": "pv2-input",
                    "accept": "audio/*",
                }
            ),
            "external_url": forms.URLInput(
                attrs={"class": "pv2-input"}
            ),
            "sort_order": forms.NumberInput(
                attrs={"class": "pv2-input"}
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user:
            program_ids = allowed_programs(
                user
            ).values_list("id", flat=True)

            self.fields["course"].queryset = (
                Course.objects
                .filter(
                    program_id__in=program_ids
                )
                .order_by(
                    "program__name",
                    "title",
                )
            )


class TestMaterialForm(forms.ModelForm):
    class Meta:
        model = TestMaterial
        fields = [
            "program",
            "course",
            "skill",
            "title",
            "instructions",
            "passage_text",
            "prompt_text",
            "transcript",
            "audio_file",
            "attachment",
            "answer_key",
            "source_note",
            "is_published",
            "is_question_bank_ready",
        ]
        widgets = {
            "program": forms.Select(
                attrs={"class": "pv2-input"}
            ),
            "course": forms.Select(
                attrs={"class": "pv2-input"}
            ),
            "skill": forms.Select(
                attrs={"class": "pv2-input"}
            ),
            "title": forms.TextInput(
                attrs={"class": "pv2-input"}
            ),
            "instructions": forms.Textarea(
                attrs={
                    "class": "pv2-input",
                    "rows": 4,
                }
            ),
            "passage_text": forms.Textarea(
                attrs={
                    "class": "pv2-input",
                    "rows": 8,
                }
            ),
            "prompt_text": forms.Textarea(
                attrs={
                    "class": "pv2-input",
                    "rows": 8,
                }
            ),
            "transcript": forms.Textarea(
                attrs={
                    "class": "pv2-input",
                    "rows": 8,
                }
            ),
            "audio_file": forms.ClearableFileInput(
                attrs={
                    "class": "pv2-input",
                    "accept": "audio/*",
                }
            ),
            "attachment": forms.ClearableFileInput(
                attrs={"class": "pv2-input"}
            ),
            "answer_key": forms.Textarea(
                attrs={
                    "class": "pv2-input",
                    "rows": 6,
                }
            ),
            "source_note": forms.TextInput(
                attrs={"class": "pv2-input"}
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user:
            programs = allowed_programs(user)

            self.fields["program"].queryset = programs
            self.fields["course"].queryset = (
                Course.objects
                .filter(
                    program__in=programs
                )
                .order_by(
                    "program__name",
                    "title",
                )
            )
