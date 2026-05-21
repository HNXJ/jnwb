# f038
import os
import sys
from pathlib import Path

# Ensure repo root is in path
root = Path(__file__).parent.parent.parent
sys.path.append(str(root))

from src.analysis.io.loader import DataLoader
from src.f038_layer_granger.analysis import run_f038_pipeline
from src.f038_layer_granger.plot import plot_layer_granger_contrast

def main():
    loader = DataLoader()
    
    # Analyze V1-PFC flow
    # Note: Using areas that frequently co-occur in mapping table or significant sessions
    pairs = [("V1", "PFC")]
    
    print(f"""[action] Starting f038 Layer Granger Pipeline...""")
    results_df = run_f038_pipeline(loader, pairs)
    
    if not results_df.empty:
        # Export results
        output_dir = loader.get_output_dir("f038")
        results_df.to_csv(output_dir / "f038_granger_results.csv", index=False)
        
        # Plot
        plot_layer_granger_contrast(results_df, output_dir)
        print(f"""[action] f038 Pipeline Complete. Results in {output_dir}""")
    else:
        print(f"""[warning] No yield for f038. Check Stable-Plus criteria.""")

if __name__ == "__main__":
    main()

# Pipeline contract alias — run_pipeline.py imports run_f038
run_f038 = main
