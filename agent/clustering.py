import logging
from agent.embeddings import cosine_similarity

logger = logging.getLogger(__name__)

#PRs with similarity above this threshold are considered related
SIMILARITY_THRESHOLD = 0.80

async def cluster_prs(pr_records: list[dict], embeddings: list[list[float]]) -> list[list[int]]:
    """Group PR indices into clusters based on embedding similarity.

    Uses simple single-link clustering: two PRs join a cluster if their
    similarity exceeds the threshold. This is intentionally simple — for
    a batch of 3-10 PRs, a full clustering algorithm is overkill.

    Args:
        pr_records: List of PR record dicts (for logging/context only).
        embeddings: List of embedding vectors, same order as pr_records.

    Returns:
        List of clusters, each a list of indices into pr_records.
    """
    n = len(embeddings)
    if n == 0:
        return[]
    if n == 1:
        return [[0]]
    
    #Build adjacency based on similarity threshold
    visited = [False] * n
    clusters = []

    for i in range(n):
        if visited[i]:
            continue

        cluster = [i]
        visited[i] = True

        for j in range(i + 1, n):
            if visited[j]:
                continue

            sim = await cosine_similarity(embeddings[i], embeddings[j])
            if sim >= SIMILARITY_THRESHOLD:
                cluster.append(j)
                visited[j] = True
                logger.info(
                    f"Clustered PR #{pr_records[i]['pr_number']} with "
                    f"PR #{pr_records[j]['pr_number']} (similarity: {sim:.3f})"
                )

        clusters.append(cluster)

    return clusters


def format_clusters_for_prompt(pr_records: list[dict], clusters: list[list[int]]) -> str:
    """Format clustered PRs into a structure the generation prompt can use, grouping related changes together with an explicit note.
    """
    sections = []

    for cluster_idx, indices in enumerate(clusters):
        if len(indices) == 1:
            pr = pr_records[indices[0]]
            sections.append(
                f"--- Change ---\n"
                f"PR #{pr['pr_number']}: {pr['pr_title']}\n"
                f"{pr['details_text']}\n"
                f"{pr['diff_text']}"
            )
        else:
            # Multiple related PRs - flag this explicity for the writer
            pr_titles = ", ".join(f"#{pr_records[i]['pr_number']}" for i in indices)
            sections.append(f"--- Related changes (treat as one theme: {pr_titles}) ---")
            for idx in indices:
                pr = pr_records[idx]
                sections.append(
                    f"PR #{pr['pr_number']}: {pr['pr_title']}\n"
                    f"{pr['details_text']}\n"
                    f"{pr['diff_text']}"
                )
    return "\n\n".join(sections)


