# SmartScan viva questions and answers

**1. What does your project do?**
It finds a likely page in a photograph, maps its quadrilateral into a rectangular scan, offers controlled enhancement, and explains its intermediate operations and heuristic quality metrics through a desktop GUI.

**2. Why use traditional computer vision instead of a neural model?**
The FCV lab focuses on inspectable image processing. Contours, edges, colour masks and a homography work locally without a training set, model download or GPU. The tradeoff is weaker semantic understanding in cluttered scenes.

**3. Why not select the largest contour directly?**
A table border or another object might be larger. We generate quads from several masks and combine edge support, inside/outside contrast, area and shape evidence. Even then, we ask the user to inspect the boundary.

**4. Why resize for detection?**
Pixel-level operations become cheaper. We keep the aspect ratio and divide detected corner coordinates by the scale factor, so the warp uses the original image. Detection is capped at 1000 pixels on the longest side; output at 2600.

**5. What are the steps of Canny?**
Smoothing, gradients, non-maximum suppression, double thresholds and hysteresis linking. We use it to gather edge evidence rather than to interpret page content.

**6. Why does bilateral filtering help?**
It combines spatial and intensity weights so that nearby pixels on the same surface are averaged more than pixels across a strong edge. It costs more than Gaussian smoothing and can still harm faint strokes if set aggressively.

**7. Gaussian versus median?**
Gaussian smoothing is a weighted mean and handles mild random noise. Median selects a local middle value and is especially useful for isolated impulse noise. Both can remove useful details.

**8. What does morphological closing do?**
Dilation then erosion bridges small gaps. It helps broken document edges form coherent contours. Too large a kernel can join unrelated objects.

**9. What is polygon approximation?**
Douglas-Peucker reduces a contour while keeping its geometric deviation within epsilon. We try multiple perimeter-relative epsilon values and retain valid convex quads.

**10. What is a homography?**
A 3×3 projective mapping, defined up to scale, between two views of a plane. It has eight independent parameters. Four nondegenerate point pairs determine it.

**11. Why order corners?**
The source and destination vertices need corresponding cyclic positions. A wrong correspondence can twist, mirror or rotate the result. We sort around the centroid, enforce orientation and validate the quad.

**12. Do you use RANSAC?**
No. The warp uses exactly four geometric correspondences, so a direct solution is sufficient. RANSAC is useful with many noisy feature matches and outliers; using its name here would misdescribe this implementation.

**13. Does perspective correction recover the true page dimensions?**
No. Opposite-edge lengths define a practical output rectangle. True physical aspect ratio requires extra information, such as a known page size or camera calibration.

**14. How does histogram equalization differ from CLAHE?**
Global equalization remaps levels using the whole-image CDF. CLAHE applies locally clipped histogram mappings and interpolates them, reducing some global-overprocessing problems. It can still increase noise.

**15. Why work on Lab lightness for colour enhancement?**
Applying separate equalization to B, G and R may shift colours strongly. Processing primarily the luminance-like Lab channel preserves colour relationships better, though it is not perfect colour fidelity.

**16. What gamma convention do you use?**
Output is `255*(input/255)^(1/gamma)`. Gamma above 1 brightens; below 1 darkens. A 256-entry LUT applies it efficiently.

**17. Otsu versus adaptive thresholding?**
Otsu chooses one global split using between-class variance. Adaptive Gaussian thresholding computes a local weighted mean minus C and handles some uneven lighting better. Neither restores lost information.

**18. Why must the adaptive window be odd?**
An odd width gives a centered pixel neighbourhood. The application forces at least 3 and an odd value. Larger windows follow slower illumination variation; C shifts the local decision threshold.

**19. What does Hough contribute?**
Long line segments can remain even when the contour is broken. Intersections of separated dominant line pairs produce alternative quads. Lines on unrelated objects can create incorrect hypotheses, so candidates still need evidence scoring.

