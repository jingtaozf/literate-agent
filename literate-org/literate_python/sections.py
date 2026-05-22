from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score


def optimal_clusters(definitions, embeddings, min_k=2, max_k=10, threshold=0.05):
    """
    Computes the optimal clusters for the given definitions and embeddings.

    It evaluates KMeans clustering for k in range(min_k, max_k+1) by computing the
    silhouette score for each k. If a candidate with more clusters has a silhouette score
    only marginally lower than the best score (within the threshold), it favors the higher k.

    Args:
        definitions: List of text definitions (e.g. function, class, or constant definitions).
        embeddings: Numpy array or list of embeddings corresponding to each definition.
        min_k: Minimum number of clusters to try.
        max_k: Maximum number of clusters to try.
        threshold: If the difference between the best score and a candidate score is less than
                   this threshold, choose the candidate with more clusters.

    Returns:
        clusters: A dictionary mapping each cluster label to a list of definitions.
        optimal_k: The optimal number of clusters chosen.
        scores: A dictionary mapping k to its silhouette score.
    """
    scores = {}
    # # Cap k at sample count and short-circuit the trivial "too few samples" case.
    # Limit max_k to the number of samples
    max_k = min(max_k, len(embeddings))

    # If too few samples, return one cluster containing all definitions.
    if len(embeddings) < 2:
        return {0: definitions}, 1, scores

    best_k = None
    best_score = -1

    # # Sweep k = min_k..max_k by silhouette score; ties within `threshold` favour the larger k.
    # Evaluate silhouette scores for each candidate k.
    for k in range(min_k, max_k + 1):
        kmeans = KMeans(n_clusters=k, random_state=42)
        labels = kmeans.fit_predict(embeddings)
        score = silhouette_score(embeddings, labels)
        scores[k] = score
        print(f"k={k}, silhouette score={score:.4f}")

        # For the first candidate, simply assign best_k.
        if best_k is None:
            best_k = k
            best_score = score
        else:
            # If a candidate has a slightly lower score (within threshold) but with more clusters,
            # favor it for increased granularity.
            if score > best_score:
                best_k = k
                best_score = score
            elif (best_score - score) < threshold and k > best_k:
                best_k = k
                best_score = score

    optimal_k = best_k
    print(f"\nOptimal number of clusters chosen: {optimal_k}")

    # # Re-run KMeans once more with the chosen k to get the final label assignments.
    # Run final clustering with the optimal number of clusters.
    final_kmeans = KMeans(n_clusters=optimal_k, random_state=42)
    final_labels = final_kmeans.fit_predict(embeddings)

    # # Group input definitions by their final cluster label and return the mapping.
    # Group definitions by cluster.
    clusters = {}
    for label, definition in zip(final_labels, definitions):
        clusters.setdefault(label, []).append(definition)

    return clusters, optimal_k, scores


# Example usage:
def test_optimal_clusters():
    # Sample list of definitions (could be function/class definitions, etc.)
    definitions = [
        "def load_data(filepath):\n    # loads the data from a file",
        "def preprocess_data(data):\n    # cleans and normalizes the data",
        "class DataLoader:\n    # class for loading data from various sources",
        "def train_model(data):\n    # trains a machine learning model",
        "class ModelTrainer:\n    # class that encapsulates the training logic",
        "def predict(input):\n    # makes predictions using the trained model",
        "def render_vue_component(props):\n    // renders a Vue component based on the props",
        "class VueComponent:\n    // defines a Vue component with state and methods",
        "def mount_vue_app(selector, component):\n    // mounts a Vue app to the DOM element",
        # Add more definitions as needed...
    ]

    # Load a pre-trained model to compute sentence embeddings.
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(definitions)

    # Compute optimal clusters.
    clusters, optimal_k, scores = optimal_clusters(
        definitions, embeddings, min_k=2, max_k=5, threshold=0.05
    )

    # Print out the resulting clusters.
    for cluster_id, items in clusters.items():
        print(f"\nCluster {cluster_id}:")
        for item in items:
            print(f"  - {item}")
