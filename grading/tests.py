from django.test import SimpleTestCase

from .b1_speaking import (
    build_insufficient_item_assessment,
    build_item_assessment,
)


class B1SpeakingSpecificationTests(SimpleTestCase):
    def test_short_valid_part_one_answer_is_not_penalised_for_brevity(self):
        result = build_item_assessment(
            question="How do you travel to work?",
            transcript="By bus.",
            part_order=1,
            duration=2.0,
            silence_seconds=0.2,
            asr_confidence=0.94,
            mean_db=-24.0,
        )
        self.assertGreaterEqual(
            result["criteria"]["task_achievement"]["score"],
            3.0,
        )

    def test_read_aloud_does_not_score_productive_language(self):
        result = build_item_assessment(
            question="The meeting starts at nine tomorrow morning.",
            transcript="The meeting starts at nine tomorrow morning.",
            part_order=3,
            duration=4.0,
            silence_seconds=0.2,
            asr_confidence=0.95,
            mean_db=-24.0,
        )
        self.assertIsNone(result["criteria"]["grammar"]["score"])
        self.assertIsNone(result["criteria"]["vocabulary"]["score"])
        self.assertIsNone(result["criteria"]["coherence"]["score"])

    def test_unusable_audio_is_insufficient_evidence_not_zero(self):
        result = build_insufficient_item_assessment(
            transcript="",
            part_order=2,
            duration=0.2,
            silence_ratio=1.0,
            asr_confidence=None,
            mean_db=-60.0,
            reasons=["No spoken words were detected."],
        )
        self.assertEqual(result["assessment_status"], "INSUFFICIENT_EVIDENCE")
        self.assertIsNone(result["score_total"])