**20. What does K-means demonstrate?**
Unsupervised colour clustering in Lab space with three centers. It segments by feature similarity, not page semantics, and it is deliberately independent of the final scanning pipeline.

**21. How is blur measured?**
Variance of the Laplacian estimates high-frequency structure. Blur generally lowers it, but noise, sharpening and binarization can increase it. It is a diagnostic, not a universal focus threshold.

**22. Is the quality score scientifically validated?**
No. It is an explicitly weighted educational heuristic: 15% resolution, 15% brightness, 25% contrast, 30% log sharpness and 15% low noise. Boundary confidence is separate. The code and guide give every normalization constant.

**23. Can the output quality score be misleading?**
Yes. The source includes the background while the output is cropped. Binarization can raise contrast and sharpness statistics even while thin characters disappear. We show both images so visual inspection remains part of the workflow.

**24. What happens when detection fails?**
There is no automatic scan to export. The interface explains the failure and offers four manual corners. Manual points are checked for bounds, convexity and area; no fabricated confidence is assigned.

**25. How do you avoid freezing the GUI?**
CV, decoding and export tasks run in a Qt thread pool and return results by signals. The camera has a separate capture thread. Widgets are updated in the main event loop. Conflicting operations are disabled while a task is active.

**26. What was actually tested?**
The included testing report records automated tests and measured deterministic synthetic scenes with known corner truth. Geometry, image/PDF writes, failure paths and real Qt widgets were exercised. These are not real-world accuracy results; webcam and a Windows desktop need local checking.

**27. Why does a clean rectangle sometimes get selected incorrectly?**
Traditional geometry cannot reliably distinguish paper from a similarly shaped object. Texture, lighting and foreground/background separation determine the available evidence. Manual correction is a necessary fallback.

**28. Can you recover a blurred, folded or partly missing page?**
A planar transform can rectify visible geometry. It cannot reconstruct missing text, severe defocus, curved surfaces or clipped highlights. A new photograph is often the right solution.

**29. Are your PDFs searchable?**
Both export types are available. Image PDF contains raster page images; searchable PDF also includes OCR text. Tesseract supplies an aligned invisible text layer for searchable PDF export. Ordinary image-only PDF remains available. The persistent document queue supports a maximum of 20 pages.

**30. What would you improve next?**
Collect a diverse annotated camera-image set, calibrate detection confidence, evaluate OCR character error against ground truth, evaluate additional languages, add automatic orientation and curved-page dewarping. These require additional implementation and evaluation.

**31. How is OCR integrated?**
A local Tesseract subprocess receives the final scan and emits TXT, TSV word positions/confidence, and PDF in one invocation. The application uses no network API or hardcoded key. Tesseract itself is a trained recognition component; the document-scanning algorithms are classical OpenCV.

**32. How can text stay aligned in a resized PDF?**
We transform Tesseract's PDF page as a whole, keeping the image and invisible text in the same coordinate system, then add a visible page-number footer outside the scan.

**33. What happens to OCR after rotating or enhancing?**
The current result is invalidated, because its image/text relationship may no longer match. A requested searchable export reruns recognition instead of reusing stale text.

**34. Is engine confidence equal to OCR accuracy?**
No. It is the engine's own word confidence. Actual error rates require known reference text. The included evaluation reports normalized edit distances on one generated English fixture, not unrestricted real-world accuracy.

**35. How do history and documents persist?**
SQLite stores snapshot metadata, OCR text and ordered page IDs. PNG/PDF files hold scan and OCR data. Reopening the app restores the queue; deleting a snapshot also removes its queued references. Original photographs are not copied into history.

**36. What if one batch file fails?**
It receives an independent status in the result table/JSON report. A boundary failure can be opened for manual correction. An OCR failure retains the PNG. Cancellation stops before the next page and marks the remainder cancelled.

**37. What does the comparison slider compare?**
The perspective-corrected image before enhancement and its enhanced output share geometry, so the wipe is registered. The original distorted photo is still shown separately in the main workspace.
