import os
import logging
import voyageai

logger = logging.getLogger(__name__)

voyage_client = voyageai.AsyncClient(api_key=os.environ.get("VOYAGE_APY_KEY"))

def build_pr_summary_text(pr_number: int, pr_title: str, details_text: str, diff_text: str ) -> str:
    """Build the text representation of a PR used for embedding.
    
    Keeps it concise - title, labels, and a truncated diff summary, not the full raw diff, to keep embedding quality high and cost low.
    """
    # Truncate diff to avoid noisy embeddings from huge files
    diff_snippet = diff_text[:800] if diff_text else ""

    return(
        f"PR #{pr_number}: {pr_title}\n"
        f"{details_text[:500]}\n"
        f"Changes: {diff_snippet}"
    )

async def embed_pr_summary(summary_text: str) -> list[float]:
    """Generate a vector embedding for a PR summary using Voyage AI."""
    try:
        result = await voyage_client.embed(
            texts=[summary_text],
            model="voyage-4-lite",
            input_type="document",
            output_dimension=512,
        )
        return result.embeddings[0]
    except Exception as e:
        logger.exception(f"Embedding generation failed: {e}")
        raise


async def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors. Used for clustering."""
    import math
    dot = sum(a * b for a,b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)

