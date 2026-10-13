import json
import unittest
from unittest.mock import patch

from gtm_agent import data_service
from gtm_agent.gtm_records import OFFERINGS, PROSPECTS

with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
    from gtm_agent.gtm_agent import (
        ProspectScore,
        RubricBreakdown,
        build_prospect_profile,
        score_prospect,
    )


class UpdateProspectInfoTests(unittest.TestCase):
    prospect_id = "LEAD-71001"

    def setUp(self):
        record = PROSPECTS[self.prospect_id]
        original_stack = list(record["tech_stack"])
        original_profile = data_service._PROFILES.get(self.prospect_id)
        had_profile = self.prospect_id in data_service._PROFILES

        def restore_state():
            record["tech_stack"] = original_stack
            if had_profile:
                data_service._PROFILES[self.prospect_id] = original_profile
            else:
                data_service._PROFILES.pop(self.prospect_id, None)

        self.addCleanup(restore_state)
        data_service._PROFILES.pop(self.prospect_id, None)

    def test_update_persists_and_returns_source_stack(self):
        result = data_service.update_prospect_info(self.prospect_id, "Kafka")

        self.assertTrue(result["updated"])
        self.assertEqual(result["tech_stack"], data_service.fetch_tech_stack(self.prospect_id))
        self.assertIn("Kafka", data_service.fetch_tech_stack(self.prospect_id))

        duplicate_result = data_service.update_prospect_info(self.prospect_id, "Kafka")
        self.assertEqual(duplicate_result["tech_stack"].count("Kafka"), 1)

    def test_update_invalidates_cached_profile(self):
        data_service.save_profile_to_db(self.prospect_id, {"tech_stack": ["stale"]})

        data_service.update_prospect_info(self.prospect_id, "Kafka")

        self.assertIsNone(data_service.get_profile_from_db(self.prospect_id)["prospect_profile"])

    def test_missing_prospect_behavior_is_preserved(self):
        self.assertEqual(
            data_service.update_prospect_info("LEAD-MISSING", "Kafka"),
            {"updated": False, "found": False},
        )

    def test_rebuild_and_rescore_use_updated_source_stack(self):
        initial_profile = build_prospect_profile.invoke({"prospect_id": self.prospect_id})[
            "prospect_profile"
        ]
        self.assertNotIn("Kafka", initial_profile["tech_stack"])

        data_service.update_prospect_info(self.prospect_id, "Kafka")
        profile = build_prospect_profile.invoke({"prospect_id": self.prospect_id})[
            "prospect_profile"
        ]
        score = ProspectScore(
            score=80,
            justification="Updated source stack was supplied.",
            rubric_breakdown=RubricBreakdown(
                revenue_fit=80,
                tech_stack_match=80,
                segment_fit=80,
            ),
        )

        with patch("gtm_agent.gtm_agent._scoring_llm") as scoring_llm:
            scoring_llm.invoke.return_value = score
            score_prospect.invoke(
                {"prospect_profile": profile, "offering": OFFERINGS["OFFER-10001"]}
            )

        score_request = scoring_llm.invoke.call_args.args[0][1]["content"]
        scored_profile = json.loads(score_request.split("\n\nProspect profile:\n", 1)[1])
        self.assertIn("Kafka", scored_profile["tech_stack"])


if __name__ == "__main__":
    unittest.main()
