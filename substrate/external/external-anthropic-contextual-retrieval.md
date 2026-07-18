---
name: external-anthropic-contextual-retrieval
type: reference
source: https://www.anthropic.com/engineering/contextual-retrieval
source_sha: e37bd52c9cd9a974
fetched_at: 2026-07-14T09:29:53Z
last_verified: 2026-07-14
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: anthropic contextual retrieval
---

## reference · anthropic contextual retrieval

* For AI models to be useful in specific contexts, they often need access to background knowledge.
* Retrieval-Augmented Generation (RAG) enhances a model's knowledge by retrieving relevant information from a knowledge base and appending it to the user's prompt.
* Traditional RAG solutions can fail to retrieve relevant information due to loss of context during encoding.
* Contextual Retrieval is a method that improves the retrieval step in RAG using two sub-techniques: Contextual Embeddings and Contextual BM25.
* Contextual Retrieval can reduce failed retrievals by 49% and, when combined with reranking, by 67%.
* For small knowledge bases (< 200,000 tokens or 500 pages), including the entire knowledge base in the prompt can be a simpler solution.
* Prompt caching can reduce latency by > 2x and costs by up to 90% for larger knowledge bases.

### Implementing Contextual Retrieval

* Break down the knowledge base into smaller chunks of text (usually no more than a few hundred tokens).
* Create TF-IDF encodings and semantic embeddings for these chunks.
* Use Contextual Embeddings to prepend chunk-specific explanatory context to each chunk before embedding.
* Use Contextual BM25 to create a BM25 index with contextualized chunks.
* Combine and deduplicate results from Contextual Embeddings and Contextual BM25 using rank fusion techniques.

### Performance Improvements

* Contextual Embeddings reduced the top-20-chunk retrieval failure rate by 35% (5.7% → 3.7%).
* Combining Contextual Embeddings and Contextual BM25 reduced the top-20-chunk retrieval failure rate by 49% (5.7% → 2.9%).
* Reranked Contextual Embedding and Contextual BM25 reduced the top-20-chunk retrieval failure rate by 67% (5.7% → 1.9%).

### Implementation Considerations

* Consider chunk boundaries, embedding models, and custom contextualizer prompts when implementing Contextual Retrieval.
* Experiment with different settings to find the right balance between performance and latency/cost.

Sources: https://www.anthropic.com/engineering/contextual-retrieval
