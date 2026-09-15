# OSF Preregistration — draft (OSF Prereg template structure)

Fill-in fields are marked `[ ]`. Text is aligned with `outputs/docs/analysis_plan.md` v1.0
(git commit `e131aff`, 2026-09-15). Register BEFORE the first annotator starts a study session.

---

## Title
How much training data does a segmentation model need before it helps its annotators?
A blinded, within-subject, multi-reader multi-case study of human-in-the-loop annotation
efficiency versus model maturity in periocular photographs

## Authors
Yoshiyuki Kitaguchi — Department of Ophthalmology, The University of Osaka Graduate School of Medicine.
ORCID: 0000-0002-0135-9715

## Description
Human-in-the-loop (HITL) annotation — correcting a model's prediction instead of drawing from
scratch — is widely assumed to save effort, but the amount of training data (model maturity)
needed before assistance becomes beneficial, and where the benefit saturates, has not been
studied systematically. We will measure annotation effort and quality while annotators correct
predictions from eight SegFormer-B1 models trained on nested, patient-disjoint subsets of
100–2500 images, compared with drawing from scratch, using a blinded within-subject design.
Task: three-class segmentation (eyelid fissure incl. caruncle as a polygon; iris and pupil as
rotated ellipses) of external eye photographs.

## Hypotheses
- H1 (efficiency): per-image annotation time decreases with the training-set size of the
  assisting model with diminishing returns (approximately linear in log10 of training size,
  or saturating).
- H2 (quality non-inferiority): final agreement with ground truth under every HITL condition is
  non-inferior to scratch annotation (Dice margin −0.01; HD95 margin +2 px).
- H3 (automation bias): with low-data models, final quality is positively associated with the
  quality of the initial prediction (anchoring); the association weakens with training size.
- H4 (subjective load): single-item mental-effort ratings decrease with training size.

---

## Study type
Experiment — a researcher randomly assigns treatments (here: assistance conditions) to study
units (image × annotator). Human participants are the annotators; patient images are
pre-existing, de-identified clinical photographs. Not a clinical trial: no health-related
intervention or outcome.

## Blinding
- Annotators are blind to which model produced each initial prediction: the eight HITL
  conditions are shuffled and mixed within each session; model identity, training size and
  block are never sent to the client and are stored only server-side.
- Scratch (no model) cannot be blinded and is presented as a labelled baseline.
- Ground truth and accuracy scores are shown only during practice, never during study sessions.
- Analysts will not be blinded (conditions are needed for the models).

## Is there any additional blinding in this study?
The final blind session ("Session 9") re-presents 10 already-seen HITL images under the same
hidden model; annotators are not told it is a repeat. The last session re-presents the 10
scratch images ("Scratch, 2nd") and is labelled as scratch.

## Study design
Within-subject, 3 annotators × 9 conditions (scratch + 8 HITL models: 100, 200, 300, 500, 1000,
1500, 2000, 2500 training images). 90 study images are divided into 9 gaze-balanced blocks
(7 frontal + 3 peripheral gaze). A 3×9 cyclic Latin square maps (annotator, block) → condition,
so every image is annotated by all three annotators under three different conditions
(multi-reader multi-case, partially crossed on condition). Per annotator: 2 practice sessions
(6 images, GT revealed, excluded) → Scratch (10) → Sessions 1–8 (80 HITL images,
condition-mixed, 10 per session) → Session 9 (10 HITL repeats) → Scratch 2nd (the same 10
scratch images, reshuffled). Sessions unlock strictly in this order.

## Randomization
All assignment is generated once by `scripts/prepare_experiment.py` with fixed seed 42
(image sampling, block formation, within-session order; dedicated seeds for the two repeat
sessions). The frozen assignment file is kept off the public repository because file names
contain patient identifiers; its hash is recorded here: sha256 abca3a66bc4fa31623980ec2b0e842ed482bee07557713a01f4a560ca6a671aa (experiment.json, 2026-09-15).

---

## Existing data
Registration prior to analysis of the data. Pre-existing: the clinical photographs and their
manual ground-truth annotations (CVAT), and the eight trained models with their held-out Dice
on a fixed 463-image patient-disjoint test set (0.919 → 0.954 mean Dice from 100 → 2500
images). No annotator behaviour data have been collected (only developer test runs, which are
tagged and excluded).

## Explanation of existing data
Images and GT were produced before this study for an unrelated segmentation project; the GT
author is excluded from being an annotator. The models were trained and evaluated before the
protocol was finalized, and their performance informed the choice of the 100–2500 range, but no
annotator outcome data exist.

## Data collection procedures
Annotators (ophthalmology clinicians, not involved in GT creation) work remotely in a browser
on a purpose-built web application (FastAPI + Konva.js) served from a single GPU workstation.
For each image the app records: active working time (inference wait, focus-loss pauses,
confirmation and rating time excluded), clicks, vertex add/move/delete counts, mouse travel in
image pixels, undo/redo, zoom/pan, timestamped edit events, per-class time attribution,
a post-submission Paas 9-point mental-effort rating, and the final geometry. Per-class Dice,
IoU, HD95, ASSD and Boundary-F1@2 px against GT, and the change from the initial prediction,
are computed server-side. Annotators complete a background questionnaire before starting.
Sessions may be spread over several days; timestamps are recorded.

