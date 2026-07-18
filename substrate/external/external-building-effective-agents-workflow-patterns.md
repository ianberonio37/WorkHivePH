---
name: external-building-effective-agents-workflow-patterns
type: reference
source: https://www.anthropic.com/engineering/building-effective-agents
source_sha: 7a8cbb8514369dbe
fetched_at: 2026-07-17T06:10:38Z
last_verified: 2026-07-17
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: building effective agents workflow patterns
---

## reference · building effective agents workflow patterns

* Start with simple solutions and only increase complexity when needed.
* Consider tradeoffs: agentic systems often increase latency and cost for better task performance.
* Use **workflows** for predictable, well-defined tasks; use **agents** for flexibility and model-driven decision-making at scale.
* When using frameworks, ensure understanding of underlying code to avoid incorrect assumptions.

* **Augmented LLM**: Enhance LLMs with retrieval, tools, and memory; focus on tailoring capabilities to specific use cases and providing easy interfaces.
* **Prompt Chaining**: Decompose tasks into sequences of steps; use for tasks that can be cleanly decomposed into subtasks (e.g., generating marketing copy, then translating).
* **Routing**: Classify inputs and direct to specialized tasks; use for complex tasks with distinct categories (e.g., customer service queries).
* **Parallelization**: Run tasks simultaneously; use for speed or diverse outputs (e.g., implementing guardrails, automating evals).
* **Orchestrator-Workers**: Central LLM breaks down tasks, delegates to worker LLMs; use for complex tasks with unpredictable subtasks (e.g., coding products).
* **Evaluator-Optimizer**: One LLM generates, another evaluates and provides feedback; use for clear evaluation criteria and iterative refinement (e.g., literary translation).

* **Agents**: Use for open-ended problems with unpredictable steps; prioritize simplicity, transparency, and thorough tool documentation and testing.
* Combine and customize patterns to fit use cases; measure performance and iterate on implementations.

Sources: https://www.anthropic.com/engineering/building-effective-agents
