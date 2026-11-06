# FCV technique guide and exact implementation map

All paths below are relative to the project root. The lab view performs independent demonstrations on the source image. It does not secretly alter the final scan.

| FCV technique | Implementation module / function | Purpose | Demonstration |
|---|---|---|---|
| Image acquisition | image_processing.load_image; gui.CameraThread | Decode images, EXIF orientation, camera frames | Open / Webcam |
| Aspect-preserving resizing | image_processing.resize_longest | Bounded cost, correct coordinate scaling | Detection and stage sizes |
| Cropping | image_processing.crop | ROI extraction | Lab: Center crop |
| BGR to gray | image_processing.gray | Luminance for gradients/statistics | Stage: Grayscale |
| Normalization | image_processing.demonstrate | Stretch min/max intensities | Lab: Normalize |
| Histogram | image_processing.histogram_image | Show intensity distribution | Lab: Histogram |
| Histogram equalization | image_processing.demonstrate | Global contrast redistribution | Lab: Equalize |
| CLAHE | enhancement.enhance; image_processing.demonstrate | Controlled local contrast | Colour/gray/enhanced; Lab: CLAHE |
| Brightness / contrast | enhancement.enhance | User-controlled centered linear mapping | Appearance sliders + Update |
| Gamma | image_processing.gamma_correct | Nonlinear exposure adjustment via LUT | Gamma slider; Lab: Gamma |
| Gaussian filtering | document_detection.detect_document; demonstrate | Smooth before threshold/edge operations | Otsu proposal preprocessing; Lab: Gaussian |
| Median filter | image_processing.demonstrate | Suppress impulse noise | Lab: Median |
| Bilateral filter | document_detection.detect_document; enhancement.enhance | Denoise while protecting strong edges | Filtering stage; Lab: Bilateral |
| Convolution sharpening | enhancement.enhance; demonstrate | Increase local edge contrast | Sharpen control; Lab: Sharpen |
| Canny | document_detection.detect_document | Thin connected edge evidence | Edge detection; Lab: Canny |
| Binary threshold | image_processing.demonstrate | Simple fixed-level segmentation | Lab: Binary |
| Otsu threshold | document_detection.detect_document; enhancement.enhance | Global intensity split | Paper segmentation; B&W method Otsu |
| Adaptive threshold | enhancement.enhance; demonstrate | Local threshold for uneven illumination | B&W preset; Lab: Adaptive |
| Morphology | document_detection.detect_document; demonstrate | Close gaps in edges / masks | Morphological close; Lab: Morphology |
| HSV colour segmentation | document_detection.detect_document; demonstrate | Bright, low-saturation paper proposal | HSV candidate; Lab: HSV paper mask |
| K-means segmentation | image_processing.demonstrate | Partition Lab colours into three clusters | Lab: K-means |
| Contour detection | document_detection.detect_document | Trace connected mask boundaries | Contour candidates stage |
| Convex hull / polygon approximation | document_detection.detect_document | Simplify noisy boundaries to quadrilaterals | approxPolyDP with 4 epsilon ratios |
| Candidate selection | document_detection.detect_document | Select a large, supported, valid page | Boundary + heuristic confidence |
| Hough lines | document_detection._hough_proposals; demonstrate | Supporting boundary hypotheses | Candidate strategy; Lab: Hough lines |
| Corner detection / ordering | perspective_correction.order_corners | Cyclic TL,TR,BR,BL correspondences | Numbered overlay / manual points |
| Homography | perspective_correction.warp_document | Solve projective correspondence | Saved stages quality.json matrix |
| Perspective warp / auto crop | perspective_correction.warp_document | Resample page into its tight rectangle | Perspective correction stage |
| Blur / noise / quality | quality_analysis.analyze_quality | Explain acquisition weaknesses | Quality report |

## 1. Acquisition, resizing and grayscale

OpenCV uses BGR arrays; the GUI converts to RGB for Qt. Pillow applies EXIF orientation before conversion. A reduction factor `s = min(1, 1000/max(H,W))` bounds detection work. Detected corners are divided by `s` before the full input is warped. Experiments are bounded separately at 1200 pixels. Center cropping demonstrates explicit ROI indexing; the final document crop comes from the homography.

Grayscale uses the standard weighted conversion approximately `Y = 0.114 B + 0.587 G + 0.299 R`. Colour can be important for markings, so original and colour modes preserve three channels. Min/max normalization maps `I' = 255 (I-I_min)/(I_max-I_min)`; constant images contain no contrast to recover.

## 2. Histograms, equalization and CLAHE

