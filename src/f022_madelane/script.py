"""
f022_madelane/script.py

STATIC SCHEMATIC — NON-ANALYTICAL OUTPUT.

This script generates an HTML wrapper around the MaDeLaNe (Markov Decision
Latent Network) projection schematic PNG. It does not produce computed
analytical results, run any statistical model, or claim inferential
significance.

No p-values, significance markers, or computed model outputs are claimed
by this figure.
"""
import os
import base64
from pathlib import Path


def run_f022() -> str:
    """
    Generates an HTML wrapper for the MaDeLaNe static schematic PNG.

    Returns:
        str: Absolute path to the generated HTML output file.
    """
    REPO_ROOT = Path(__file__).resolve().parent.parent.parent
    output_dir = REPO_ROOT / "outputs" / "oglo-8figs" / "f022-madelane"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Canonical static asset — schematic PNG committed to repo
    png_path = output_dir / "madelane.png"

    # Embed PNG as base64 if available; otherwise use a placeholder message
    if png_path.exists():
        with open(png_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        img_tag = (
            f'<img src="data:image/png;base64,{img_b64}" '
            f'alt="MaDeLaNe Projection Schematic" style="max-width:100%;height:auto;" />'
        )
        asset_status = "Static schematic PNG embedded from outputs/oglo-8figs/f022-madelane/madelane.png"
    else:
        img_tag = "<p style='color:#cc0000;font-weight:bold;'>[Schematic PNG not found — madelane.png missing from output directory]</p>"
        asset_status = "WARNING: madelane.png not found in output directory."

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Figure f022 — MaDeLaNe Projection</title>
  <!-- Machine-readable figure metadata for pipeline auditors -->
  <script type="application/json" id="figure-metadata">
    {{"paper_bgcolor": "#FFFFFF", "type": "static_schematic", "analytical": false}}
  </script>
  <style>
    body {{
      background: #ffffff;
      color: #111111;
      font-family: 'Segoe UI', Arial, sans-serif;
      max-width: 960px;
      margin: 40px auto;
      padding: 0 24px;
    }}
    .status-banner {{
      background: #fff3cd;
      border: 2px solid #ffc107;
      border-radius: 6px;
      padding: 16px 20px;
      margin-bottom: 28px;
    }}
    .status-banner h2 {{
      margin: 0 0 8px;
      font-size: 1.1rem;
      color: #856404;
    }}
    .status-banner p {{
      margin: 0;
      font-size: 0.92rem;
      color: #533f03;
    }}
    h1 {{ font-size: 1.5rem; margin-bottom: 6px; }}
    .subtitle {{ color: #555; margin-bottom: 28px; font-size: 0.95rem; }}
    .figure-container {{
      border: 1px solid #ddd;
      border-radius: 6px;
      padding: 20px;
      background: #fafafa;
    }}
    footer {{
      margin-top: 40px;
      font-size: 0.8rem;
      color: #888;
      border-top: 1px solid #eee;
      padding-top: 12px;
    }}
  </style>
</head>
<body>
  <h1>Figure f022 — MaDeLaNe Projection</h1>
  <p class="subtitle">Markov Decision Latent Network — Projection Architecture</p>

  <div class="status-banner">
    <h2>⚠ STATIC SCHEMATIC — NON-ANALYTICAL OUTPUT</h2>
    <p>
      This figure is a <strong>static schematic</strong> illustrating the MaDeLaNe
      (Markov Decision Latent Network) projection architecture. It is <strong>not</strong>
      a computed analytical output. No p-values, significance markers, model fit
      statistics, or inferential claims are made by this figure.<br /><br />
      Asset status: {asset_status}
    </p>
  </div>

  <div class="figure-container">
    {img_tag}
  </div>

  <footer>
    <p>
      Source module: <code>src/f022_madelane/script.py</code><br />
      Output directory: <code>outputs/oglo-8figs/f022-madelane/</code><br />
      Pipeline phase: 5 (Computational Model Schematics)<br />
      Statistical status: No statistical analysis performed. This is a conceptual diagram only.
    </p>
  </footer>
</body>
</html>
"""

    out_path = output_dir / "f022_madelane_schematic.html"
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"[success] Figure f022 (MaDeLaNe static schematic) written to {out_path}")
    return str(out_path)


if __name__ == "__main__":
    run_f022()
