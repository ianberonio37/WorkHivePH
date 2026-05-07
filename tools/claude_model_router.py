"""
Claude Model Router
Reads historical token data from the tracker and recommends the cheapest
Claude model that can reliably handle each action type.

Routing tiers (cheapest-first):
    Haiku 4.5   →  simple, repetitive, small output
    Sonnet 4.6  →  medium complexity, moderate output
    Opus 4.7    →  complex reasoning, large output, high stakes

Decision rules per action type (requires MIN_SAMPLES calls to activate):
    - If avg_total_tokens < HAIKU_TOKEN_LIMIT  and success >= HAIKU_THRESHOLD  → Haiku
    - If avg_total_tokens < SONNET_TOKEN_LIMIT and success >= SONNET_THRESHOLD → Sonnet
    - Otherwise                                                                 → Opus

Usage:
    from tools.claude_model_router import ModelRouter

    router = ModelRouter()
    model  = router.suggest("debugging")      # e.g. "claude-opus-4-7"
    report = router.routing_table()           # full recommendation table
"""

from dataclasses import dataclass, field
from collections import defaultdict
from tools.claude_token_tracker import get_all_stats

# Minimum samples before the router trusts its data
MIN_SAMPLES = 15

# Token thresholds that justify cheaper models
HAIKU_TOKEN_LIMIT  = 800    # avg total tokens ≤ this → Haiku eligible
SONNET_TOKEN_LIMIT = 3_000  # avg total tokens ≤ this → Sonnet eligible

# Minimum success rate required to use a cheaper model
HAIKU_THRESHOLD  = 0.90   # 90% success rate
SONNET_THRESHOLD = 0.85   # 85% success rate

DEFAULT_MODEL = "claude-opus-4-7"
MODELS_BY_TIER = ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-7"]

MODEL_COST_PER_1M = {
    "claude-opus-4-7":   {"input": 5.00,  "output": 25.00},
    "claude-sonnet-4-6": {"input": 3.00,  "output": 15.00},
    "claude-haiku-4-5":  {"input": 1.00,  "output": 5.00},
}


@dataclass
class ActionProfile:
    action_type:      str
    total_samples:    int   = 0
    avg_total_tokens: float = 0.0
    max_total_tokens: int   = 0
    success_rate:     float = 1.0
    avg_cost_usd:     float = 0.0
    models_seen:      dict  = field(default_factory=dict)  # model → sample_count