For level `k`, `p(k)=n_k/N`; cumulative probability `CDF(k)=sum(j=0..k) p(j)`. A discrete equalization mapping is `T(k)=round(255*(CDF(k)-CDF_min)/(1-CDF_min))`, excluding zero-count prefixes. OpenCV handles degenerate constant images. Global equalization spreads the occupied intensity range but can amplify noise or alter page/background balance.

CLAHE divides the image into tiles, clips histogram peaks, redistributes clipped mass and interpolates tile mappings. The app uses 8×8 tiles with a clip limit of 1.6 for colour or 2.0 for grayscale/enhanced presets. Applying CLAHE to Lab lightness avoids independent RGB-channel stretching. Lab Equalize demonstrates the global alternative.

## 3. Linear adjustments and gamma

The centered brightness/contrast mapping is `J = clip(alpha*(I-127.5)+127.5+beta,0,255)`. Brightness shifts levels; contrast expands them about midgray. Gamma correction is `O=255*(I/255)^(1/gamma)`. In this project's convention `gamma>1` brightens. A precomputed 256-entry lookup table makes it cheap. Do not confuse this reciprocal convention with formulas that use gamma as the exponent.

Clipping cannot recover saturated information. Original scan bypasses every appearance adjustment and returns only the perspective warp.

## 4. Convolution and noise filtering

For a kernel `K`, a local linear filter evaluates `J(x,y)=sum_u sum_v K(u,v) I(x+u,y+v)` (OpenCV filter2D uses correlation; symmetric kernels here give the same result as convolution). The sharpening kernel has center `1+4a`, axial neighbours `-a`, corners zero. Its weights sum to one, preserving a constant field. Large `a` introduces ringing and amplifies noise.

Gaussian filtering averages neighbours with spatial Gaussian weights. A median filter selects a local order statistic and is useful for salt-and-pepper noise. Bilateral filtering weights both spatial distance and intensity similarity, reducing noise while keeping strong boundaries. Its intensity threshold can also preserve noise or erase faint text if poorly set. The main pipeline uses a modest bilateral filter; the lab compares all three independently.

## 5. Canny and morphology

Canny follows smoothing, gradient estimation, `G=sqrt(Gx^2+Gy^2)`, gradient direction, non-maximum suppression and double-threshold hysteresis. The detector uses low/high thresholds 40/130 after bilateral smoothing. Strong edges seed connected weaker edges. Fixed thresholds are simple but not universally optimal for low-contrast photographs.

Closing is dilation followed by erosion: `A • B=(A ⊕ B) ⊖ B`. A 5×5 structuring element bridges small edge gaps. A larger element can merge nearby objects. Morphological opening would erode then dilate and is an alternative for isolated noise, but is not applied to document text here because it may delete thin strokes.

## 6. Thresholds and segmentation

Binary thresholding uses `B(x,y)=255` if `I(x,y)>T`, else zero. Otsu chooses the global threshold that maximizes between-class variance `omega0*omega1*(mu0-mu1)^2`; it works best with separable intensity groups. The detector tries both Otsu polarities. Binary output with Otsu is independently selectable.

Adaptive Gaussian thresholding uses `T(x,y)=(Gaussian-weighted local mean)-C`. The threshold window is odd, at least 3, and defaults to 31. Larger `C` makes more pixels white. Smaller windows track local shading but can break large characters or introduce texture. Black-and-white mode defaults to adaptive thresholding.

HSV paper segmentation seeks bright, low-saturation pixels (H unrestricted, S≤110, V≥110). It is a supporting hypothesis, not an assumption that every page is white. Coloured paper, glare and bright table surfaces can defeat it.

K-means minimizes `sum_i ||x_i-mu_label(i)||^2` in Lab colour space, alternating nearest-center assignment and center recomputation. The lab uses K=3, seeded initialization, one attempt and at most 20 iterations. Cluster labels carry no semantic meaning; this is an educational colour segmentation experiment, not a trained document classifier.

## 7. Contours, polygon proposals and ranking

`findContours(..., RETR_LIST, CHAIN_APPROX_SIMPLE)` traces every connected boundary without assuming only the outermost object is relevant. The detector examines the 20 largest contours per mask, ignoring area below 7% of the working image. Convex hulls remove inward text/noise irregularities. Douglas-Peucker `approxPolyDP` uses epsilon equal to 1.5%, 2.5%, 4% or 6% of perimeter. Only convex four-point results survive.

Hough lines use `rho=x*cos(theta)+y*sin(theta)`. The probabilistic transform yields long segments. Up to seven segments in each dominant horizontal/vertical group are retained; intersections of line pairs propose additional quads. This supporting path handles some broken contours but is less rotation-general than the contour path and can connect unrelated objects.

