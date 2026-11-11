"""Offline boundary and adversarial tests; fake HTTP replies are NOT model runs."""
import json
from unittest.mock import patch
import unittest

from saturn_ai.grounding.saturn_claim_contracts import (
    SaturnGenerationEvidence, SaturnGenerationNeed, SaturnGenerationRequest,
    SaturnClaimDraft,
)
from saturn_ai.grounding.saturn_local_provider import (
    SaturnLocalClaimProvider, SaturnLocalModelConfig, LocalModelError,
)
from saturn_ai.grounding.saturn_generation import SaturnClaimVerificationService
from saturn_ai.grounding.saturn_answer_assembly import SaturnAnswerAssemblyService
from saturn_ai.evaluation.saturn_fixture import fixture_snapshot
from saturn_ai.retrieval.saturn_channel import SaturnRetrievalService, build_saturn_retrieval_bundle


CONFIG = SaturnLocalModelConfig(
    "http://127.0.0.1:11434/v1/chat/completions",
    "qwen-test-local", "a" * 64, timeout_seconds=5, max_completion_tokens=256,
)


def sample_request():
    return SaturnGenerationRequest(
        "b" * 64, "c" * 64, "d" * 64, "policy-test",
        (SaturnGenerationNeed("need", "field_value", "owner", "interfaces", None, None),),
        (SaturnGenerationEvidence(
            "need", "evidence", "site_field", "revision", "owner",
            "fact", "interfaces", '["RS-485"]', None, None,
            None, None, None, None, None, None, "interfaces: RS-485",
        ),),
    )


def completion(claims, *, model="qwen-test-local", reason="stop"):
    return json.dumps({
        "model": model, "choices": [{"finish_reason": reason,
            "message": {"content": json.dumps({"claims": claims})}}],
    }).encode("utf-8")


class LocalProviderContractTests(unittest.TestCase):
    def test_exact_loopback_and_digest_required(self):
        for url in (
            "https://127.0.0.1:11434/v1/chat/completions",
            "http://localhost:11434/v1/chat/completions",
            "http://example.com:11434/v1/chat/completions",
            "http://127.0.0.2:11434/v1/chat/completions",
            "http://127.0.0.1:11434/other",
            "http://127.0.0.1:11434/v1/chat/completions?x=y",
            "http://user:pass@127.0.0.1:11434/v1/chat/completions",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                SaturnLocalModelConfig(url, "test-model", "b" * 64)
        with self.assertRaisesRegex(ValueError, "digest_required"):
            SaturnLocalModelConfig(CONFIG.endpoint, "test-model", "")

    def test_valid_untrusted_draft_shape_and_no_source_urls(self):
        item = {"need_id": "need", "evidence_id": "evidence",
                "claim_kind": "field_value", "asserted_payload": "{}"}
        received = []
        def stub(config, payload):
            received.append(json.loads(payload))
            return completion([item])
        with patch("saturn_ai.grounding.saturn_local_provider._post_loopback", stub):
            answer = SaturnLocalClaimProvider(CONFIG).generate(sample_request())
        self.assertEqual(answer, (SaturnClaimDraft(**item),))
        self.assertEqual(received[0]["model"], CONFIG.model_id)
        self.assertEqual(received[0]["temperature"], 0)
        self.assertFalse(received[0]["stream"])
        self.assertNotIn("https://", received[0]["messages"][1]["content"])
        self.assertNotIn("api_key", json.dumps(received[0]))

    def test_fail_closed_on_malformed_responses_and_extra_claims(self):
        bad = [
            b"{oops",
            completion([], model="other-model"),
            completion([], reason="length"),
            completion([{"need_id":"need"}]),
            completion([{"need_id":"need","evidence_id":"evidence",
                         "claim_kind":"field_value","asserted_payload":"x"}] * 7),
        ]
        for raw in bad:
            with self.subTest(raw=raw[:35]), patch(
                    "saturn_ai.grounding.saturn_local_provider._post_loopback",
                    return_value=raw):
                with self.assertRaises(LocalModelError):
                    SaturnLocalClaimProvider(CONFIG).generate(sample_request())

    def test_bad_provider_cannot_force_verified_technical_answer(self):
        snap = fixture_snapshot()
        service = SaturnRetrievalService()
        service.publish(build_saturn_retrieval_bundle(snap))
        provider = SaturnLocalClaimProvider(CONFIG)
        verifier = SaturnClaimVerificationService(provider=provider)
        assembly = SaturnAnswerAssemblyService(verifier=verifier)
        bad = {"need_id": "forged_need", "evidence_id": "forged_evidence",
               "claim_kind": "field_value", "asserted_payload": "fabricated"}
        with patch("saturn_ai.grounding.saturn_local_provider._post_loopback",
                   return_value=completion([bad])):
            with service.open_answer_session() as session:
                context = session.build_context(
                    "Device X: interface?", mode="lexical", top_k=10)
                result = assembly.assemble(session=session, context=context)
        self.assertNotEqual(result.status, "answered")
        self.assertEqual(len(result.citations), 0)

    def test_provider_failure_becomes_error_not_refusal(self):
        snap = fixture_snapshot()
        service = SaturnRetrievalService()
        service.publish(build_saturn_retrieval_bundle(snap))
        verifier = SaturnClaimVerificationService(provider=SaturnLocalClaimProvider(CONFIG))
        assembly = SaturnAnswerAssemblyService(verifier=verifier)
        with patch("saturn_ai.grounding.saturn_local_provider._post_loopback",
                   side_effect=LocalModelError("unavailable")):
            with service.open_answer_session() as session:
                context = session.build_context(
                    "Device X: interface?", mode="lexical", top_k=10)
                result = assembly.assemble(session=session, context=context)
        self.assertEqual(result.status, "error")
        self.assertEqual(len(result.citations), 0)


if __name__ == "__main__":
    unittest.main()
