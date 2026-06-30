# SegFormer学習パイプラインを患者リーク無しサブセットへ移植する
- type: technique
- created: 2026-06-16
- tags: [segformer, training, patient-leakage, data-split, venv, segmentation]

## 概要
既存の実証済み学習ノートブック(`train_SegFormerB1_Amodal_Blur_v3.ipynb`)を、
**~500/1000/1500/2000/2500枚の患者安全な nested サブセット**で再学習する自己完結スクリプトに
移植した際の知見。アブレーション/データ量スケーリング実験で再利用できる。

## やったこと・要点

### 1. 患者リークの正しい境界(最重要)
- patient_id = `filename.split('-')[0]`。リークは**画像単位ではなく患者単位**で判定する。
- test プールは「min annotated image_id ≥ TEST_START(=2500)」の患者(test-eligible)から作る。
  学習は **min annotated id < 2500 の患者のみ**から取れば、学習患者 ∩ test-eligible = ∅ を保証できる。
  (このデータでは 0-2499域と≥2500域にまたがる患者は1人だけ。境界をまたぐ患者は学習から除外。)
- **落とし穴**: リポジトリに転がっている `fold_indices.json` は別パイプライン(crossvalidation.ipynb)用で
  `patient_list.json` とインデックス体系が違い、**患者グルーピングされていない**(train/val に同一患者が混入)。
  B1学習ノートブックは inline で独自の患者分割をしている。**既製の fold ファイルを鵜呑みにしない**。
- nested(各サブセットが次の上位集合の部分集合)にすると「データ量↑で習熟度がどう上がるか」が
  同一系列で比較できる。

### 2. 検証を分割スクリプトに内蔵する
- サブセット生成時に **leak(test-used)=0 / leak(test-eligible)=0 を assert/print** して必ず確認。
  「枚数はちょうどでなくてよい」要件なので、患者単位で取ると端数(505,1020,1505,2007,2494)になるのは正常。

### 3. transformers のバージョン整合(venv)
- 学習コードが transformers 4.x 系前提なのに system が 5.x だと API 不整合でハマる。
- `python -m venv .venv --system-site-packages`(torch/cv2/albumentations は重いので system 継承)
  → その venv に `pip install "transformers==4.57.3"` でピン留め(system 5.x を上書き)。
- 速くて確実。torch+CUDA は system のものをそのまま使える。

### 4. B1 への移植で正常な挙動
- `nvidia/segformer-b1-finetuned-ade-512-512` から読むと
  `decode_head.classifier` の shape が [150,...] → [3,...] で**再初期化される warning は正常**
  (150クラスのADE20K head を 3クラス amodal head に置き換えるため)。
- 3ch amodal: ch0=Eyelid∪Caruncle union / ch1=iris全形 / ch2=pupil全形。
  損失は per-channel Tversky + pupil⊂iris 制約。AdamW 6e-5, AMP, mean val Dice で early-stop。
- checkpoint は `{"model": state_dict, ...}` 形式・num_labels=3 で保存すると
  webapp 側の推論(b1, num_labels=3)とそのまま互換。

### 5. 複数モデルの順次学習はモデル毎に別プロセス
- `for n in ...; do python train_subset.py --subset $n ...; done` をデタッチ実行。
  **1モデル=1プロセス**にすると終了時に GPU メモリが確実に解放され、次モデルが OOM しない。
- 本番前に必ず **スモークテスト**(`--limit 40 --epochs 2`)で一気通貫を確認してから起動。
- 時間見積もり: RTX 3080 Ti(16GB)で train445枚=~0.4分/epoch。学習枚数に比例。persistent Monitor で完了/エラーを監視。
  - **注意**: early-stop の best epoch は想定より遅く出ることがある(実測 seg500 は best @ep144、patience20 で実質 ~164ep まで回り約66分)。
    epoch/分 だけから「6〜10時間」と楽観しがちだが、best epoch が深いと **実際は 12〜16時間規模**になり得る。
    完全収束より時短を優先するなら patience を 10 に下げる/epoch 上限を設けると、ほぼ同等品質で数時間短縮できる。

### 6. nested サブセットの後付け拡張 & 2ジョブ並行学習
- サブセットを後から追加(例: 100/200/300 を `TARGETS` に足す)しても、**患者選択が決定的なら既存サイズの内容は不変**。
  実行中の大ジョブや既に学習済みの checkpoint に影響せず、追加分だけ別途学習できる(再生成後に既存 entry の不変を必ず確認)。
- 小モデルは速いので、大ジョブを止めず **別ログで並行起動**すると総所要を短縮できる。
  - B1・512px・固定 batch は 1プロセス ~5GB なので、**2本並行でも ~10GB < 16GB** で OOM しない(起動直後に `nvidia-smi` で空きを確認)。
  - OOM の兆候が出たら小ジョブを大ジョブ終了後の直列実行に切り替える運用に。

