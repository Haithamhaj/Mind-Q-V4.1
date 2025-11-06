# Correlation Matrix Sampling Analysis

## Current Implementation Analysis

### When Sampling Occurs:
1. **Heavy Load Case**: `columns > 300 AND rows > 100,000` → Sample 100K rows
2. **High Dimensionality**: `columns > 300` → Sample 100% (shuffle only)

### Statistical Validity of Current Approach:

#### ✅ Advantages:
1. **Performance**: Reduces computational complexity from O(n²×m) to manageable levels
2. **Memory Efficiency**: Prevents memory overflow in high-dimensional datasets
3. **Statistical Soundness**: 100K samples generally sufficient for correlation estimation
4. **Reproducibility**: Fixed random seed ensures consistent results

#### ⚠️ Potential Issues:
1. **Rare Pattern Loss**: Low-frequency correlations might be missed
2. **Stratification**: No stratified sampling by time/business segments
3. **Threshold Rigidity**: 300 columns threshold might be too conservative
4. **No Confidence Intervals**: No uncertainty quantification for sampled correlations

## Recommendations:

### Option 1: Enhanced Stratified Sampling
```python
def _smart_correlation_sampling(df: pd.DataFrame, max_rows: int = 100000) -> pd.DataFrame:
    """Stratified sampling preserving temporal and business patterns"""
    if 'main_ts' in df.columns:
        # Time-based stratification
        return df.groupby(pd.to_datetime(df['main_ts']).dt.date).apply(
            lambda x: x.sample(min(len(x), max_rows // df['main_ts'].nunique()))
        ).reset_index(drop=True)
    else:
        # Random sampling as fallback
        return df.sample(n=min(len(df), max_rows), random_state=42)
```

### Option 2: Adaptive Threshold
```python
def _should_sample_correlations(n_rows: int, n_cols: int) -> bool:
    """Adaptive sampling decision based on computational complexity"""
    computational_cost = (n_cols * (n_cols - 1) / 2) * n_rows
    memory_cost = n_cols * n_rows * 8  # bytes for float64
    
    return computational_cost > 1e9 or memory_cost > 1e9  # 1GB threshold
```

### Option 3: Chunked Correlation (No Sampling)
```python
def _chunked_correlation_matrix(df: pd.DataFrame, chunk_size: int = 50) -> pd.DataFrame:
    """Calculate correlation matrix in chunks to handle large datasets"""
    # Implementation would process column pairs in batches
    # Preserves full data while managing memory
```

## Business Impact Assessment:

### Low Risk Scenarios (Current approach OK):
- Exploratory data analysis
- Feature redundancy detection
- General data profiling

### High Risk Scenarios (Need full data):
- Financial fraud detection
- Critical infrastructure monitoring
- Regulatory compliance reporting
- Scientific research requiring precision

## Conclusion:
The current sampling approach is **statistically sound for most business cases** but should be enhanced with:
1. Stratified sampling for temporal data
2. Configurable thresholds based on use case criticality
3. Option to force full computation for critical analyses