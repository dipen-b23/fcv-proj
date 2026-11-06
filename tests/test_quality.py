import cv2,numpy as np
from src.quality_analysis import analyze_quality

def test_blur_monotonic(image):
    sharp=analyze_quality(image);blur=analyze_quality(cv2.GaussianBlur(image,(25,25),7))
    assert sharp['laplacian_variance']>blur['laplacian_variance']
    assert sharp['components']['sharpness']>blur['components']['sharpness']

def test_noise_flat_field():
    rng=np.random.default_rng(1)
    clean=np.full((600,800,3),180,np.uint8)
    noisy=np.clip(clean.astype(float)+rng.normal(0,12,clean.shape),0,255).astype(np.uint8)
    assert analyze_quality(noisy)['noise_mad']>analyze_quality(clean)['noise_mad']

def test_score_finite(image):
    for im in [image,np.zeros((100,100),np.uint8),np.full((100,100),255,np.uint8)]:
        report=analyze_quality(im)
        assert 0<=report['score']<=100
        assert np.isfinite(report['laplacian_variance'])
        assert report['classification'] in ['Poor','Fair','Good','Excellent']
