import numpy as np
from scipy.ndimage import gaussian_filter1d


class ResultAnalyzer:
    def get_subpixel_row(self, edge_map):
        p = gaussian_filter1d(np.mean(edge_map, 1), 1.0)
        i = int(np.argmax(p))
        if 0 < i < len(p) - 1:
            y1, y2, y3 = p[i-1], p[i], p[i+1]
            return i + 0.5 * (y1 - y3) / (y1 - 2*y2 + y3 + 1e-10)
        return float(i)