class ModelRouter:
    """
    Reads token usage history and recommends the optimal Claude model per action.
    Re-loads stats on each call so it reflects new data without restart.
    """

    def suggest(self, action_type: str) -> str:
        """
        Return the recommended model ID for the given action type.
        Falls back to DEFAULT_MODEL when there is insufficient historical data.
        """
        profile = self._build_profile(action_type)

        if profile.total_samples < MIN_SAMPLES:
            return DEFAULT_MODEL

        avg = profile.avg_total_tokens
        sr  = profile.success_rate

        if avg <= HAIKU_TOKEN_LIMIT and sr >= HAIKU_THRESHOLD:
            return "claude-haiku-4-5"

        if avg <= SONNET_TOKEN_LIMIT and sr >= SONNET_THRESHOLD:
            return "claude-sonnet-4-6"

        return "claude-opus-4-7"

    def routing_table(self) -> list[dict]:
        """
        Return a full recommendation table, one row per action type.
        Each row includes the recommended model, the reason, and estimated
        monthly savings vs always using Opus.
        """
        raw = get_all_stats()
        action_types = {r["action_type"] for r in raw}

        rows = []
        for at in sorted(action_types):
            profile   = self._build_profile(at)
            model     = self.suggest(at)
            reason    = self._reason(profile, model)
            savings   = self._estimate_savings(profile, model)

            rows.append({
                "action_type":        at,
                "recommended_model":  model,
                "reason":             reason,
                "total_samples":      profile.total_samples,
                "avg_total_tokens":   int(profile.avg_total_tokens),
                "max_total_tokens":   profile.max_total_tokens,
                "success_rate_pct":   round(profile.success_rate * 100, 1),
                "avg_cost_usd":       round(profile.avg_cost_usd, 6),
                "est_savings_per_100_calls_usd": round(savings, 4),
                "data_ready":         profile.total_samples >= MIN_SAMPLES,
            })

        return rows

    def summary(self) -> dict:
        """High-level stats: total calls, total cost, potential savings."""
        raw     = get_all_stats()
        total_c    = sum(r["sample_count"]   for r in raw)
        total_cost = sum(r["total_cost_usd"] for r in raw)
        table      = self.routing_table()

        savings = sum(
            r["est_savings_per_100_calls_usd"] * r["total_samples"] / 100
            for r in table
        )

        return {
            "total_calls":         total_c,
            "total_cost_usd":      round(total_cost, 4),
            "potential_savings_usd": round(savings, 4),
            "action_types_tracked": len(table),
            "actions_with_data":   sum(1 for r in table if r["data_ready"]),
        }

    # ── internal helpers ──────────────────────────────────────────────────────

    def _build_profile(self, action_type: str) -> ActionProfile:
        raw = [r for r in get_all_stats() if r["action_type"] == action_type]
        if not raw:
            return ActionProfile(action_type=action_type)

        total_samples    = sum(r["sample_count"]   for r in raw)
        # weighted avg across models
        total_tokens_sum = sum(r["avg_total_tokens"] * r["sample_count"] for r in raw)
        avg_tokens       = total_tokens_sum / total_samples if total_samples else 0
        max_tokens       = max(r["max_total_tokens"] for r in raw)
        # success rate: success_rate_pct is already a percentage from the DB query
        total_success    = sum((r["success_rate_pct"] / 100) * r["sample_count"] for r in raw)
        success_rate     = total_success / total_samples if total_samples else 1.0
        avg_cost         = sum(r["total_cost_usd"] for r in raw) / total_samples if total_samples else 0

        models_seen = {r["model"]: r["sample_count"] for r in raw}

        return ActionProfile(
            action_type      = action_type,
            total_samples    = total_samples,
            avg_total_tokens = avg_tokens,
            max_total_tokens = max_tokens,
            success_rate     = success_rate,
            avg_cost_usd     = avg_cost,
            models_seen      = models_seen,
        )

    def _reason(self, profile: ActionProfile, model: str) -> str:
        if profile.total_samples < MIN_SAMPLES:
            return f"Insufficient data ({profile.total_samples}/{MIN_SAMPLES} samples) - defaulting to Opus"

        if model == "claude-haiku-4-5":
            return (
                f"Avg {int(profile.avg_total_tokens)} tokens (limit {HAIKU_TOKEN_LIMIT}), "
                f"success rate {profile.success_rate:.0%} (min {HAIKU_THRESHOLD:.0%})"
            )
        if model == "claude-sonnet-4-6":
            return (
                f"Avg {int(profile.avg_total_tokens)} tokens (limit {SONNET_TOKEN_LIMIT}), "
                f"success rate {profile.success_rate:.0%} (min {SONNET_THRESHOLD:.0%})"
            )
        return f"Avg {int(profile.avg_total_tokens)} tokens or success rate too low for cheaper models"

    def _estimate_savings(self, profile: ActionProfile, recommended: str) -> float:
        """Estimated cost savings per 100 calls vs always using Opus 4.7."""
        if profile.total_samples == 0:
            return 0.0

        # Approximate: use avg_tokens split 50/50 input/output
        half = profile.avg_total_tokens / 2

        def cost_for(model: str) -> float:
            p = MODEL_COST_PER_1M[model]
            return (half * p["input"] + half * p["output"]) / 1_000_000

        opus_cost = cost_for("claude-opus-4-7")
        rec_cost  = cost_for(recommended)
        return (opus_cost - rec_cost) * 100  # per 100 calls


if __name__ == "__main__":
    router = ModelRouter()
    print("\n=== Model Router Recommendations ===\n")
    for row in router.routing_table():
        status = "READY" if row["data_ready"] else f"need {MIN_SAMPLES - row['total_samples']} more"
        print(
            f"  {row['action_type']:<14} → {row['recommended_model']:<20} "
            f"({row['total_samples']} calls, {status})"
        )
    s = router.summary()
    print(f"\nTotal: {s['total_calls']} calls, ${s['total_cost_usd']:.4f} spent")
    print(f"Potential savings (vs always Opus): ${s['potential_savings_usd']:.4f}\n")
