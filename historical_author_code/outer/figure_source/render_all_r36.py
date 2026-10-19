"""Portable regeneration: accepted Fig1 plus newly rebuilt Fig2-Fig6."""
from pathlib import Path
import argparse, subprocess, sys
H = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument('--data', type=Path, default=H/'source_data')
p.add_argument('--output', type=Path, default=H/'rendered_figures')
p.add_argument('--inkscape', default='C:/Program Files/Inkscape/bin/inkscape.com')
p.add_argument('--skip-fig1', action='store_true')
opt = p.parse_args()
opt.output.mkdir(parents=True, exist_ok=True)
if not opt.skip_fig1:
    subprocess.run([sys.executable,str(H/'build_fig1_vector.py'),'--data',str(opt.data),
                    '--output',str(opt.output),'--inkscape',opt.inkscape],check=True)
for name in ['build_fig2_3.py','build_fig4_5.py','build_fig6.py']:
    subprocess.run([sys.executable,str(H/name),'--data',str(opt.data),'--output',str(opt.output)],check=True)
print('All requested figure masters regenerated:',opt.output)
