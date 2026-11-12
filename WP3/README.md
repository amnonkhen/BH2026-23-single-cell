
# Cell-type homology
Project 23 - BioHackathon Europe 2026 - ELIXER Single-Cell Omics - _Single-cell dataset integration across repositories and species for cell-type homology analyses_

This repository contains the scripts and output from Axis 3 (homology and non-homology signals). We focus on developing a pipeline to robustly detect homologous and species-specific cell types across species and the genes that underlie these patterns. We use the SAMap output from WP2 (benchmarking) and apply two different kinds of analyses.

| **Category**     | **Approach**          | **Input**              | **Output**                    |
|:----------------:|:---------------------:|:----------------------:|:-----------------------------:|
| Expression-first | ElasticNet Regression | Expression matrix      | species-specific genes        |
| Manifold-first   | Local outlier factor  | joint species manifold | species-specific cells/states |

Our strategy was to choose two types of methods that use different data inputs and algorithms to infer species-specific cell-types and expression profiles. We compare the results of these methods with SAMap output (homology alignment scores and gene pairs). 

# ElasticNet regression
The first method is ElasticNet regression which takes an expression matrix and weighs the ability of each gene to classify a cell in a category of interest (e.g., species). We provide expression matrices for SAMap-defined homologous groups and it outputs coefficients for each gene as well as a classification accuracy value. Gene weights allow us to detect genes that drive species-specific signals while we can compare the classification accuracy score to determine the overall strength of the species-specific signal.

Interpretation
|                                   | High SAMap homology                    | Low SAMap homology          |
| High species classification score | homology + transcriptional divergence? | Candidate non-homology      |
| Low species classification score  | homology + strong conservation?        | Ambiguous / poorly resolved |

# Local outlier factor
The other method we test is a novelty detection method (local outlier factor) which takes a manifold and asks how much a datapoint (e.g., a cell) differs from its closest neighbor. We provide PCA (integrated dataset) from SAMap and it outputs outlier scores which we will aggregate by cell-type annotation and integrate with other sources of information like marker gene expression and lack of SAMap-based homology support. We then characterize candidate species-specific clusters.

# Running the workflow

To be updated after scripts finished.

# References
* Tarashansky et al. (2021)

---

# ElasticNet regression (Expression-first)

The first method is ElasticNet regression which takes an expression matrix and weighs the ability of each gene to classify a cell in a category of interest (e.g., species). We provide expression matrices for SAMap-defined homologous groups and it outputs coefficients for each gene as well as a classification accuracy value. Gene weights allow us to detect genes that drive species-specific signals while we can compare the classification accuracy score to determine the overall strength of the species-specific signal.

## Implementation Details

### Dataset
*   **Cells:** ~20,000 cells from mouse (`mm`) and zebrafish (`dr`), muscle populations.
*   **File:** `data/raw/samap_mm_dr_map2_20K`
*   **Ortholog Map:** `data/raw/GenePair_annot_map2.tsv`

### Methodology
1.  **Ortholog Mapping:** We force-renamed zebrafish genes to their mouse orthologs using the SAMap GenePair map to remove the "gene naming artifact" (`mm_` vs `dr_`). *Note: This map only covered 337 genes, so the mapping is partial.*
2.  **Grouping:** Cells were grouped into biological categories (`fast_muscle`, `slow_muscle`, `progenitors`) based on SAMap annotations.
3.  **Model:** `ElasticNet` (regression) with fixed hyperparameters (`alpha=0.01`, `l1_ratio=0.5`), following the methodology of Brito et al. (2025).
4.  **Subsampling:** Max 10,000 cells per species to ensure computational efficiency.

### Results (with partial ortholog mapping)

| Group | \(R^2\) | RMSE | Signature Size (# non-zero genes) | Top Discriminative Gene |
| :--- | :--- | :--- | :--- | :--- |
| **progenitors** | 0.8777 | 0.0842 | 213 | `mm_Meg3` (Mouse) |
| **fast_muscle** | 0.9948 | 0.0360 | 35 | `mm_Ttn` (Mouse) |
| **slow_muscle** | 0.9903 | 0.0477 | 61 | `dr_ttn.2` (Zebrafish) |

### Interpretation
*   **Progenitors (\(R^2\) = 0.88):** A more honest biological signal. The partial ortholog mapping reduced the naming artifact, and the model still distinguishes species well.
*   **Fast/Slow Muscle (\(R^2\) = 0.99):** The high \(R^2\) is partially inflated by gene naming artifacts. The top discriminative genes (e.g., Titin `Ttn`/`ttn.1`/`ttn.2`) were **not covered** by the partial 337-gene map, so the model still relies on `mm_` vs `dr_` prefixes.
*   **Signature Size (35–213 genes):** ElasticNet identified compact gene signatures. The number of genes increases for less differentiated cells (progenitors), which have more plastic transcriptomic programs.

### Comparison to SAMap
*   SAMap correctly identified homology at the cellular level.
*   ElasticNet reveals that the underlying gene regulatory programs are **highly divergent**, but the exact magnitude for fast/slow muscle is confounded by incomplete ortholog mapping.

### How to Run
```bash
cd WP3/src
python elasticnet_analysis.py
