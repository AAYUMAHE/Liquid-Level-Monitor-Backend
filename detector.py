import numpy as np
import cv2

import scipy.sparse
import scipy.sparse.linalg
from scipy.ndimage import convolve
from sklearn.neighbors import radius_neighbors_graph
from skimage import color, util, io


class PMI_Edge_Detector:
    def __init__(self, num_eigenvecs=5, sigma=0.1, radius=0.2, max_dim=100):
        """
        num_eigenvecs : number of non-trivial eigenvectors
        sigma         : bandwidth for PMI weighting
        radius        : neighborhood radius in feature space
        max_dim       : image scaled so max(H, W) = max_dim for speed
        """

        self.num_eigenvecs = num_eigenvecs
        self.sigma = sigma
        self.radius = radius
        self.max_dim = max_dim

        # Precompute oriented filters (8 directions)
        self.filters = []
        norient = 8
        for o in range(norient):
            theta = (np.pi / norient) * o
            filt = self.oeFilter_custom(sigma=1.0, support=2.0, theta=theta)
            self.filters.append(filt)

    # ---------------------------------------------------
    # Oriented Edge Filter
    # ---------------------------------------------------
    def oeFilter_custom(self, sigma, support, theta, deriv=1):
        hs = int(np.ceil(sigma * support))

        y, x = np.meshgrid(
            np.arange(-hs, hs + 1),
            np.arange(-hs, hs + 1),
            indexing='ij'
        )

        x_theta = x * np.cos(theta) + y * np.sin(theta)
        y_theta = -x * np.sin(theta) + y * np.cos(theta)

        gauss = np.exp(-(x_theta**2 + y_theta**2) / (2 * sigma**2))

        if deriv == 1:
            filt = -(x_theta / (sigma**2)) * gauss
        else:
            filt = gauss

        filt = filt - np.mean(filt)
        filt = filt / (np.sum(np.abs(filt)) + 1e-10)

        return filt

    # ---------------------------------------------------
    # Apply filter
    # ---------------------------------------------------
    def applyFilter(self, img, f):
        return convolve(img, f, mode='reflect')

    # ---------------------------------------------------
    # Extract LAB Features
    # ---------------------------------------------------
    def get_features(self, img):

        if img.ndim == 2:
            img = color.gray2rgb(img)

        lab = color.rgb2lab(img)

        # Normalize to [0,1]
        lab = (lab - lab.min()) / (lab.max() - lab.min() + 1e-8)

        return lab

    # ---------------------------------------------------
    # Build Affinity Matrix
    # ---------------------------------------------------
    def build_affinity_matrix(self, features, h, w):

        flat_feats = features.reshape(-1, features.shape[2])

        # Add spatial coordinates
        y_grid, x_grid = np.mgrid[0:h, 0:w]
        coords = np.stack((y_grid.ravel(), x_grid.ravel()), axis=1)
        coords = coords / max(h, w)

        combined_feats = np.hstack((flat_feats, coords))

        W = radius_neighbors_graph(
            combined_feats,
            radius=self.radius,
            mode='distance',
            metric='euclidean',
            include_self=False
        )

        W.data = np.exp(-(W.data**2) / (self.sigma**2))

        return W.tocsr()

    # ---------------------------------------------------
    # Spectral Clustering
    # ---------------------------------------------------
    def spectral_clustering(self, W, h, w):

        diag_d = np.array(W.sum(axis=1)).ravel()
        diag_d[diag_d < 1e-10] = 1e-10

        D = scipy.sparse.diags(diag_d)
        L = D - W

        try:
            vals, vecs = scipy.sparse.linalg.eigsh(
                L,
                k=self.num_eigenvecs + 1,
                M=D,
                which='SM',
                tol=1e-2
            )
        except Exception:
            return np.zeros((h, w, self.num_eigenvecs), dtype=np.float32)

        eigen_maps = vecs[:, 1:self.num_eigenvecs + 1].reshape(
            h, w, self.num_eigenvecs
        )

        return eigen_maps

    # ---------------------------------------------------
    # Main Detection Function
    # ---------------------------------------------------
    def detect(self, image_input):

        # Load image
        if isinstance(image_input, str):
            img = io.imread(image_input)
            img = util.img_as_float(img)
        else:
            rgb = cv2.cvtColor(image_input, cv2.COLOR_BGR2RGB)
            img = util.img_as_float(rgb)

        if img.ndim == 2:
            img = color.gray2rgb(img)

        orig_h, orig_w = img.shape[:2]

        # Resize for speed
        scale = self.max_dim / max(orig_h, orig_w)

        if scale < 1.0:
            new_h, new_w = int(orig_h * scale), int(orig_w * scale)
            img_small = cv2.resize(
                img,
                (new_w, new_h),
                interpolation=cv2.INTER_AREA
            )
        else:
            new_h, new_w = orig_h, orig_w
            img_small = img.copy()

        # Feature extraction
        features = self.get_features(img_small)

        # Build graph
        W = self.build_affinity_matrix(features, new_h, new_w)

        # Spectral clustering
        eigen_maps = self.spectral_clustering(W, new_h, new_w)

        final_edge = np.zeros((new_h, new_w), dtype=np.float32)

        # Apply oriented filters
        for i in range(eigen_maps.shape[2]):
            e_img = eigen_maps[:, :, i]

            e_img = (e_img - e_img.min()) / (
                e_img.max() - e_img.min() + 1e-8
            )

            for filt in self.filters:
                resp = np.abs(self.applyFilter(e_img, filt))
                final_edge += resp.astype(np.float32)

        # Resize back
        if (new_h, new_w) != (orig_h, orig_w):
            final_edge = cv2.resize(
                final_edge,
                (orig_w, orig_h),
                interpolation=cv2.INTER_LINEAR
            )

        # Normalize final output
        final_edge = (final_edge - final_edge.min()) / (
            final_edge.max() - final_edge.min() + 1e-8
        )

        return final_edge
