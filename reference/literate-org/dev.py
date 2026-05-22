import marimo

__generated_with = "0.8.22"
app = marimo.App(app_title="Literate Python Development notebook")


@app.cell
def __():
    import marimo as mo
    import os
    import sys
    import logging

    def set_log_level(logger, level):
        # Set the logger level
        if isinstance(logger, str):
            logger = logging.getLogger(logger)
        logger.setLevel(level)

        # If no handler is attached, add one:
        if not logger.handlers:
            ch = logging.StreamHandler()  # Logs to console
            ch.setLevel(level)
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            ch.setFormatter(formatter)
            logger.addHandler(ch)
            logger.propagate = False

    mo.md("# Prepareation\n ## setup marimo & logger \n")
    return logging, mo, os, set_log_level, sys


@app.cell
def __(logging, set_log_level):
    set_log_level("literate_python", logging.INFO)
    return


@app.cell
def __(mo, os):
    mo.md("## Prepare a server for literate python")
    from literate_python import server as literate_server
    from threading import Thread

    os.environ["LITERATE_PYTHON_HOST"] = "127.0.0.1"
    os.environ["LITERATE_PYTHON_PORT"] = "7329"

    literate_server.server_locals = locals()
    literate_python_server_thread = Thread(target=literate_server.run_server)
    literate_python_server_thread.start()
    return Thread, literate_python_server_thread, literate_server


@app.cell(disabled=True, hide_code=True)
def __():
    from sentence_transformers import SentenceTransformer
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    import numpy as np

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
        # Limit max_k to the number of samples
        max_k = min(max_k, len(embeddings))

        # If too few samples, return one cluster containing all definitions.
        if len(embeddings) < 2:
            return {0: definitions}, 1, scores

        best_k = None
        best_score = -1

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

        # Run final clustering with the optimal number of clusters.
        final_kmeans = KMeans(n_clusters=optimal_k, random_state=42)
        final_labels = final_kmeans.fit_predict(embeddings)

        # Group definitions by cluster.
        clusters = {}
        for label, definition in zip(final_labels, definitions):
            clusters.setdefault(label, []).append(definition)

        return clusters, optimal_k, scores

    # Example usage:

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
    return (
        KMeans,
        SentenceTransformer,
        cluster_id,
        clusters,
        definitions,
        embeddings,
        item,
        items,
        model,
        np,
        optimal_clusters,
        optimal_k,
        scores,
        silhouette_score,
    )


@app.cell
def __():
    from literate_python.tests.test_server import test1

    return (test1,)


@app.cell
def __(test1):
    test1()
    return


if __name__ == "__main__":
    app.run()
