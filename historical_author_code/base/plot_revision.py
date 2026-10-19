"""R33 compatibility entry point; use plot_figures_r33.py for the editable renderer."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('plot_figures_r33.py')),run_name='__main__')
