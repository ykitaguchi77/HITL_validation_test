# OSF Preregistration — draft v2 (OSF Prereg template structure)

Fill-in fields are marked `[ ]`. Text is aligned with `outputs/docs/analysis_plan.md` **v2.0**
(2026-09-19). Register BEFORE the first annotator starts a study session.

**Relation to the earlier registration.** A first preregistration of this study
(https://osf.io/d7e2g, 2026-09-16) described a design in which the assisting models were eight
SegFormer-B1 networks trained on 100–2500 images and three annotators followed a 3×9 Latin
square. Before any annotator data were collected, the assisting model was replaced by a
few-shot approach (SAM2 decoder-LoRA checkpoints trained sequentially, one epoch per added
annotation), which changes the manipulated variable (number of annotated images n = 1…128
instead of training-set size 100–2500), the assignment scheme and the primary/co-primary
analyses. Because none of the original outcome data existed, we register the new design as a
separate registration rather than as a deviation; d7e2g is superseded and will be cited as
such. All statements below refer to the new design only.

---

## Title
How many annotations does a few-shot segmentation model need before it helps its annotators?
A blinded, within-subject, dose–response study of human-in-the-loop annotation efficiency and
quality versus the number of images the assisting model has learned from (n-shot SAM2 decoder-LoRA)

## Authors
Yoshiyuki Kitaguchi — Department of Ophthalmology, The University of Osaka Graduate School of Medicine.
ORCID: 0000-0002-0135-9715

## Description
Human-in-the-loop (HITL) annotation — correcting a model's proposal instead of drawing from
scratch — is assumed to save effort once the model is "good enough", but how many annotated
images a continually-learning few-shot model must have seen before its proposals reduce human
effort, where the benefit saturates, and whether proposals compromise quality (anchoring), have
not been measured under blinding. We will present proposals from FIXED checkpoints of a
structure-specific SAM2.1 mask-decoder LoRA that was trained sequentially, one epoch per added
annotated image, after n = 1, 2, 4, 8, 16, 32, 64 and 128 images (three independent training
orders), mixed at random with manual (no-proposal) items, to six annotators blind to n. Task:
three-structure segmentation (eyelid fissure incl. caruncle as a polygon; iris and pupil as
rotated amodal ellipses) of external eye photographs. We also test whether the proposal's
precomputed distance to the reference annotation (a "backward simulation" of correction cost)
predicts measured human effort.

## Hypotheses
- H1 (efficiency, primary): among proposal items, per-image active annotation time decreases
  with log2(n).
- H2 (quality non-inferiority, co-primary): for each structure, final ASSD to the reference
  annotation is non-inferior to manual annotation for sufficiently large n; tested in a fixed
  sequence from n = 128 downward; we report the smallest n* at which non-inferiority holds.
- H3 (automation bias): the proposal's error carries over to the final annotation (positive
  slope of final ASSD on proposal ASSD after adjusting for the same image's manual ASSD).
- H4 (subjective load): Paas mental-effort ratings decrease with log2(n).
- H5 (proposal quality predicts effort): the precomputed proposal-to-reference distance explains
  annotation time, and the effect of log2(n) is attenuated once it is included.

---

## Study type
Experiment — assistance conditions are assigned to units (image × annotator) by a fixed
rotation scheme; human participants are the annotators; patient images are pre-existing,
de-identified clinical photographs. Not a clinical trial.

## Blinding
- Annotators are blind to n, training-order seed, model and condition: all conditions are mixed
  in random order within every session; none of these fields is ever sent to the client.
- Proposals are precomputed offline and served by lookup, so manual and proposal items have
  identical response latency (no timing side-channel).
- Manual items are recognisable by the absence of a proposal (an intended baseline); n is not.
- Ground truth and accuracy scores are shown only during practice, never during study sessions.
- A post-study questionnaire asks whether annotators noticed quality differences or could guess
  n (manipulation check). Analysts are not blinded.

## Is there any additional blinding in this study?
No.

## Study design
Within-subject, 6 annotators × 9 conditions (manual; proposals after n = 1, 2, 4, 8, 16, 32,
64, 128 annotated images). Twelve condition slots (8 proposal levels + 4 manual slots) and 60
study images in 12 gaze-balanced groups of 5 (3 frontal + 2 peripheral). Annotator a works
group g under slot[(g + 2a) mod 12]; hence every image is annotated by all six annotators
under six distinct slots — manually by exactly two of them and under four different n by the
others. Per annotator: 2 practice sessions (5 images, GT revealed, excluded) → 6 study sessions
of 10 images. Each session contains one image of 10 of the 12 slots (each n-level at most once
per session, 3–4 manual items); the two omitted slots rotate so that every slot is omitted in
exactly one of the six sessions. Presentation order within a session is random. Sessions
unlock strictly in order; no going back. Each (annotator, n) cell has
5 images split 2/2/1 over the three training-order seeds so that every n uses each seed
equally overall (10/10/10).

## Randomization
Image sampling (`scripts/select_study_images.py`, seed 42; frozen file sha256
e53784f921ed5e122061f6c490bc73d45093a4e5740d66be830513428b04d21f), group formation, the
seed split, session composition and presentation order are generated once by
`scripts/prepare_experiment.py` (seed 42). The assignment file is kept off the public
repository (file names embed patient identifiers); its hash is recorded here:
sha256 bcc841d931a6e57d26e3c118794514d96fa01800ee76d39f95e97dfb4cf4deed (experiment.json, 2026-09-20; regenerate and update once annotators 4–6 are named). Proposal file sha256 b0268b2b7a8f18da0d9a94ae99f9258dc8d14d8f6661e401bb4b8b5e4bd8de86 (proposals.json; probability maps are Gaussian-smoothed, sigma 2 px at 512 px, before thresholding — identical for all n); checkpoint manifest and study-pool hashes are embedded in experiment.json.

---

## Existing data
Registration prior to creation of the outcome data. Pre-existing: the clinical photographs,
their manual reference annotations (CVAT, one annotator, not a study participant), and the
72 LoRA checkpoints with their evaluation on a patient-disjoint 200-image set
(`outputs/model_eval/summary.csv`, generated 2026-09-19). No annotator behaviour data have
been collected (only developer test runs, which are tagged and excluded).

## Explanation of existing data
Images and reference annotations were produced for an unrelated segmentation project. The
checkpoints were trained (sequential warm start, 1 epoch per added image, lr 1e-3, LoRA r = 8,
3 patient-stratified random training orders) and evaluated before the annotator study; their
curves informed the choice of n = 1…128 but contain no annotator outcome data. Training orders
and the model-evaluation set exclude every patient of the study image pool (verified by
assertion in `prepare_experiment.py`).

## Data collection procedures
Annotators (clinicians / trained annotators, not involved in creating the reference
annotations) work remotely in a browser on a purpose-built web application (FastAPI +
Konva.js). For each image the app records active working time (loading, focus-loss pauses,
confirmation and rating time excluded), clicks, vertex add/move/delete counts (overall and per
structure), shape create/delete counts, mouse travel, undo/redo, zoom/pan, timestamped edit
events, a post-submission Paas 9-point mental-effort rating and the final geometry. Per-class
Dice, IoU, HD95, ASSD and Boundary-F1@2 px against the reference, the change from the proposal,
and the proposal's own precomputed reference metrics are stored server-side. Annotators
complete a background questionnaire before starting and a manipulation-check questionnaire
after finishing. Sessions may be spread over several days.

## Sample size
6 annotators × 60 images = 360 image-annotations (120 manual; 30 per n level; each image has
2 manual and 4 proposal annotations).

## Sample size rationale
Simulation-based power (`scripts/analysis/power_sim.py`, 300 replicates, crossed random
intercepts for annotator and image): with a manual→n=128 time ratio of 0.7 (−5 % per doubling
of n), log-scale residual SD 0.5 and annotator/image SD 0.3, power for H1 is 0.99 (0.67 for a
ratio of 0.8 at SD 0.5; 0.90 at SD 0.4); with a true ASSD difference of 0.3 px, margin 1 px and
residual SD 1 px, power for H2 at n = 128 is 0.96 (0.80 for a true difference of 0.5 px)
(`outputs/analysis/power_sim.csv`). Six annotators were the number available who had not
created the reference annotations.

## Stopping rule
Data collection ends when all six annotators complete all 6 study sessions. No interim analyses.

---

## Manipulated variables
Assistance condition (9 levels): manual (n = 0) or proposal from the checkpoint after n = 1, 2,
4, 8, 16, 32, 64, 128 annotated images (same n for all three structures of an image; training
order seed ∈ {0, 1, 2} balanced). Analysed as log2(n) for proposal items with manual as a
separate baseline.

## Measured variables
Primary: `duration_sec` (active working time per image).
Co-primary quality: per-structure ASSD (px) to the reference annotation.
Secondary effort: total clicks, vertices added/moved/deleted (overall and per structure),
shapes created/deleted, mouse distance, undo count, time to first action, idle time.
Secondary subjective: Paas effort (1–9).
Secondary quality: Dice, IoU, HD95, Boundary-F1@2 px per structure; for iris and pupil the
ellipse-parameter errors used in the iris-localisation / pupillometry literature (centre error
in px, major/minor axis errors, horizontal/vertical diameter errors, major-axis rotation error);
clinical indices MRD1, MRD2 and palpebral fissure height derived from the eyelid outline and
pupil centre, converted to mm with the reference iris horizontal diameter (HVID = 11.7 mm) and
compared with the reference (clinical tolerance ±0.5 mm, descriptive); correction magnitude
(Dice between proposal and final; area change).
Explanatory (precomputed): proposal Dice / ASSD / HD95 / BF@2 px / area difference to the
reference.
Covariates: gaze (frontal/peripheral), order within session, session index, seed, annotator, image.

## Indices
log(duration_sec); log2(n); redraw = shapes_deleted > 0; prop_assd_mean = mean of the three
structures' proposal ASSD.

---

## Statistical models
All mixed models use crossed random intercepts for annotator and image (REML; statsmodels
MixedLM variance components; if the annotator variance degenerates to 0, annotator enters as
a fixed effect — decided a priori). Code: `scripts/analysis/fit_models.py`.
H1 (proposal items): `log(duration_sec) ~ log2(n) + gaze + order_in_session + session_index +
seed + (1|annotator) + (1|image)`; one-sided test of the log2(n) slope < 0, α = 0.05.
Saturation: `a + b·exp(−n/τ)` vs linear-in-log2(n) on per-n means, AIC; n90 with cluster
bootstrap CI. Manual vs each n: 8 pre-specified contrasts (Holm), secondary. Gamma GLMM as
sensitivity for the time distribution.
H2 (per structure): `ASSD ~ condition(ref = manual) + gaze + random effects`; non-inferiority
of level n if the one-sided 95 % upper CI bound of (n − manual) < δ_structure. Fixed sequence
n = 128 → 64 → … stopping at the first failure; report n*. Dice (−0.01) and HD95 (+2 px) are
reported as supporting margins. H1 → H2 hierarchical; "faster and non-inferior" requires both.
H3: `final ASSD ~ proposal ASSD + gaze + manual ASSD of the same image (mean of the two manual
annotators) + random effects`; slope > 0 indicates carry-over. `redraw ~ log2(n)` logistic
mixed model as a supplement.
H4: `effort ~ log2(n) + gaze + random effects` (linear; cumulative-link as sensitivity).
H5: compare (a) `log(duration) ~ prop_assd_mean + covariates`, (b) `~ log2(n) + covariates`,
(c) both; report the prop_assd_mean coefficient and the attenuation of the log2(n) slope in (c).
Descriptive: inter-annotator agreement on manual items (two annotators per image),
gate-failure rate (ASSD > 2× inter-rater) per n, empty-proposal rate per n, and the model-side
curve (checkpoint Dice/ASSD/HD95/BF@2 px vs n on the patient-disjoint evaluation set).

## Transformations
Natural log of duration_sec; log2 of n. Boundary metrics in native-image pixels.

## Inference criteria
Confirmatory: H1 (one test) then H2 (fixed sequence per structure). Non-inferiority margins
δ_structure = 0.5 × the structure's inter-rater ASSD measured before the study on 20 images
annotated manually by the developer (not a participant) against the reference:
eyelid [ ] px, iris [ ] px, pupil [ ] px. All other outcomes: 95 % CIs and nominal p-values,
exploratory.

## Data exclusion
Practice sessions and the developer test account are excluded. Aborted sessions are discarded
by the application. If a session was redone, attempt 1 is used (a later attempt only if
attempt 1 is incomplete, reported). Empty proposals (possible at small n) are analysed as
proposal items (they are part of the dose). Sensitivity analysis excludes images with duration
> 5× the annotator-by-condition median or a heartbeat gap > 60 s; the main analysis keeps them.

## Missing data
The application blocks submission unless all three structures are present and the effort
rating is given. Any missing session (withdrawal) is reported and analysed as available-case
within the mixed model.

## Exploratory analysis
Per-structure dose–response (polygon vs ellipse editing), effort-vs-quality curves from
timestamped edit events, gaze effects, within-session learning trends, seed-to-seed variation
of the checkpoints, and the correspondence between the model-side curve and the human-effort
curve.

---

## Other
Code, analysis plan, design rules and the annotator guide are version-controlled
(`https://github.com/ykitaguchi77/HITL_validation_test`, private during data collection; to be
made public / archived with a DOI at publication). Patient images, the assignment file, the
proposal file and raw results are not shared publicly (file names embed patient identifiers);
de-identified per-image result tables will be shared at publication subject to ethics approval.
Ethics: Institutional Review Board of Osaka University Hospital (大阪大学医学部附属病院 倫理審査委員会),
approval No. 19492-7, approved 20 September 2022.
Superseded registration: https://osf.io/d7e2g (design changed before data collection; see top).
Embargo: [ 3 days ].

---

## Registration record
- v1 (superseded): https://osf.io/d7e2g (2026-09-16 19:30 JST; associated project https://osf.io/awgqf)
- v2: [ to be registered after `experiment.json` / `proposals.json` hashes, δ margins and power values are filled in ]