For each candidate, edge support `E` is the fraction of sampled boundary points within 4 pixels of a Canny edge. Photometric separation `P` is the absolute difference of median intensity inside the eroded quad and in an outside ring, divided by 55 and clipped. Area term `A=min(area_fraction/0.6,1)` favours substantial documents. Angle term `R=1-mean(abs(cos(interior_angle)))` mildly favours rectangular shapes without enforcing right angles in the photograph.

Candidate evidence is `S=0.42E+0.28P+0.18A+0.12R`. Area outside 7–97%, tiny edges and candidates with two or more corners touching the frame are rejected. Edge support must be ≥0.35; weak photometric separation needs stronger edge support. A final S below 0.57 is rejected. This is an engineering heuristic, not a calibrated probability. The largest contour alone is not sufficient: a desk border could be larger than the page.

## 8. Corners, homography and resampling

Distinct finite points are sorted by polar angle around their centroid and rotated to the smallest x+y starting point. Orientation is made consistent; convexity, area, edge length and image bounds are checked. For ordinary upright photographs this corresponds to TL,TR,BR,BL. Near-symmetric rotated pages may start at a different physical corner; the method does not infer text orientation.

A planar projective transform is `lambda*[u,v,1]^T = H*[x,y,1]^T`, where H is 3×3 and has 8 degrees of freedom after scale normalization. Equivalently, `u=(h11*x+h12*y+h13)/(h31*x+h32*y+h33)` and similarly for v. Four nondegenerate point pairs provide eight linear constraints. `getPerspectiveTransform` solves the four-point homography; `warpPerspective` inverse-samples using cubic interpolation. RANSAC is not needed when exactly four user-validated correspondences are supplied. It would be suitable for many noisy feature matches.

Output width is the larger of top/bottom edge lengths; height is the larger of left/right lengths, with a 2600-pixel longest-side cap. This produces a useful crop but cannot infer the original physical page ratio from an uncalibrated view. Perspective warping corrects a flat plane, not bent paper, lens distortion or motion blur.

## 9. Quality metrics and score

Metrics are measured on a grayscale image reduced to a longest side of 1000 pixels (no upscaling). Resolution uses the original dimensions. Brightness is the mean; contrast is standard deviation. Laplacian variance is `L=Var(Delta I)`, where `Delta I` is the discrete second spatial derivative. Defocus often reduces high-frequency response, but noise and sharpening can raise it. A focus number is not an OCR score.

Noise estimate: compute high-pass residual `R=I-Gaussian3x3(I)`; select pixels with Sobel gradient magnitude below 10; calculate `sigma_proxy=1.4826*median(|R-median(R)|)`. If fewer than 100 flat pixels exist, use all residual pixels. This is a flat-region MAD proxy; textured paper, filtering and binary thresholding affect its interpretation. It is not a calibrated sensor-noise estimator.

Normalized components are `r=min(1,min(W,H)/1000)`, `b=max(0,1-|mean-180|/180)`, `c=min(1,std/55)`, `s=min(1,ln(1+L)/ln(501))`, `n=max(0,1-noise/20)`. Overall `Q=100*(0.15r+0.15b+0.25c+0.30s+0.15n)`. Excellent ≥85, Good ≥70, Fair ≥50, Poor below 50. Constants are explicit, uncalibrated design choices.

Boundary confidence is displayed separately and is not mixed into Q. Manual corners have no automatic confidence. Opposite-edge relative length differences provide a perspective-asymmetry proxy; they are not a pose estimate. Input score includes the scene/background while output score describes a cropped/processed page. Thresholding can raise Q even when small text gets worse. Compare crops visually before drawing conclusions.

## 10. Alternatives and scope

A learned segmenter could improve semantic selection on cluttered scenes but adds model/data dependencies. GrabCut could refine a known foreground box; a calibrated camera could correct lens distortion. Local Tesseract OCR is implemented in ocr.py and evaluated on a known generated English text fixture; searchable-PDF export preserves its text/image alignment. Page dewarping needs a nonplanar model. Learned semantic segmentation, camera-calibrated undistortion and nonplanar dewarping remain future extensions.

## 11. Extended document workflows

See OPTIONAL_FEATURES.md for all optional-feature mappings. OCR is a local external recognition component; the document detector and enhancement pipeline remain traditional CV. `ocr.recognize` captures TXT, TSV boxes/confidence and a searchable PDF from the same invocation. `export.save_pdf` transforms the whole OCR page to A4 and adds optional visible numbering below its image. `history.HistoryStore` persists image/OCR snapshots and ordered page IDs. Batch cancellation is checked between pages; per-file errors do not discard successful scans. Rotation composes a 90-degree coordinate transform with the stored homography and invalidates OCR. The comparison wipe uses registered rectified input/output images rather than mixing different perspective geometries.