## Sample size
3 annotators; 90 study images each (270 image-annotations in the main analysis; 30 per
condition), plus 30 HITL repeat and 30 scratch repeat annotations.

## Sample size rationale
Fixed by design and resource: three clinician annotators were available who had not created
the ground truth. The unit of analysis is the image-annotation and effects are estimated
within annotator. A dose–response analysis over 8 training sizes (240 observations) rather
than pairwise contrasts is the primary test; simulations were not run. Annotator count is
acknowledged as the main generalisability limit; inference is conditional on these annotators.

## Stopping rule
Data collection ends when all three annotators complete all 13 sessions. No interim analyses.

---

## Manipulated variables
Assistance condition (9 levels): scratch, or initial prediction from the model trained on
100/200/300/500/1000/1500/2000/2500 images. Analysed as log10(training size) for HITL
conditions, with scratch as a separate baseline.

## Measured variables
Primary: `duration_sec` (active working time per image).
Secondary effort: total clicks, vertices added/moved/deleted, mouse distance, undo count,
time to first action, idle time, redraw (prediction deleted and redrawn).
Secondary subjective: Paas effort (1–9).
Secondary quality: mean Dice; per-class Dice, HD95, ASSD, Boundary-F1@2 px.
Correction magnitude (HITL only): per-class Dice between initial prediction and final
annotation; area change.
Covariates: gaze (frontal/peripheral), order within session, session index, annotator, image.

## Indices
log(duration_sec); log10(training size); redraw = shapes_deleted > 0; initial-prediction
quality = Dice of the initial prediction vs GT (recomputed from stored geometry).

---

## Statistical models
Primary (H1), HITL conditions only:
`log(duration_sec) ~ log10(train_size) + gaze + order_in_session + session_index
 + (1 | annotator) + (1 | image_id)` — linear mixed model (REML, Satterthwaite df).
If the annotator variance component degenerates to zero, annotator enters as a fixed effect
(decided a priori). Saturation is described by additionally fitting an exponential-decay
model `a + b·exp(−n/τ)` and comparing AIC.
Scratch baseline: the second (post-familiarity) scratch session is the primary reference;
the first scratch is a sensitivity analysis; their paired difference (same images) estimates
the order/learning effect.
H2: `mean_dice ~ condition + covariates + random effects`; non-inferiority declared if the
lower 95% CI bound of (HITL − scratch 2nd) exceeds −0.01 Dice (HD95: upper bound < +2 px).
H3: `mean_dice ~ initial_quality × log10(train_size) + gaze + random effects`;
`redraw ~ log10(train_size)` logistic mixed model.
H4: `effort ~ log10(train_size) + gaze + random effects` (linear; cumulative-link mixed model
as sensitivity).
Reproducibility: ICC(2,1) of duration and pairwise Dice for the 30 HITL repeat pairs and the
30 scratch repeat pairs. Per-class analyses repeat the primary model per class (exploratory).

## Transformations
Natural log of duration_sec; log10 of training size. Boundary metrics in pixels of the native
image.

## Inference criteria
One confirmatory test: the log10(train_size) coefficient in the primary model, two-sided
α = 0.05. Pre-specified contrasts (each HITL condition vs scratch 2nd; seg100 vs seg2500) with
Holm correction. All other outcomes are reported with 95% CIs and nominal p-values as
exploratory.

## Data exclusion
Practice sessions and the developer test account are excluded. Aborted sessions are discarded
by the application. If a session was redone, attempt 1 is used (a later attempt only if attempt 1
is incomplete, reported). Sensitivity analysis excludes images with duration > 5× the
annotator-by-condition median or a heartbeat gap > 60 s (suspected absence); the main analysis
keeps them.

## Missing data
The application blocks submission unless all three classes are present and the effort rating
is given, so item-level missingness is not expected. Any missing session (annotator withdrawal)
is reported and analysed as available-case within the mixed model.

## Exploratory analysis
Per-class dose–response (polygon vs ellipse editing), effort-vs-quality curves from timestamped
edit events, effects of gaze direction, learning trends within sessions, and MRMC-style
(Obuchowski–Rockette) analysis as a complementary framework.

---

## Other
Code, analysis plan and the annotator guide are version-controlled
(`https://github.com/ykitaguchi77/HITL_validation_test`, private during data collection; to be
made public or archived with a DOI at publication). Patient images, the assignment file and
raw results are not shared publicly because file names embed patient identifiers; de-identified
per-image result tables will be shared on request/at publication subject to ethics approval.
Ethics: Institutional Review Board of Osaka University Hospital (大阪大学医学部附属病院 倫理審査委員会), approval No. 19492-7 [ approval date ].
Embargo: 1 week.
