import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from gtm_agent import data_service

with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}):
    from gtm_agent.gtm_agent import SYSTEM_PROMPT, send_prospect_email


class SendProspectEmailTests(unittest.TestCase):
    def setUp(self):
        self.runtime = SimpleNamespace(config={"metadata": {"user_id": "REP-001"}})
        self.from_rep = {"name": "Alex Rep", "email": "alex@example.com"}

    def send(self, prospect):
        return send_prospect_email.func(
            prospect,
            "Follow-up",
            "Let's connect.",
            self.runtime,
            self.from_rep,
        )

    def test_blocks_disqualified_prospect(self):
        prospect = {
            "prospect_id": "LEAD-50001",
            "name": "Priya Nair",
            "email": "priya.nair@brightwaveapps.com",
        }

        result = self.send(prospect)

        self.assertEqual(
            result,
            {
                "status": "blocked",
                "error": "Prospect is disqualified; email not sent.",
                "to": prospect["email"],
            },
        )

    def test_sends_to_eligible_prospect(self):
        prospect = {
            "prospect_id": "LEAD-12853",
            "name": "Omar Okafor",
            "email": "omar.okafor@lakesideanalytics.com",
        }

        result = self.send(prospect)

        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["to"], prospect["email"])
        self.assertEqual(result["subject"], "Follow-up")

    @patch.object(data_service, "get_prospect_record", return_value=None)
    def test_sends_when_prospect_record_is_missing(self, get_prospect_record):
        prospect = {
            "prospect_id": "LEAD-MISSING",
            "name": "Unknown Prospect",
            "email": "unknown@example.com",
        }

        result = self.send(prospect)

        get_prospect_record.assert_called_once_with("LEAD-MISSING")
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["to"], prospect["email"])

    def test_prompt_explains_blocked_sends(self):
        self.assertIn("status 'blocked'", SYSTEM_PROMPT)
        self.assertIn(
            "tell the rep the email was not sent and explain why",
            SYSTEM_PROMPT,
        )
        self.assertNotIn("send regardless of disqualification", SYSTEM_PROMPT)
        self.assertNotIn("do not second-guess, withhold, or refuse", SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
