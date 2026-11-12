import scanpy as sc
import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_squared_error
import warnings
warnings.filterwarnings('ignore')

print("Loading mapped data...")
adata = sc.read_h5ad("../data/raw/samap_mm_dr_map2_20K")
print(f"Data loaded! Shape: {adata.shape}")

# --- FORCED ORTHOLOG MAPPING ---
print("Loading SAMap GenePair map for ortholog mapping...")
samap_df = pd.read_csv("../data/raw/GenePair_annot_map2.tsv", sep='\t', index_col=0)

gene_map = {}
for pair in samap_df.index:
    if ';' in str(pair):
        parts = pair.split(';')
        if len(parts) == 2:
            dr_gene = parts[0].strip()
            mm_gene = parts[1].strip()
            gene_map[dr_gene] = mm_gene

print(f"Created mapping for {len(gene_map)} zebrafish genes to mouse orthologs.")

new_var_names = [gene_map.get(g, g) for g in adata.var_names]
adata.var_names = new_var_names

print(f"Genes before deduplication: {adata.n_vars}")
adata = adata[:, ~adata.var_names.duplicated()].copy()
print(f"Genes after deduplication: {adata.n_vars}")
# --- END OF FORCED ORTHOLOG MAPPING ---

group_mapping = {
    'mm_MyoC_Myh8': 'fast_muscle', 'mm_MyoC_Myh3': 'fast_muscle',
    'dr_fast muscle cell': 'fast_muscle', 'dr_fast muscle myoblast': 'fast_muscle',
    'dr_fast muscle cell (differentiating)': 'fast_muscle',
    'dr_slow muscle cell': 'slow_muscle', 'dr_slow muscle myoblast': 'slow_muscle',
    'mm_MyoB_Jam3': 'slow_muscle',
    'mm_MyoProg_Pax7_Col15': 'progenitors', 'mm_MyoProg_Pax7_Mki67': 'progenitors',
    'mm_MyoProg_Pax3': 'progenitors', 'mm_MyoProg_Pax3_Pax7': 'progenitors',
    'dr_adaxial cell': 'progenitors', 'dr_somite': 'progenitors',
    'dr_mesodermal cell': 'progenitors',
}

adata.obs['group'] = adata.obs['cell_type;cell_type_mapping_scores'].map(group_mapping)
adata = adata[adata.obs['group'].notna()].copy()
print(f"Cells after grouping: {adata.shape[0]}")

groups = adata.obs['group'].unique()
results = []

for group in groups:
    print(f"\n--- Analyzing group: {group} ---")
    subset = adata[adata.obs['group'] == group].copy()
    
    species_counts = subset.obs['species'].value_counts()
    if 'mm' not in species_counts or 'dr' not in species_counts:
        print(f"Skipping {group}: not both species present.")
        continue
        
    print(f"Cells: Mouse (mm) = {species_counts['mm']}, Zebrafish (dr) = {species_counts['dr']}")

    sc.pp.filter_genes(subset, min_cells=int(0.05 * subset.n_obs))
    print(f"Genes after filtering: {subset.n_vars}")

    y = (subset.obs['species'] == 'dr').astype(float).values
    X = subset.X 
    gene_names = subset.var_names

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    print("Training ElasticNet...")
    model = ElasticNet(alpha=0.01, l1_ratio=0.5, max_iter=2000, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    
    print(f"Test R2 Score: {r2:.4f}")
    print(f"Test RMSE: {rmse:.4f}")

    coefs = pd.Series(model.coef_, index=gene_names)
    non_zero_coefs = coefs[coefs != 0]
    top_genes = non_zero_coefs.abs().sort_values(ascending=False).head(10)
    
    print(f"Total non-zero genes (signature size): {len(non_zero_coefs)}")
    print("Top 10 discriminative genes:")
    for gene, coef in top_genes.items():
        direction = "Zebrafish" if coefs[gene] > 0 else "Mouse"
        print(f"  {gene}: {coef:.4f} (higher in {direction})")

    results.append({
        'group': group, 'n_mouse': species_counts['mm'], 'n_zebrafish': species_counts['dr'],
        'r2_score': r2, 'rmse': rmse, 'signature_size': len(non_zero_coefs),
        'top_genes': ', '.join(top_genes.index.tolist())
    })

df_results = pd.DataFrame(results)
df_results.to_csv("../results/elasticnet_results_final.csv", index=False)
print("\nAnalysis complete. Results saved to ../results/elasticnet_results_final.csv")
