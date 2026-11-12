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
            need_id="need", evidence_id="evidence", evidence_type="site_field",
            source_revision_id="revision", entity_id="owner", fact_id="fact",
            field_path="interfaces", raw_value_json='["RS-485"]',
            unit=None, qualifiers_json=None, relation_id=None,
            subject_entity_id=None, predicate=None, object_entity_id=None,
            source_field_path=None, source_text="interfaces: RS-485",
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


class TokenUsageIsolationTests(unittest.TestCase):
    """CR-07: mocked responses are NOT real LLM inference measurements."""

    @staticmethod
    def reply(usage_marker=None, *, include_usage=True):
        result = {
            "model": CONFIG.model_id,
            "choices": [{"finish_reason": "stop",
                         "message": {"content": json.dumps({"claims": []})}}],
        }
        if include_usage:
            result["usage"] = usage_marker
        return json.dumps(result).encode("utf-8")

    def test_CR07_T01_successful_response_has_its_own_usage(self):
        provider = SaturnLocalClaimProvider(CONFIG)
        with patch("saturn_ai.grounding.saturn_local_provider._post_loopback",
                   return_value=self.reply({
                       "prompt_tokens": 7, "completion_tokens": 4,
                       "total_tokens": 11})):
            self.assertEqual(provider.generate(sample_request()), ())
        self.assertEqual(provider.last_usage, {
            "prompt_tokens": 7, "completion_tokens": 4, "total_tokens": 11})
        self.assertEqual(provider.successful_requests, 1)
        self.assertEqual(len(provider.latencies_ms), 1)

    def test_CR07_T02_prior_usage_cleared_when_next_reply_omits_usage(self):
        provider = SaturnLocalClaimProvider(CONFIG)
        with patch("saturn_ai.grounding.saturn_local_provider._post_loopback",
                   side_effect=[
                       self.reply({"prompt_tokens": 7, "total_tokens": 7}),
                       self.reply(include_usage=False)]):
            provider.generate(sample_request())
            self.assertIsNotNone(provider.last_usage)
            provider.generate(sample_request())
        self.assertIsNone(provider.last_usage)
        self.assertEqual(provider.successful_requests, 2)
        self.assertEqual(len(provider.latencies_ms), 2)

    def test_CR07_T03_invalid_or_partial_usage_is_unmeasured(self):
        invalid = (
            {"prompt_tokens": -1},
            {"prompt_tokens": True},
            {"prompt_tokens": "7"},
            {"prompt_tokens": 4, "total_tokens": -4},
            {"unknown": 2},
            {},
            [], 0, None,
        )
        for value in invalid:
            with self.subTest(value=value):
                provider = SaturnLocalClaimProvider(CONFIG)
                with patch("saturn_ai.grounding.saturn_local_provider._post_loopback",
                           side_effect=[
                               self.reply({"prompt_tokens": 5}),
                               self.reply(value)]):
                    provider.generate(sample_request())
                    provider.generate(sample_request())
                self.assertIsNone(provider.last_usage)
                self.assertEqual(provider.successful_requests, 2)

    def test_CR07_T04_failure_after_success_does_not_retain_usage(self):
        provider = SaturnLocalClaimProvider(CONFIG)
        with patch("saturn_ai.grounding.saturn_local_provider._post_loopback",
                   side_effect=[
                       self.reply({"prompt_tokens": 13}),
                       LocalModelError("unavailable")]):
            provider.generate(sample_request())
            self.assertEqual(provider.last_usage, {"prompt_tokens": 13})
            with self.assertRaises(LocalModelError):
                provider.generate(sample_request())
        self.assertIsNone(provider.last_usage)
        self.assertEqual(provider.successful_requests, 1)
        self.assertEqual(len(provider.latencies_ms), 1)

    def test_CR07_T05_latency_and_success_count_only_valid_responses(self):
        provider = SaturnLocalClaimProvider(CONFIG)
        with patch("saturn_ai.grounding.saturn_local_provider._post_loopback",
                   side_effect=[
                       self.reply({"prompt_tokens": 2}),
                       self.reply(include_usage=False),
                       self.reply({"prompt_tokens": -1}),
                       b"{malformed"]):
            for _ in range(3):
                provider.generate(sample_request())
            with self.assertRaises(LocalModelError):
                provider.generate(sample_request())
        self.assertEqual(provider.successful_requests, 3)
        self.assertEqual(len(provider.latencies_ms), 3)
        self.assertTrue(all(type(ms) is float and ms >= 0
                            for ms in provider.latencies_ms))
        self.assertIsNone(provider.last_usage)

    def test_CR07_T06_unchanged_backend_verifier_rejects_forged_claim(self):
        snapshot = fixture_snapshot()
        service = SaturnRetrievalService()
        service.publish(build_saturn_retrieval_bundle(snapshot))
        provider = SaturnLocalClaimProvider(CONFIG)
        verifier = SaturnClaimVerificationService(provider=provider)
        assembly = SaturnAnswerAssemblyService(verifier=verifier)
        forged = {
            "need_id": "forged_need", "evidence_id": "forged_evidence",
            "claim_kind": "field_value", "asserted_payload": "fake",
        }
        with patch("saturn_ai.grounding.saturn_local_provider._post_loopback",
                   return_value=json.dumps({
                       "model": CONFIG.model_id,
                       "choices": [{
                           "finish_reason": "stop",
                           "message": {"content": json.dumps({"claims": [forged]})},
                       }],
                       "usage": {"total_tokens": 20},
                   }).encode("utf-8")):
            with service.open_answer_session() as session:
                context = session.build_context(
                    "Device X: interface?", mode="lexical", top_k=10)
                result = assembly.assemble(session=session, context=context)
        self.assertNotEqual(result.status, "answered")
        self.assertEqual(result.citations, ())
        self.assertEqual(provider.last_usage, {"total_tokens": 20})


if __name__ == "__main__":
    unittest.main()