### 7. 「結果が良すぎる」時のリーク確認(真の held-out 患者で評価)
- 内部 val Dice が高すぎて不安な時は、**学習に一切出ていない患者(テスト域)で評価し直す**のが確定的な確認になる。
- リークがあれば未知患者の値は内部 val より**大きく落ちる**。**ほぼ同等〜わずかに低い**(正常な汎化ギャップ)なら**リーク無し**と判断できる。
  - 実例: seg500 内部val 0.971 → 真の held-out(120枚/29患者、患者完全分離)で 0.949。100→0.919/200→0.927/300→0.936/500→0.949 と素直な右肩上がりも傍証。
- 確認は3段で: ①各サブセットの内部 train/val が患者非重複(`train_pat ∩ val_pat=0`)②学習プールと test-eligible が患者完全分離 ③未知患者テストで内部valと整合。
- リーク評価は学習GPUを邪魔しないよう **CPU で別実行**してよい(`scripts/eval_on_heldout.py`)。
- **最終比較用の固定テストセット**は学習プールと患者単位で完全分離した test-eligible 患者から作る(`scripts/make_heldout_test.py` → `heldout_test.json`、画像/患者オーバーラップ0を検証)。
  - 注意: 全クラス注釈が揃う画像数が上限になる(本データは iris/pupil OBB XML が id≤3000 までで、test域の全注釈そろい画像は **463枚/37患者**が上限 → 「500枚」要求でも届かないことがある)。

## 再現メモ
- `scripts/make_training_subsets.py` → `outputs/training_subsets/subsets.json`
- `scripts/train_subset.py --subset {N} --out outputs/models/seg{N}.pth --epochs 300 --patience 20`
- 元コード: `C:\Users\CorneAI\Eyelid_Iris_pupil_seg_comparison\b3_v3_full_dump.txt`(ノートブックの text dump)

## 関連
- [[gaze-direction-from-iris-eccentricity]](同じ CVAT XML / 患者安全プールを使う)
- [[hitl-annotation-webapp-konva]](学習した seg{N}.pth を HITL 初期提示に使う)

## 関連リンク
- Experimental_record/20260616.md

## 更新 (2026-06-16)
- 参照: Experimental_record/20260616.md
- **データ量スケーリング比較は必ず「全モデル共通の固定テストセット」で測る**(最重要)。
  内部 val はサブセットごとに**検証患者が異なる**ため非単調になり、データ量との関係が見えない。
  実例: 内部 val は 500→0.971 / 1000→0.964 / 1500→0.953 / 2000→0.962 と乱れるが、
  **固定463枚 held-out で測り直すと素直に単調**: 100=0.919 / 200=0.923 / 300=0.936 / 500=0.947 /
  1000=0.950 / 1500=0.953 / 2000=0.958 / 2500=0.954(mean Dice)。
- 傾向: **500枚以降は収穫逓減**(500→2000 で +0.011)、ピークは seg2000、2500 はわずかに頭打ち。
  クラス別は pupil が最難(≤0.932)・eyelid が最易(〜0.977)。
- 全8モデル完了後の一括スコアリングは GPU 解放済みなので高速。`scripts/eval_on_heldout.py` を
  固定 `heldout_test.json` に向けて全 `seg{N}.pth` をループ評価 → `outputs/models/eval_final_463.log`。
- **落とし穴(フック)**: `echo "... eval ..."` の半角スペース付き `eval ` が secure フックの
  `eval`(シェル組込み)検出に当たり弾かれる。echo の文言を変えれば回避できる(スクリプト名 `eval_on_heldout.py` は下線続きなので無害)。
- **学習環境と推論(webapp)環境で transformers バージョンが違っても checkpoint は互換**:
  学習は `.venv`(transformers **4.57.3**)、webapp は system python(transformers **5.4**)で動く。
  `{"model": state_dict}` 形式・`from_pretrained(...num_labels=3...)` + `load_state_dict(ckpt["model"])` で
  保存/読込していれば、**4.57.3 で保存した checkpoint を 5.4 でそのまま推論できる**(seg500 で実証: eyelid 多角形・iris/pupil 楕円を生成)。
  ただし「配線したら必ず推論側の実環境で実モデル1枚を流して確認」する(バージョン差で読めないと配線が無意味になるため)。
- **配線(experiment.json / prepare_experiment.py)**: 実モデル確定後は MODELS の `placeholder` を解除し
  実 `seg{N}.pth` を参照、各モデルに `test_mean_dice`(固定テストの実測値)を付与しておくと後の集計で使える。
  最終 Dice 表は `outputs/models/heldout_dice.csv` のように CSV でも残す。
