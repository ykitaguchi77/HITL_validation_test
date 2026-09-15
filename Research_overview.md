# 研究進捗 Overview
- last_updated: 2026-09-15

## 研究概要
眼瞼（Eyelid/Caruncle）および虹彩・瞳孔（Iris/Pupil）のセグメンテーションを対象に、
**Human-in-the-Loop (HITL) アノテーションの効率が学習データ量（モデル習熟度）によって
どう変化するか**を検証する研究。ゼロからのアノテーションと、500/1000/1500/2000/2500枚で
学習した SegFormer-B1 をベースにした HITL とで、GroundTruth に対する Dice・所要時間・
クリック数・マウス移動距離・クラス別修正量などを比較する。データは
`Eyelid_Iris_pupil_seg_comparison` の CVAT アノテーション（画像 id 0-2999 が手動アノテ済み、
2500-2999 を test とする）を用いる。

## 現在の到達点
検証用の **HITLアノーテーション webapp を実装完了**（FastAPI推論バックエンド + Konva.js フロント、
ビルド不要）。CVAT風UIで polygon（Eyelid/Caruncle）・楕円OBB（Iris/Pupil）を編集でき、
ズーム/パン・頂点編集・中点挿入即ドラッグ・背景ドラッグパン・タッチ操作に対応。
UI操作性のバグ修正も実施: **未選択時はどこを掴んでも画像パン**（図形の塗りが画像を覆っても可）、
**楕円のリサイズ/回転/移動**（Transformer をパン処理と共存させ、ハンドルは拡大率非依存で掴みやすく）。
さらに **選択中ポリゴンへの点追加(統合)モード**（Shift+クリック、ダブルクリック/Enterで確定・Escで取消）と、
マスク表示とは独立した **塗りつぶし(中の色)ON/OFF トグル**（塗りOFFでも内部クリック選択は維持）を追加。
6 phase（scratch + HITL@500..2500）× 10枚 = 症例リーク無しの 60枚を test set から割当済み。
モデル推論→初期ベクタ提示、GT比較（per-class Dice/IoU）、全操作計測、JSONL+CSV保存まで
end-to-end で動作検証済み（SegFormer実推論 vs GT: eyelid/iris/pupil ≈ 0.98）。
また**セッション記録の Stop hook が文字化けで機能していなかった問題を修正**
（stdin を UTF-8 固定で読む。自己展開テンプレートにも反映）。
さらにアノテーション高速化のUI操作を追加: **点追加は最近接エッジへ挿入**（自然にエリア拡張）、
**クラス選択で既存同クラス図形を自動active化**、**スペースキーで点打ち・矢印キーで1px微調整・
ウィンドウフィット**。加えて、各 phase の **視線方向構成を「正面視7+周辺視3・提示順ランダム」に固定**
する実験設計を実装: 視線メタデータが無いため**虹彩偏心度**（虹彩OBB中心 − 瞼bbox中心、瞼サイズで正規化、
**プール中央値で de-baseline** して解剖学的縦オフセットを除去）から `ECC_THRESHOLD=0.20` で
正面/周辺を自動分類し、患者リーク無しプール463枚（正面270/周辺193）から `experiment.json` を再生成済み。
さらに**HITLサブセット5モデルの学習パイプラインを構築し本番学習を起動**(バックグラウンド・数時間規模)。
参照ノートブック(`train_SegFormerB1_Amodal_Blur_v3`)のロジックを B1・サブセット対応に移植し
(`scripts/train_subset.py`)、**患者リーク無しの nested サブセット**(505/1020/1505/2007/2494枚、
学習患者 ∩ test-eligible = 空、`scripts/make_training_subsets.py` で全リーク検証 PASS)を生成、
transformers 4.57.3 ピン留めの `.venv` で順次学習中。**seg500 は完了**(best mean val Dice **0.971** @ ep144・約66分 → `outputs/models/seg500.pth`)、現在 seg1000 を学習中。best epoch が想定より遅く、総所要は約12〜16時間の見込み。
さらにユーザー要望で**小サブセット 100/200/300 を追加**(`TARGETS` 拡張で再生成、100=100枚/9患者・200=204/15・300=312/23、**全リーク検証 PASS・nested 維持・既存500〜2500は不変**)し、**大ジョブと並行**で別ログ(`train_small.log`)学習を起動。GPUは 2プロセス並行で 9.5GB使用/6.7GB空き(16GB)で**OOM無し**。**seg100 完了**(best mean val Dice **0.922** @ ep136 → `outputs/models/seg100.pth`、※val 1患者のため参考値)、**seg200 完了**(best mean val Dice **0.937** @ ep70 → `outputs/models/seg200.pth`)、現在 seg300 学習中。データ量↑で素直に改善傾向(100→0.922 / 200→0.937 / 500→0.971、参考: 旧full3000=0.945)だが、各サブセットで val 患者が異なるため**最終比較は共通テストで実施**する。最終的に **8モデル(100〜2500)** が揃う予定。
「結果が良すぎる」という懸念に対し、**学習に一切出ていない患者(真の held-out 120枚/29患者、患者完全分離)で再評価しリーク無しを確認**(seg500: 内部val 0.971→未知患者 0.949 で正常な汎化ギャップ、100→0.919/200→0.927/300→0.936/500→0.949 と単調増加)。また**最終比較用の固定 held-out テストセット**を作成(`scripts/make_heldout_test.py` → `outputs/training_subsets/heldout_test.json`、学習と画像・患者オーバーラップ0)。全注釈そろい画像の上限により **463枚/37患者**(iris/pupil XML が id≤3000 まで、500枚には届かず)を採用。全8モデル完了後にこの463枚で最終 Dice を一括算出する。
**全8モデルの学習が完了**し、学習プールと患者・画像が完全分離した**固定 held-out 463枚/37患者で全モデルを一括スコアリング**(`outputs/models/eval_final_463.log`)。共通テストで測ると内部 val の非単調性は解消され、**データ量に対し素直に単調改善**する効率カーブを確定した(mean Dice: seg100=0.919 / 200=0.923 / 300=0.936 / 500=0.947 / 1000=0.950 / 1500=0.953 / **2000=0.958(ピーク)** / 2500=0.954)。**500枚以降は収穫逓減**(500→2000 で +0.011)、クラス別は pupil が最難(≤0.932)・eyelid が最易(〜0.977)。
**残タスクだった MODELS 差し替えも完了**: `experiment.json`/`prepare_experiment.py` の `MODELS` を
full3000 プレースホルダから実 `seg{N}.pth` へ差し替え(`placeholder=false`、各モデルに固定463枚の
`test_mean_dice` を付与)、最終 Dice 表を `outputs/models/heldout_dice.csv` に保存。さらに、学習は
`.venv`(transformers 4.57.3)・webapp は system python(transformers 5.4)とバージョンが異なるため、
**system python で実 checkpoint(seg500)を読み込み推論できることを実環境で検証**(eyelid 多角形・
iris/pupil 楕円を生成、caruncle 空=仕様通り)。これで学習→配線→HITL初期提示まで一気通貫。
**HITLモデル学習フェーズは完了**。残るは、seg100/200/300 を実験フェーズに追加するか(現状は scratch+
HITL@500..2500 の6フェーズ、100/200/300 はデータ効率カーブの参照点として登録のみ)のユーザー確認、
ablation の vanilla U-Net 学習、そして実アノテーション施行・統計解析。
直近セッションでは**実験設計(ブラインド vs ノンブラインド提示)の相談**を行い、**盲検方式の方向性が確定**した。
期待バイアス・画像難易度交絡・scratch は盲検化不可能(部分盲検のみ)を整理し、私(Claude)の推奨を提示。さらに
**Gemini(flash)のセカンドオピニオンを取得し 5論点すべてで Claude と一致**(ブラインド混合/scratch別建て/
画像難易度交絡が残存脅威/ラテン方格/ハイブリッド)、設計の頑健性を確認した(Codex は ChatGPT アカウントの
モデル制約=`gpt-5`/`gpt-5-codex` 非対応・`o4-mini` 400 で未取得)。これを受け**ユーザーが Q1 を決定**:
**scratch は別建ての基準・8つの HITL モデル間は盲検ランダム混合提示・条件は内部ログ、提示単位は1セッション
=10枚(正面7+周辺3)**。実装はハイブリッド(ブラインド混合モード)方向で確定。残るは **Q2(アノテータ人数・
前向き研究化の是非・パイロット要否・推奨解析=混合効果モデル等)**。Codex は再依頼も全モデル非対応で取得できず
(Gemini もクォータ枯渇)、**Claude の Q2 推奨のみ提示**(前向き化=軽量に・事前固定/アノテータ3〜5名/専用
パイロット不要=1人目を内部パイロット化し本解析に組入れ/解析=画像をランダム効果に含む混合効果モデル)。
設計確定用の2点を提示したところでセッション終了=**ユーザー回答待ち**。Q2 確定後に `prepare_experiment.py` を
9フェーズ・90枚で再生成し、混合モードUIを実装する。
**直近セッションで Q2 を含む実験設計を確定し、盲検実験仕様へ webapp を作り直して end-to-end 検証まで完了**した。
確定設計: **アノテータ3名・GT作成者除外**、1セッション=10枚(正面7+周辺3)、**練習1 + scratch1 + HITL8 = 9セッション**を
**3×9 Latin 方格**でアノテータ×条件均衡化、**scratch はセッション0固定の別建て基準**、HITL 8条件(seg100..2500)は
**盲検でシャッフル混合提示**(モデル名/条件/ブロックは API でクライアントへ出さず正解はサーバ側のみ保持)。
**練習セッション**(5枚=正面3+周辺2/seg1000・`is_practice=true` で解析除外・本番と画像非重複)を追加し、
**練習でのみ GT オーバーレイ + per-class Dice を表示**(本番は GT/Dice 非表示=期待バイアス除去)。
`scripts/prepare_experiment.py` を上記仕様で書き直し(全 assertion PASS)`experiment.json` を再生成、
backend(`main.py`/`inference.py`(キャッシュ4→9)/`session.py` に解析カラム追加)とフロント(アノテータ選択・
順序固定セッションピッカー・モデル名秘匿・Dice 抑制・練習 GT 表示)を実装。**実サーバ + Playwright で盲検リーク
ゼロを機械確認**(DOM/全 API でモデル名・条件・ブロック非露出、保存記録にのみ隠し正解; 練習は GT+Dice 表示)。
**HITL モデル学習・実験設計・盲検 UI 実装まで完了**。残るは ablation の vanilla U-Net 学習、実アノテーション施行・統計
解析(混合効果モデル)。なお Codex/Gemini への設計セカンドオピニオン照会はツール問題(401/モデル非対応・429クォータ)で
結局取得できず、設計判断は Claude 自身の分析に基づく。任意拡張として predict 結果の事前計算による**タイミング・
サイドチャネル対策**(盲検の潜在漏れ)を計画明記(未実装・推奨)。
直近セッションで、実アノテーション運用を見据えた**操作性改修を完了・実機検証**(**Caruncle 廃止=Eyelid∪Caruncle 統合で3クラス化**・
**推論プレフィルの eyelid ポリゴン点数を16→38点(約2.4倍, eps 0.004→0.0015)**・**選択中クラスを `moveToTop` で最前面化して重なり部でも編集可**・
**クラス選択は右タブのみ(canvasクリック無効)**)。`config.py`/`geometry.py`/`tools.js`/`app.js` を編集し、**実サーバ + Playwright で全4点を機械確認済み**
(GT eyelid は Eyelid+Caruncle 統合の2ポリゴンでモデル eyelid チャンネルと一致)。`experiment.json` はクラス情報を持たず再生成不要。
続けて、**プレフィル点を等弧長リサンプリングで均等化**(eyelid 約58点・間隔ほぼ一定 std≈1.1px、曲率ベース approxPolyDP の不均等を解消)し、
「ポリゴン選択中に別クラスが選択される」というユーザー報告は**コードでは既に解消済み**(Playwright 実証: 選択はサイドバーのみ)で、
真因が**ブラウザの旧JSキャッシュ**だったと特定。`main.py` に **no-cache ヘッダ**を追加して解消した(`geometry.py`/`main.py` 編集)。
セッション末尾ではさらに2点を実装・実機検証: **GT 表示の Eyelid/Caruncle 内部境界を消すため練習GTの eyelid を Eyelid∪Caruncle の統合外形1本に変更**(`main.py`、75点・等間隔)と、**右サイドバーに明るさ・コントラスト調整スライダーを追加**(`canvas.js`/`index.html`/`app.js`/`style.css`、Konva の Brighten/Contrast フィルタを `imageNode.cache()` 後に適用し画像切替をまたいで値を保持)。Playwright で両機能を機械確認。最後にユーザー確認(「再実行して確認します」)のためサーバを再起動し `classes=[eyelid,iris,pupil]/annotators=[1,2,3]` を確認、`localhost:8000` 稼働状態のまま継続。
さらに**練習1例目の GT 遅延ポップインを解消**: 初回推論のコールドロード(数秒)で編集開始後に GT が遅れて出ていた問題に対し、(1)**画像+プレフィルが揃うまで入力をブロックする `#loading-overlay`(z-index 30・「推論中…」)**、(2)**起動時のモデル事前ウォームアップ**(daemon thread `_warm_models()`、warm predict 0.07〜0.17秒)、(3)**計測タイマーを準備完了後に開始**(推論/画像ロード待ちを作業時間 duration に非計上)を実装(`main.py`/`index.html`/`style.css`/`app.js`)。Playwright + curl 計測で検証。
最後に**練習を2部構成へ再設計**し(練習1「Scratch(ゼロ描画)」+ 練習2「修正(seg1000予測を直す)」、各 正面2+周辺1=3枚・提出ごとに GT 点線表示・解析除外)、両ワークフローを必ず練習させて習熟差の交絡を低減。さらに**「動作テスト用」擬似アノテータ**(`test`、表示名「動作テスト用(本番に含めない)」)を追加し、割当はアノテータ1と同一だが記録は `outputs/results/test_*/`(annotator="test")へ分離してリハーサルが本解析を汚さないようにした(`prepare_experiment.py` の `PRACTICE_SPEC`・`main.py` の `RUN_ALIAS`/`UI_ANNOTATORS`・`app.js`、`experiment.json` 再生成)。**セッション終了時点でサーバは `localhost:8000` 稼働中(実アノテーション施行待ち)**。
直近セッションでは、実アノテーション直前の**運用UI調整**を実装し**実機検証まで完了**した: **ウィンドウ最大化(画像フィット)と塗りつぶし無しを既定化**・**練習モードの再実行を可能化**・**提出ボタン横に赤い「中断」ボタンを追加**・**中断時はセッション情報を完全リセット**(中途半端な計測値を本解析へ混入させないフォールバック、backend に `/api/abort` 追加。中断したセッションは記録フォルダごと削除し未完了状態へ戻す/パストラバーサルもガード)。`canvas.js`/`index.html`/`style.css`/`app.js`/`main.py` を編集し、**実サーバ + Playwright で全5点を機械確認**(起動時 scale=2.34 で fill・showFill=false・練習は完了後も再実行可・赤い中断ボタン動作・中断で記録破棄)。
続けて、**完了済セッションのやり直し(フォールバック)＋試行回数(attempt)の記録**を実装・検証した: ユーザー要望で**完了済セッションもクリックでやり直し可(確認アラート付き)**にし、設計判断として**中断(部分破棄)とは別物**として扱い**前の記録は消さず attempt 番号(1,2,3…)を付けて新規記録**する方式に(`session_id` を `{annotator}_{key}_a{attempt}_{stamp}` 形式にして上書き防止、試行回数は localStorage で管理、UI に「(N回目)」「[N回完了・やり直し可]」表示)。attempt を**データファイル両方(`records.jsonl`・`summary.csv` の `attempt` 列)に保存**し、解析時に試行を区別可能にした(`app.js`/`main.py` の `SubmitReq.attempt`/`session.py` の `_BASE_COLS`・`_flatten` を編集)。**サーバ再起動後に実 API で end-to-end 検証**(`attempt=3` が JSONL・CSV 3列目に到達することを確認、検証記録は削除)。セッション末尾でサーバは `localhost:8000` 稼働中。
最後に、やり直しは“どうしても必要な場合のみ”という運用方針を受け、**完了済セッションの「やり直し可」「[N回完了]」表示を撤去**して「✓ ラベル (N枚)」のみに簡素化(`app.js` のボタンラベルのみ・フロント変更)。やり直し機能本体(クリック→確認アラート→最初からやり直し、内部 attempt 計上と `records.jsonl`/`summary.csv` 記録)はフォールバックとして温存し、UI で積極的に勧めないだけの調整。
最後に、実アノテーション開始前の確認として**モデル・データの収納レイアウトを棚卸し**(調査のみ・コード変更なし): モデルは `outputs/models/seg{100..2500}.pth`(8 ckpt・約52MB、評価 `heldout_dice.csv`/`eval_final_463.log`、`experiment.json` の `models` に絶対パス登録)、入力画像は別プロジェクト `Eyelid_Iris_pupil_seg_comparison/Images/images`(git管理外)、サブセット定義は `outputs/training_subsets/{subsets,heldout_test}.json`、実験割付は `scripts/webapp/config/experiment.json`(SEED=42・90枚盲検・3×9 Latin方格・runs/practice 内包)、収集結果は `outputs/results/<session_id>/`(`{annotator}_{key}_a{attempt}_{stamp}`、各 `records.jsonl`+`summary.csv`)。現状 `outputs/results/` の4フォルダは annotator「1」の動作確認分(本番未収集)で、**本番開始前に削除するかをユーザーへ確認 → 回答待ち**。
続けて**3名アノテータへの配布方法を相談**し、GPU・モデル・医用画像を持つサーバは1台据え置きのまま **Cloudflare Tunnel で `localhost:8000` を外部公開 + HTTP Basic 認証**でブラウザ配信する方針を推奨(デスクトップ配布は非現実的で不採用方向、quick tunnel のURLは再起動ごとに変わるため安定URLには named tunnel が必要)。**推奨提示段階でセッション終了**＝認証追加・トンネル起動・URL配布の実装は次セッション。
直近セッションでこの**配布構成を実装・実機検証まで完了**した: `main.py` に **共有パスワード HTTP Basic 認証**を追加(`HITL_AUTH_PASS` 環境変数があれば API・静的ファイル両方を保護、未設定の localhost 開発時は認証なし＋起動時「access control DISABLED」警告で設定忘れ防止、失敗時 401＋`WWW-Authenticate` 返却)。**認証なし→401/誤り→401/正→200** を実機確認。あわせて**一括起動スクリプト**(`scripts/webapp/run_server.ps1`: `$Pass` を書換え実行 → uvicorn 起動 + `cloudflared tunnel --url http://localhost:8000` で公開URL発行)、**管理者向け運用手順**(`README_deploy.md`)、**アノテータ向け配布資料**(`annotator_guide.md`: ログイン→アノテータ選択→練習2種→Scratch→Session1〜8 の順序・3クラスの描き方・操作表・盲検説明)を作成。検証後はローカル開発挙動へ戻すためサーバを認証なしで再起動。**これで実アノテーション配布は即時開始可能**(残課題: quick tunnel URLは再起動ごと変動するため固定URLには named tunnel が必要、`outputs/results/` の test 記録4フォルダの削除可否は引き続き保留)。続けてユーザーが `$Pass` を本番値に書換え済みであることを確認し、**PowerShellに不慣れでも使えるダブルクリック起動用 `scripts/webapp/run_server.bat`**(chcp 65001 + `powershell -ExecutionPolicy Bypass -File run_server.ps1` + pause)を作成した。最後に **`run_server.bat`→`run_server.ps1` の起動を Cloudflare 公開URL経由まで通して end-to-end 検証**(バッチから uvicorn 起動・PW `hitl` 子プロセス継承・公開URL `pilot-bookstore-lyrics-workout.trycloudflare.com` 発行 → 公開URLで 認証なし401/`annotator:hitl`200/トップ200 を確認)。起動ログの `classifier MISMATCH`(3クラス用ヘッド再初期化=設計どおり)・`cert.pem ERR`(クイックトンネルでは無害)は正常と切り分け説明し、**テスト用トンネル＋uvicorn は医用画像公開を放置しないため停止**して終了。これで実アノテーション配布は即時開始可能。
直近セッションでは、プロジェクトを **git 管理下に置き初回コミット**した(ユーザー依頼「commit、画像は外して push」)。
医用研究のため「画像を外す」だけでなく、**ファイル名に患者IDが埋め込まれた識別情報**(`experiment.json`・
`outputs/training_subsets/`・`outputs/results/`)と**患者由来の大容量モデル `*.pth`(419MB)**・`.venv`・
ジャンクファイルを `.gitignore` で除外、安全なログ・研究ノート・コード・集計 `heldout_dice.csv` のみ保持。
**コミット前にステージ内容を機械検証**(ジャンクファイルがパターン不一致で混入→パターン修正で除外)し、
**`master` に初回コミット(4716de3・49ファイル、患者データ/モデル/画像すべて除外済み)**。続けて、ユーザーが作成した
空 private リポジトリ `https://github.com/ykitaguchi77/HITL_validation_test` へ `git remote add` / `branch -M main` /
`push -u` を **GCM のブラウザ1回サインインで実行し push 成功**(`gh` CLI 自動インストールは UAC 中断で失敗したが不要だった)。
**push 後にリモートを機械検証**(HEAD `4716de3` がローカル一致・リモート 49ファイル・機微検索ヒットは `make_training_subsets.py`
=スクリプト本体で患者データ無しのみ)し、患者由来でない成果物のみが Private リポジトリに安全にバックアップされたことを確認。
直近セッションでは、実アノテーション施行前の確認として**タスク中の記録項目を棚卸し**(調査のみ・コード変更なし)。
1画像提出ごとに `outputs/results/<session_id>/` へ `records.jsonl`(ロスレス・ジオメトリ/初期予測含む)+`summary.csv`(解析用フラット表)の2形式で、
①識別・実験条件(盲検の隠し正解 condition/model/train_size/block を含む)②操作計測(duration_sec は推論待ち非計上・mouse_distance はズーム非依存・クラス別内訳)
③精度スコア(per-class Dice/IoU・HITL 修正量 correction_dice/area_change)④JSONL 限定の再解析用項目、が保存されることを確認。
**研究概要の比較指標はすべてカバー済み**と結論。軽微な残骸として `metrics.js:8` に廃止済み `caruncle` キーが残存(実害なし・1行削除で解消可)を発見。
続けて「既報で他に計測が望ましい項目が無いか」の**文献調査(deep-research ワークフロー)を実施し完了**
(25主張を 3-0 全会一致検証・一次情報源19件)。既報と比べた欠落は**5系統**と判明: ①主観的作業負荷(NASA-TLX/SUS・最優先)
②境界距離品質(HD95/ASSD/Surface-Dice・保存済みポリゴンからオフライン計算可)③アノテータ間/内一致度(反復設計が必要)
④品質正規化した労力(NoC@IoU・編集ごとタイムスタンプで修正労力vs品質曲線)⑤交絡対策(ウォッシュアウト期間・**オートメーション
バイアス**=低データモデルの誤予測初期提示は実在の脅威)。追加実装の推奨は NASA-TLX と境界距離オフライン計算が上位(いずれも
既存記録設計への影響小)。続けて**ユーザーと各論点を詰め、本プロジェクトへの実装方針を確定**した(調査・設計のみ・未実装):
**①主観負荷=フルNASA-TLXは重すぎ→Paas 9段階単一項目を全画像・submit後に分離**(8 HITL セッションが condition-mixed で
画像ごとに取るしかないため)、**②境界距離=許容幅3px固定・眼瞼のみ**(瞳孔/虹彩は負荷考慮で対象外)を保存済ポリゴンから
オフライン計算、**③NoC翻訳=編集イベントのタイムスタンプで修正労力vs品質曲線**、**④オートメーションバイアスは後付け解析で対応**
(scratch基準比較+最終Diceが初期予測品質に相関するか)、**⑤再現性=後半に同一条件5枚再掲で個人内 test-retest**。実装見取り図は
[タイムスタンプ記録(metrics.js)→Paas単一項目(front+session.py)→境界指標(scoring.py)→再掲5枚(prepare_experiment.py)]の順。
**主観負荷を単一項目で全画像とする1点の合意をユーザーに確認提示 → 回答待ち・実装未着手**。
続く同日セッションで**全方針にユーザー合意**(「はい、それでいきましょう」)。あわせて**境界許容幅を 3px→2px に変更**
(「3px 以上は意味がある=実誤差、2px 以内を一致」)し、境界指標の最終仕様を **眼瞼のみ・Boundary-F1(Surface Dice)@2px・
HD95/ASSD は生の距離値併記** で確定。合意後に実装フェーズへ入り `scoring.py`/`geometry.py`/`app.js`/`index.html` を
読み込んで構造把握したが、**ファイル編集は未実施のままセッション終了**(4段=タイムスタンプ記録→Paas単一項目→境界指標@2px→
再掲5枚 は次セッションで着手)。
直近セッションで**追加計測5項目の実装をすべて完了し end-to-end 検証まで済ませた**: ①編集イベントのタイムスタンプ
`events[]`(`{t,type,cls}`)+初動 `time_to_first_action_sec`/アイドル `idle_time_sec` の自動導出(`metrics.js`)、
②眼瞼のみの境界指標 **HD95/ASSD/Boundary-F1@2px**(scipy 不在のため cv2.distanceTransform で実装=新規依存なし、
判別性検証: 同一→F1=1.0/HD95=0・1pxズレ→F1=1.0・5px→F1=0.5/HD95=5・空→None)(`scoring.py`)、③**Paas 9段階の
努力尺度モーダル**(submit→metrics スナップショットで duration 確定→タイマー停止→モーダルの順で回答時間を作業時間に
非計上)(`index.html`/`app.js`/`style.css`)、④summary.csv へ `is_repeat`/`time_to_first_action_sec`/`idle_time_sec`/
`effort`/`eyelid_hd95`/`eyelid_assd`/`eyelid_boundary_f1` 列を追加・JSONL に `events[]` 無損失保存(`session.py`/`main.py`)、
⑤**再現性用の「Session 9」**=各アノテータへ既出 HITL 画像5枚を同一条件で盲検再掲(`is_repeat` タグ、**専用RNGで既存90枚
割当・練習は不変**のまま `experiment.json` 再生成・audit 全 assertion PASS)(`prepare_experiment.py`)。検証は backend
パイプライン(GT提出→dice=1.0/HD95=0/F1=1.0、effort・初動・アイドル・events が CSV/JSONL 到達)+実サーバ+Playwright
(scratch で描画→提出→モーダル9ボタン→評価7→記録→次画像へ前進、JSエラーなし)+盲検維持(`/api/run`/`/api/session` の
再掲セッション応答に condition/model/is_repeat 非露出=「Session 9」5枚としか見えない)まで機械確認。検証用 test 記録は
削除しテストサーバ停止(2026-06-30 の `test_p_*` 2件は棚卸し保留のため温存)。オートメーションバイアスは実装せず
`correction_dice`/`area_change` と最終 Dice の相関による**後付け解析**で対応する方針を維持。続けてユーザー再確認を受け、
**境界指標を眼瞼のみ→全3クラス(eyelid/iris/pupil)へ拡張**した(当初は負荷考慮で眼瞼のみとしたが、境界指標は保存済みマスクからの
オフライン計算でアノテーター負担ゼロのため絞る理由が無いと整理)。楕円(虹彩/瞳孔)は `cv2.ellipse` で塗りつぶし→**マスク境界のずれ**を
測る方式(眼瞼と同じ土俵。パラメータ直接比較ではない)。`scoring.py` を全クラス算出へ、`session.py` を眼瞼ハードコードから
**per-class 共通カラム**(`{k}_hd95`/`{k}_assd`/`{k}_boundary_f1`)へリファクタし、3クラス×3指標の列生成と GT 提出時の
HD95=0/ASSD=0/F1=1.0 を検証済み(瞳孔は小さく Boundary-F1@2px が甘めに出る点は認識、HD95/ASSD の絶対px値が有用)。
最後に主観負荷指標の仕様確認応答(画像ごと Paas 9段階=submit 後モーダル・回答時間は duration 非計上・`effort` 列)を行い、
**努力尺度の目盛りを 1–9(Paas 1992 そのまま)で確定**(0–10 の臨床 NRS も候補だったが論文での「single-item cognitive load scale (Paas)」引用可能性を優先。現行実装が既に 1–9 のためコード変更不要)。
これで**計測系の拡張・主観負荷尺度がすべて確定・実装・検証済みとなり、残るは ablation の U-Net 学習と実アノテーション施行・統計解析**。
直近セッションでは、ローカル起動での動作確認中にユーザーが気づいた**計測バグを1件修正**した:
**ゼロから点を打つ scratch 描画(`tools.js` の `_polyClick`)が頂点追加を計上しておらず**、
既存ポリゴンへの点追加(`_extendClick`)だけが `vertexAdded()` を呼んでいたため、**scratch では
`vertices_added=0`** となり scratch vs HITL の労力比較が成立しない非対称があった。`_polyClick` の
初点・追加点の2箇所で `metrics.vertexAdded()` を呼ぶよう修正し、実サーバ + Playwright で
**ゼロから4点→`vertices_added=4`・クラス別 `eyelid.vertices_edited=4`・`events[]` に `v+` 4件**を確認
(フロントのみ変更・no-cache で稼働中サーバへ即反映)。あわせてユーザーから**複数頂点選択
(Ctrl+ドラッグ marquee)+まとめてカーソル移動**機能の有無を問われ、**現状は単一頂点操作のみで未実装**と
切り分け、想定仕様(選択中1ポリゴンの矩形内頂点を複数選択→まとめて移動/`vertices_moved` 計上・
1ジェスチャ=1 undo・Esc 解除)と確認2点を提示。ユーザー回答(スコープ質問=選択範囲の意味/Ctrl+ドラッグ=OK)を得て
**同一セッション内で実装・実機検証まで完了**した: スコープ **A(選択中1ポリゴンの頂点のみ・隣クラスの点は矩形内でも無視)**で、
`canvas.js` の `PolygonShape` に複数選択状態+まとめて移動メソッド、`tools.js` の `ToolController` に Ctrl+ドラッグ marquee 選択・
グループドラッグ・矢印キー微調整・Esc 解除・1ジェスチャ=1 undo・ツール切替時の marquee 掃除を配線。実サーバ + Playwright で
**上辺2頂点だけ選択→まとめて移動(`vertices_moved=2`・下2頂点不動)・Esc 解除・undo 復元**を機械確認(undo は `restore()` で図形
再構築のため検証は undo 後に図形を読み直して再選択)。これで scratch/HITL の頂点編集計測の対称性と複数頂点編集の操作性が揃った。
続けてユーザー要望で**計測タイミングの衛生を2機能で強化**した: **①フォーカス喪失(タブ切替/最小化=`visibilitychange`＋他アプリへの
`blur`)で計測を一時停止**(タイマー・全カウント・マウス移動距離の加算を止め、戻ると自動再開、非アクティブ経過は `duration_sec` から除外し
`paused_time_sec` に計上、復帰直後のカーソル飛びは移動距離に非加算、努力尺度モーダル中/保存中=`timing=false` は誤停止しない、`#pause-overlay`
で canvas をブロック)、**②席外し監視 heartbeat**(アクティブ中 15秒ごとに `{t,wall}` を JSONL `heartbeats[]` に記録=タブを開いたまま席を立つと
一時停止はかからず heartbeat は継続する一方で操作イベントが途切れる→`idle_time_sec` と併用して「PC前にいるが無操作」と「席/画面を離れた」を区別可能)。
`metrics.js`/`app.js`/`index.html`/`style.css`/`session.py`(`paused_time_sec` 列追加)を編集し、実サーバ + Playwright で**350ms停止→duration除外
(アクティブ0.29s)・`paused_time_sec=0.35`・非アクティブ中の700pxカーソル移動は非加算(5pxのみ)**、backend 再起動後の実API往復で `paused_time_sec`/
heartbeat/events の記録到達まで機械確認。**セッション終了時点でサーバは `localhost:8000` 稼働中(実アノテーション配布可能)**。
最後に**Cloudflare 遠隔配信の現状を確認応答**(6/24 実装済み=quick tunnel + 共有PW Basic 認証・`run_server.bat` 起動で今セッション追加分もそのまま遠隔反映=別途デプロイ不要)。ただし**`annotator_guide.md` のセッション数が古い(再掲 Session 9 追加で 1〜8 → 1〜9)+新操作の追記が望ましい**点を提示。ユーザー依頼を受けて**配布資料 `annotator_guide.md` をセッション1〜9(全12セッション)構成へ更新**し、あわせて新操作(Ctrl+ドラッグの複数頂点まとめ移動・別ウィンドウ切替で自動一時停止)を操作表・提出注記へ追記(盲検上 Session 9 が再掲である旨は伏せて普通の本番セッションとして記載)。これで URL+共有PW+本資料をセットで3名へ即配布可能。**残るは ablation の vanilla U-Net 学習と実アノテーション施行・統計解析**。
セッション末尾ではさらに2点をユーザー指摘で改善・実機検証: **①提出フローを「提出(=タイマー停止)→確認画面(3択: 確認OK・次へ/修正する/中断)→苦痛(Paas 1–9)の記録→保存」へ再構成**(`index.html`/`style.css`/`app.js` の `submit()`+`_confirming` フラグ。確認・負担度回答・修正時の確認レビュー時間は `duration_sec` 非計上、「修正」で編集へ戻ると計測再開。Playwright で 提出→確認→修正→再提出→確認OK→負担度→保存 の全経路を機械確認。既知の小さな限界: 修正時の確認レビュー時間は `paused_time_sec` に少量混入)、**②再掲 Session 9 を 5枚→10枚(正面7+周辺3)へ拡張**(5枚だけ異質で盲検上目立つため他セッションと不可区別に。`prepare_experiment.py`+audit assertion 更新・`experiment.json` 再生成 全PASS・サーバ再起動後に実 API で Session 9=10枚を確認)。あわせて `annotator_guide.md` の「提出と中断」節を新確認フローへ更新。最後にユーザー指摘でさらに2点を改善・実機検証: **③確認アクションを右上ボタンへ集約**(中央3ボタンダイアログを廃止し、「提出」ボタンが確認中は「確認OK・次へ →」ラベルに変化・確認中のみ「修正」ボタンを表示・中断は既存ボタン流用。`index.html`/`app.js`)、**④練習の GT マージを最初の確認画面へ前倒し統合**(提出直後の確認画面で GT+per-class Dice を表示し**二度目のマージ確認を廃止**、保存せず GT だけ返す軽量エンドポイント `/api/practice_gt` を追加し**本番セッション画像には 403 で GT を出さず盲検維持**。`main.py`/`index.html`/`app.js`)。実サーバ + 実API + Playwright で 本番=確認にGTなし/練習=確認画面に GT+Dice 表示・二度目確認なし・`/api/practice_gt` は本番403/練習200 を機械確認。仕上げにさらに2点を実装・検証: **⑤提出時に全ポリゴン/楕円の選択を解除**(`submit()` で確認オーバーレイ前に `tools.deselect()`=確認画面をアンカー無しのクリーン外形で提示)＋**3クラス未完成での提出ブロック**(`_missingClasses()` で未入力クラスをアラート明示し早期 return)。実サーバ + Playwright で まぶただけ→アラートで確認画面が開かず / 3クラス揃い→確認画面へ・全選択解除(selected/vsel/vselMulti=null)を確認。最後に、この「3クラス必須」ガードが**眼瞼下垂などで瞳孔が完全に隠れた症例と矛盾しないかをデータセット全体で機械検査**し、**実験96画像・候補プール463枚はいずれも瞳孔欠損ゼロ=ガードは安全**、隠れ瞳孔症例(iris注釈4467枚中1504枚が瞳孔なし・部分隠蔽8枚は患者161/162/166/198/223)は ID範囲2500–2999・患者分離・虹彩ありというプールの絞り込みで自然排除されていると確認(プールに瞳孔明示要求を足す任意の保険は未実装で保留)。**セッション終了時点でサーバは `localhost:8000` 稼働中・実アノテーション配布可能な状態**。
2026-07-13 は主に運用対応と1件の設定変更: 手元起動の**ポート8000 bind エラー(WinError 10048)**を前セッション残存の検証用 uvicorn 停止で解消し、再起動の正常性(`num_labels=3`/`HF_TOKEN`/末尾 `Shutting down` はすべて設計どおり・正常)と認証情報の在り処(`run_server.ps1` の ID=`annotator`/PW=`hitl`(仮))を確認応答。ユーザー依頼で**アノテータを実名3名(kubota/maeda/kaisho)へ変更し練習用(test)を先頭に配置**(`prepare_experiment.py` の `ANNOTATOR_NAMES`・`main.py` の `UI_ANNOTATORS`・`app.js`、experiment.json 再生成・audit 全 PASS、割付構造は不変)=**要サーバ再起動で反映**。最後に「校正モードでマスクが2つずつ生成される」報告を徹底調査したが**現行コードでは再現せず**(バックエンドは1クラス1形状・Konva 実ノードとサイドバーは常に 1/1/1・練習 p_hitl の実線+GT点線の重なりは仕様どおり)、最有力原因は**旧JSキャッシュ or 更新後コードで動いていないサーバ**(6/18 と同型の再発)としてハードリロード/再起動を案内。
続報のスクリーンショット(サイドバーのカウント自体が各クラス2=データ構造に実在)でキャッシュ説を棄却し**実バグと確定、真因を特定して修正済み**:
**セッション開始ボタンのダブルクリック競合**(`startSession` が `/api/session` を await する間もセッション一覧が表示されたまま→2回目クリックで
二重セッション開始→初期予測の描画が2回走り1クラス2マスク)。Playwright のダブルクリック模擬で完全再現後、`app.js` に**再入ガード `_starting`・
一覧の await 前即時非表示・`loadCurrent` の世代ガード `_loadSeq`** の3点で修正し、ダブル/トリプルクリックでも 1クラス1マスク・通常フロー正常を機械検証
(フロントのみ=サーバ再起動不要・ハードリロードで反映。二重生成状態の既提出記録は練習/テスト分のみで本番3名のデータは未汚染)。
2026-09-15 に**約2か月ぶりに実験を再開**(相談のみ・コード変更なし): 被検者3名で施行する前提で**論文の筋書き・3名の妥当性・論文化リスク**を整理した。
筋書きは「モデルは何枚学習した時点からアノテータの労力を減らし始め、どこで頭打ちになるか」を問いとし、**主解析は log(学習枚数)に対する
用量反応トレンド(8条件総当たりにしない)・scratch は別対比・品質は非劣性マージン事前設定**、横軸は枚数に加え held-out Dice でも報告。
3名は「最低限成立」(画像反復 270+30 観測でトレンドは検出可、先行研究も2〜5名が主流)だが**アノテータは固定効果扱い・結論を3名に限定**して書く
(Latin 方格は cyclic で `ANNOTATOR_NAMES` 追加だけで最大9名へ拡張可)。論文化リスクは優先順に **①scratch がセッション0固定=習熟交絡(末尾に scratch
再掲を推奨) ②GT スタイル継承バイアス ③主要/副次の事前文書化 ④アノテータの倫理審査/同意 ⑤学習曲線が単一 run ⑥U-Net ablation は省略可
⑦疲労・分割実施**。次の一手として(1)事前解析計画書の作成、(2)末尾 scratch セッション追加の設計変更を提示=**ユーザー判断待ち**。
同日、課題が **Eyelid(ポリゴン)/Iris・Pupil(回転楕円)の3クラス**であることを再確認(`scripts/webapp/backend/config.py`)。
ポリゴン修正と楕円パラメータ修正は労力の質が異なるため、論文では**クラス別に効率曲線を提示**する方針
(瞳孔は Boundary-F1@2px が甘めに出るため HD95/ASSD の絶対 px 値を併記)。
さらに「クラス別の手間はログから計算可能か」を確認し、**既に `summary.csv` に per-class 列(`{k}_time_sec`/`{k}_clicks`/`{k}_vertices_edited`/`{k}_correction_dice`/`{k}_area_change` + 品質5指標)として保存済み・`events[]` から初動/アイドル/時系列も再構成可=追加実装不要**と結論。解釈上の注意は①時間帰属はサイドバー選択中クラス基準で、画像表示直後の既定 eyelid にクラス非依存時間が乗る(初動時間で補正可) ②楕円操作は頂点編集に乗らないため時間/クリック/修正量で比較 ③マウス距離はクラス別なし(必要なら小改修)。
同日、ユーザー依頼で**被験者の一人称でタスク全体(練習2+Scratch+Session1〜9=12セッション・106枚・2〜3時間)を追体験**し、実施前に潰すべき点5つを抽出: **①`annotator_guide.md` のアノテータ選択が「番号 1/2/3」のまま(実画面は実名 kubota/maeda/kaisho)** **②予測が悪いとき「修正か削除→描き直しか」の方針が未規定(労力計測の意味が変わる)** ③周辺視の楕円回転は練習で1枚しか経験できない ④目標精度(px)の伝え方 ⑤休憩・分割実施の目安が無い。①②の手順書修正を提案し、ユーザー承認を得て**同日中に `annotator_guide.md` へ反映済み**(①ログイン手順を実名選択+「動作テスト用」回避+選び間違い注意へ ②「予測の直し方は自由(頂点修正でも削除→描き直しでも可)」を明記)。②の帰結として HITL 条件の `shapes_deleted > 0` を「描き直し」として識別し**描き直し率 vs 学習枚数を副次指標**に追加する方針(描き直し画像の扱いは事前解析計画に明記)。③④⑤は未対応。`annotator_guide.md` は 7/12 分も含め未コミットのため実施前に webapp 一式とまとめてコミット推奨。
続けて**「最終セッションで scratch をもう一度やる案」を検討し推奨**(設計相談・未実装): 画像は3案(A=セッション0と同じ10枚を再描画 / B=新規10枚を3人共通 / C=HITL 既出画像)のうち
**A を推奨**(順序効果を画像で対応づけた前後差=30ペアで最も高感度に推定、B は順序効果と画像難易度が分離不能、C は直前修正の記憶で汚れる)。解析では習熟後の末尾 scratch を主解析の基準に使い(保守的)、
最初の scratch との差を順序効果として別報告。実装は `prepare_experiment.py` に「Scratch(2回目)」を Session 9 の後へ専用 RNG で追加(既存割当不変・audit 確認)、記録は `is_repeat=true`+`condition=scratch`、
ガイドは全13セッションへ更新、約1時間の見込み。ユーザーが**「Aで行きましょう」と決定 → 同日中に実装・検証まで完了**:
`scripts/prepare_experiment.py` に `SCRATCH_REPEAT_KEY/LABEL` を追加し、各アノテータの末尾(Session 9 の後・`session_index=10`)に
セッション0と同じ10枚を**専用 RNG(`SEED+2000+ai`)**で再シャッフルした「Scratch（2回目）」(`is_hitl=False`/`condition=scratch`/`is_repeat=True`)を生成、
audit に「最終セッション・非HITL・画像集合==セッション0・順序が異なる・index 連番」の assertion を追加して `experiment.json` を再生成(全 PASS)。
新旧 JSON の構造比較で `blocks`/`practice`/`latin_square`/`models` と各アノテータの `sessions[0..9]` が完全一致=**既存割付は不変**、末尾1セッションのみ追加。
backend/frontend はデータ駆動でコード変更なし。ローカル起動の実 API で `/api/run`(13セッション・盲検キー非露出)・`/api/session`(10枚=セッション0)・
`/api/predict`(空プレフィル)・`/api/submit`(`summary.csv` に `condition=scratch, is_repeat=True, session_index=10`)を確認し、検証記録削除・サーバ停止。
`annotator_guide.md` を**全13セッション**構成へ更新(1人 106→116枚)。**本番前に `run_server.bat` で再起動が必要**(experiment.json は起動時ロード)。
これで**実験設計は「練習2 + Scratch + 盲検 HITL 9(うち S9 再掲) + Scratch 2回目」の13セッションで確定**し、残るは未コミット分の一括コミット・
事前解析計画書・ガイド残り3点・倫理手続きの確認、そして実アノテーション施行・統計解析。

## マイルストーン
- [x] データ所在・手動アノテ範囲の確定（2026-06-14, 前リポジトリ調査）
- [x] HITL実験計画の確定（クラス/phase/計測項目/画像割当）(2026-06-15)
- [x] HITLアノーテーション webapp 実装・検証 (2026-06-15)
- [x] 症例安全な test 60枚割当生成（experiment.json）(2026-06-15)
- [x] 各 phase の視線方向構成を 正面7+周辺3・提示順ランダム化（虹彩偏心度で自動分類）(2026-06-16)
- [x] サブセット5モデルの学習パイプライン構築・患者リーク検証・本番学習を起動（SegFormer-B1: ~505/1020/1505/2007/2494枚, 症例リーク無し）(2026-06-16)
- [x] 小サブセット 100/200/300 を追加生成（リーク検証PASS・nested・既存不変）し大ジョブと並行学習を起動（計8モデル）(2026-06-16)
- [x] リーク無しの確定確認（真の held-out 患者120枚/29患者で再評価、正常な汎化ギャップ）・最終比較用の固定 held-out テストセット463枚を作成 (2026-06-16)
- [x] 8モデル(100〜2500)の学習完了・固定463枚テストで最終 Dice 一括算出・データ効率カーブ確定(2026-06-16)
- [x] `experiment.json`/`prepare_experiment.py` の `MODELS` を実 `seg{N}.pth` へ差し替え(placeholder解除・test_mean_dice付与)・CSV保存・webapp推論を system python(transformers 5.4)で実検証(2026-06-16)
- [x] 実験設計の盲検方式を確定(Q1): scratch 別建て基準・8 HITL モデル間は盲検ランダム混合・1セッション=10枚(正面7+周辺3)。Gemini(flash)が Claude と 5論点一致で相互検証 → ハイブリッド(混合モード)実装で確定(2026-06-16)
- [x] 実験設計 Q2 を確定(アノテータ3名・GT作成者除外・前向き化は軽量に事前固定・専用パイロット不要(内部パイロット化)・解析=画像をランダム効果に含む混合効果モデル)(2026-06-18)
- [x] seg100/200/300 を HITL 実験フェーズに追加する方針をユーザー承認(6→9フェーズ・全90枚で確定。フェーズ系は完全config駆動でUI自動反映を確認)(2026-06-16)
- [x] `prepare_experiment.py` を再実行し9セッション・90枚を再生成、webapp にブラインド混合モードを実装(3×9 Latin方格・scratchセッション0固定別建て・HITL8条件は盲検シャッフル混合・正解はサーバ側のみ・練習5枚は GT+Dice 表示で解析除外)。実サーバ + Playwright で盲検リークゼロを end-to-end 検証(2026-06-18)
- [x] アノテーション操作性の改修を完了・実機検証(Caruncle 廃止=Eyelid統合で3クラス化・eyelid prefill 16→38点・選択中クラス最前面化で重なり編集・クラス選択は右タブのみ。`config.py`/`geometry.py`/`tools.js`/`app.js`、Playwright で全4点確認)(2026-06-18)
- [x] GT表示の内部境界除去(練習GT eyelid を Eyelid∪Caruncle 統合外形に)・明るさ/コントラスト調整スライダー追加(Konva Brighten/Contrast、cache後適用・値保持)。Playwright で実機検証(2026-06-18)
- [x] 練習を2部構成(練習1 Scratch + 練習2 seg1000予測修正、各3枚・提出ごと GT 表示・解析除外)へ再設計し、「動作テスト用」擬似アノテータ(test=annotator1割当・記録は test_ フォルダへ分離)を追加(`prepare_experiment.py`/`main.py`/`app.js`・experiment.json 再生成)(2026-06-18)
- [x] 実アノテーション運用向けUI調整の実装・**実機検証**(既定の最大化+塗り無し・練習の再実行・赤い中断ボタン・中断=セッション完全リセット/`/api/abort`)。実サーバ + Playwright で全5点を機械確認 (2026-06-19)
- [x] 完了済セッションのやり直し(フォールバック)＋試行回数(attempt)の記録(中断とは別物=前記録を残し attempt 番号付与で新規記録・`session_id` に `a{attempt}`・UI に試行回数表示・`records.jsonl`/`summary.csv` の `attempt` 列に保存)。実 API で end-to-end 検証(`app.js`/`main.py`/`session.py`)(2026-06-19)
- [x] 完了済セッションの「やり直し」UI 表示を簡素化(「やり直し可」「[N回完了]」表示を撤去し「✓ ラベル (N枚)」のみに。やり直し機能本体・attempt 記録は温存、`app.js` フロント変更のみ)(2026-06-20)
- [x] 3名アノテータ配布のための WebApp 外部公開を実装・実機検証(Cloudflare quick tunnel + 共有PW HTTP Basic 認証=`HITL_AUTH_PASS` 環境変数ゲート/401・200 確認、`run_server.ps1` 一括起動・`README_deploy.md`/`annotator_guide.md` 配布資料。`scripts/webapp/backend/main.py` 編集)(2026-06-24)
- [x] プロジェクトを git 管理下に置き初回コミット(`.gitignore` で患者識別情報=患者ID付き `experiment.json`/`training_subsets/`/`results/`・大容量モデル `*.pth`(419MB)・`.venv`・ジャンクを除外、安全なログ/ノート/コード/`heldout_dice.csv` のみ保持。コミット前ステージ検証→`master` 4716de3・49ファイル)。GitHub push は空 private リポジトリ URL 提供待ち(2026-06-30)
- [x] GitHub へ push(private `ykitaguchi77/HITL_validation_test` へ `remote add`/`branch -M main`/`push -u`、GCM でブラウザ1回サインイン。push 後リモート機械検証=患者データ無し確認)(2026-06-30)
- [x] 既報レビュー(deep-research)完了=追加計測項目の欠落5系統を同定(主観負荷/境界距離/一致度/品質正規化労力/交絡対策)。ユーザーへ報告済み(2026-07-11)
- [x] 追加計測の実装方針をユーザーと確定(Paas単一項目を全画像/境界距離・眼瞼のみ/編集タイムスタンプ/オートメーションバイアスは後付け解析/同一条件5枚再掲)。実装見取り図4段を提示・**全方針にユーザー合意**。境界許容幅は最終的に **2px**(Boundary-F1@2px・HD95/ASSD 生距離併記)へ確定(2026-07-11)
- [x] 追加計測5項目の実装完了・end-to-end 検証(①タイムスタンプ `events[]`+初動/アイドル導出 ②眼瞼 HD95/ASSD/Boundary-F1@2px を cv2.distanceTransform で実装 ③Paas 9段階モーダル=回答時間を duration 非計上 ④summary.csv 7列追加+JSONL `events[]` ⑤盲検再掲「Session 9」5枚=専用RNGで既存割当不変・audit 全PASS。backend+実サーバ+Playwright+盲検リーク確認まで機械検証)(2026-07-11)
- [x] 境界指標を眼瞼のみ→全3クラス(eyelid/iris/pupil)へ拡張(オフライン計算でアノテーター負担ゼロのため。楕円もマスク境界のずれで測る=`cv2.ellipse`塗りつぶし方式)。`scoring.py` を全クラス算出へ・`session.py` を per-class 共通カラム `{k}_hd95`/`{k}_assd`/`{k}_boundary_f1` へリファクタし3クラス×3指標の列生成と GT 提出時 HD95=0/ASSD=0/F1=1.0 を検証(2026-07-11)
- [x] scratch 描画時の頂点カウント漏れバグを修正(`tools.js` の `_polyClick` が `vertexAdded()` 未呼び出しで scratch のみ `vertices_added=0`=scratch vs HITL 比較不能だった。初点・追加点の2箇所に計上追加、実サーバ+Playwright で 4点→`vertices_added=4` 確認)(2026-07-12)
- [x] Ctrl+ドラッグ marquee で複数頂点選択+まとめて移動を実装(スコープA=選択中1ポリゴンの頂点のみ・`canvas.js` PolygonShape に選択状態/移動メソッド・`tools.js` ToolController に marquee/グループドラッグ/矢印微調整/Esc/1ジェスチャ=1 undo)。実サーバ+Playwright で 2頂点だけ移動(`vertices_moved=2`)・Esc・undo 復元を機械確認(2026-07-12)
- [x] 計測タイミング衛生の強化: ①フォーカス喪失(タブ切替/最小化+他アプリ blur)で計測を一時停止=`duration_sec` 除外・`paused_time_sec` に計上・復帰時カーソル飛び非加算・モーダル中/保存中は誤停止せず・`#pause-overlay` 表示、②アクティブ中 15秒ごとの席外し監視 heartbeat=`heartbeats[]`(JSONL)。`metrics.js`/`app.js`/`index.html`/`style.css`/`session.py`。実サーバ+Playwright で 350ms停止→duration除外・`paused_time_sec` 記録・カーソル飛び非加算を機械確認、backend 再起動後の実API往復で記録到達を確認(2026-07-12)
- [x] 提出フローを「提出→確認画面(3択: 確認OK・次へ/修正/中断)→苦痛(Paas)の記録→保存」へ再構成(タイマーは提出押下で停止=確認・評価時間は duration 非計上、「修正」で編集へ戻ると計測再開。`index.html`/`style.css`/`app.js`、Playwright で全経路を機械確認)(2026-07-12)
- [x] 再掲 Session 9 を 5枚→10枚(正面7+周辺3)へ拡張(枚数の異質さによる盲検漏れを防止・他セッションと不可区別に。`prepare_experiment.py`+audit 更新・`experiment.json` 再生成 全assertion PASS・実 API で10枚確認。`annotator_guide.md` の「提出と中断」節も新フローへ更新)(2026-07-12)
- [x] 確認アクションを右上ボタンへ集約(中央3ボタン廃止・「提出」→「確認OK・次へ」ラベル化・確認中のみ「修正」表示・中断は既存流用)＋練習 GT マージを最初の確認画面へ前倒し統合(二度目のマージ確認を廃止・保存せず GT を返す `/api/practice_gt` を追加し本番画像には 403 で盲検維持)。`main.py`/`index.html`/`app.js`、実API+Playwright で本番=GTなし/練習=GT+Dice表示・本番403/練習200 を機械確認(2026-07-12)
- [x] 提出時に全ポリゴン/楕円の選択を解除(確認画面をクリーン外形で提示)＋3クラス未完成での提出ブロック(`_missingClasses()` で未入力クラスをアラート明示・早期return)を実装・実機検証。`app.js` フロントのみ変更(2026-07-12)
- [x] 「3クラス必須」ガードの安全性をデータセット全体で検査(実験96画像・候補プール463枚は瞳孔欠損ゼロ=安全、隠れ瞳孔症例8枚は ID範囲/患者分離/虹彩ありのプール絞り込みで自然排除と確認)(2026-07-12)
- [x] 「マスクが2つずつ生成される」バグの真因特定と修正(セッション開始ボタンのダブルクリック競合=await 中も一覧が押せて二重セッション開始→初期予測が二重描画。`app.js` に再入ガード・一覧即時非表示・ロード世代ガードの3点で修正、Playwright でダブル/トリプルクリック→1クラス1マスク・通常フロー正常を機械検証。**ユーザーがハードリロード後に実ブラウザで解消を確認=「直りました」でクローズ**)(2026-07-13)
- [x] 実験再開に向けた論文戦略の整理(筋書き=用量反応トレンド主解析・3名の妥当性=固定効果で限定・論文化リスク7点=scratch セッション0固定の習熟交絡が最優先)。ユーザーへ提示済み(2026-09-15)
- [ ] 事前解析計画書(主要/副次指標・モデル式・非劣性マージン)の作成 — ユーザー判断待ち
- [x] 末尾 scratch セッション「Scratch（2回目）」追加(習熟交絡の前後差推定・案A=セッション0と同じ10枚を専用RNGで再シャッフル・`is_repeat=True`+`condition=scratch`・`session_index=10`)。`prepare_experiment.py` 生成+audit 拡張・`experiment.json` 再生成(全PASS・新旧 diff で既存割付不変)・実 API で end-to-end 検証・`annotator_guide.md` 13セッション化。backend/frontend 変更なし(2026-09-15)
- [ ] 本番前に `run_server.bat` でサーバ再起動(再生成した `experiment.json` を反映)
- [x] `annotator_guide.md` の実施前修正(①アノテータ選択を実名表記へ ②修正/描き直し方針=自由 を明記)。`git diff --stat` +16/−6 で確認(2026-09-15)
- [ ] `annotator_guide.md` の残り3点(③楕円回転の練習案内 ④目標精度の伝え方 ⑤休憩・分割の目安) — ユーザー判断待ち
- [ ] webapp 一式 + `annotator_guide.md` の未コミット分を実施前にコミット
- [ ] （ablation）vanilla U-Net 版モデルの学習(スコープ次第で省略可)
- [ ] 実アノテーション施行・結果集計・統計解析（phase別効率の比較）
- [ ] 論文用 図表・本文化

## タイムライン
- 2026-06-15: HITLアノーテーションwebappを実装・検証、test 60枚割当を生成 -> [詳細](Experimental_record/20260615.md)
- 2026-06-15: webappのドラッグ/楕円編集を修正、Stop hookの文字化け（UTF-8 stdin）を修正 -> [詳細](Experimental_record/20260615.md)
- 2026-06-15: webappにポリゴン点追加(extend)モード・塗りつぶしON/OFFトグルを追加 -> [詳細](Experimental_record/20260615.md)
- 2026-06-16: webapp操作性追加(最近接エッジ挿入・クラス連動・スペース/矢印/フィット)、視線方向7+3割当を虹彩偏心度で実装 -> [詳細](Experimental_record/20260616.md)
- 2026-06-16: HITLサブセット5モデルの学習パイプラインを構築(患者リーク無しnestedサブセット生成・検証PASS、B1移植スクリプト、transformers 4.57.3 venv)し本番学習をバックグラウンド起動(seg500..2500, 数時間規模)。seg500 完了(best mean val Dice 0.971 @ ep144)、seg1000 学習中 -> [詳細](Experimental_record/20260616.md)
- 2026-06-16: 小サブセット 100/200/300 を追加(リーク検証PASS・nested・既存500〜2500不変)し大ジョブと並行学習を起動(OOM無し: 9.5GB/16GB)。計8モデル(100〜2500)が揃う予定 -> [詳細](Experimental_record/20260616.md)
- 2026-06-16: 並行学習が進行し seg100(0.922)・seg200(0.937) 完了、seg300 学習中。データ量↑で改善傾向を確認 -> [詳細](Experimental_record/20260616.md)
- 2026-06-16: 「結果が良すぎる」懸念に対しリーク検証(真の held-out 120枚/29患者で再評価、seg500: val0.971→test0.949 の正常な汎化ギャップ→リーク無し確定)、最終比較用の固定 held-out テストセット463枚(heldout_test.json)を作成 -> [詳細](Experimental_record/20260616.md)
- 2026-06-16: 並行学習がさらに進行し小ジョブ全完了(seg300=0.955)・seg1000 実質完了で **5/8モデル完了**(残り 1500/2000/2500、約8〜10h)。全完了後に固定463枚で最終Dice一括算出予定 -> [詳細](Experimental_record/20260616.md)
- 2026-06-16: seg1000 完了確定(best mean val Dice 0.964 @ep98)で **6/8モデル完了**、seg1500 学習中。残り 2000/2500 -> [詳細](Experimental_record/20260616.md)
- 2026-06-16: seg1500 完了(best mean val Dice 0.953 @ep84)、seg2000 学習中。残り最後の seg2500 -> [詳細](Experimental_record/20260616.md)
- 2026-06-16: seg2000 完了(best mean val Dice 0.962 @ep163)で **7/8モデル完了**(100〜2000)、残るは最後の seg2500 のみ。完了後に固定463枚で最終Dice一括算出予定 -> [詳細](Experimental_record/20260616.md)
- 2026-06-16: 最後の seg2500 完了(内部val 0.959 @ep58)で **全8モデル完成**。固定463枚 held-out で全モデル一括スコアリング → データ効率カーブ確定(共通テストで単調改善、mean 0.919→0.958、ピーク seg2000)。残タスクは experiment.json の MODELS 差し替えのみ -> [詳細](Experimental_record/20260616.md)
- 2026-06-16: MODELS を実 `seg{N}.pth` へ差し替え(placeholder解除・test_mean_dice付与)・CSV保存・webapp推論を system python(transformers 5.4)で seg500 実検証 → **HITLモデル学習フェーズ完了**(学習→配線→初期提示が一気通貫) -> [詳細](Experimental_record/20260616.md)
- 2026-06-16: 実験設計(ブラインド vs ノンブラインド提示)を相談開始。期待バイアス/画像難易度交絡/scratch盲検不可を整理し Claude推奨(HITLモデル間ブラインド混合・scratch別基準・混合モード追加のハイブリッド)を提示。Codex(401)/Gemini(応答待ち)未取得で盲検方式は次回確定 -> [詳細](Experimental_record/20260616.md)
- 2026-06-16: seg100/200/300 の実験フェーズ追加をユーザー承認(6→9フェーズ・全90枚)。Exploreサブエージェント調査で**フェーズ系は完全config駆動**(experiment.json追加でドロップダウン自動反映・prepare_experiment.pyは`len(PHASES)`で自動スケール)と確認 → 追加は生成スクリプト再実行のみ。盲検方式確定後に再生成予定 -> [詳細](Experimental_record/20260616.md)
- 2026-06-16: 盲検方式 Q1 を確定。Gemini(flash)のセカンドオピニオンが Claude と 5論点一致で相互検証 → ユーザー決定「scratch 別建て・8 HITL モデル間は盲検混合・1セッション10枚(正面7+周辺3)」。Q2(人数・前向き化・パイロット・解析法)は Codex 相談中(ChatGPTアカウントのモデル制約=gpt-5/gpt-5-codex 非対応・o4-mini 400 で未取得)で継続 -> [詳細](Experimental_record/20260616.md)
- 2026-06-16: Q2 を Codex に再依頼も全モデル非対応・Gemini クォータ枯渇で取得不可 → Claude の Q2 推奨のみ提示(前向き化=軽量に事前固定/アノテータ3〜5名/専用パイロット不要=内部パイロット化し本解析へ組入れ/画像をランダム効果に含む混合効果モデル)。確定用の2点提示でセッション終了=ユーザー回答待ち -> [詳細](Experimental_record/20260616.md)
- 2026-06-18: Q2 含む実験設計を確定(アノテータ3名・GT作成者除外・1セッション10枚=正面7+周辺3)し、webapp を盲検 Latin方格仕様へ再構築。`prepare_experiment.py` を9セッション×10枚・3×9 Latin方格・scratchセッション0固定別建て・HITL8条件は盲検シャッフル混合・練習5枚(3F+2P/seg1000, GT+Dice表示・解析除外)で再生成、backend(API でモデル名/条件/ブロック秘匿・正解はサーバ側のみ・キャッシュ4→9・解析カラム追加)とフロント(アノテータ選択・順序固定ピッカー・Dice抑制)を実装。実サーバ + Playwright で盲検リークゼロを end-to-end 検証 → 学習・設計・盲検UI 実装まで完了 -> [詳細](Experimental_record/20260618.md)
- 2026-06-18: 実運用に向けた操作性改修を**完了・実機検証**(Caruncle 廃止=Eyelid統合で3クラス化・eyelid prefill 16→38点(eps 0.004→0.0015)・選択中クラスを `moveToTop` で最前面化し重なり編集可・クラス選択は右タブのみ/canvasクリック無効)。`config.py`/`geometry.py`/`tools.js`/`app.js` を編集し実サーバ + Playwright で全4点を機械確認 -> [詳細](Experimental_record/20260618.md)
- 2026-06-18: プレフィル点を**等弧長リサンプリングで均等化**(eyelid 約58点・間隔ほぼ一定 std≈1.1px)。「選択中に別クラスが選択される」報告は**コードでは解消済み**で真因は**ブラウザ旧JSキャッシュ**と特定 → `main.py` に no-cache ヘッダ追加で解消(`geometry.py`/`main.py`、Playwright 実証) -> [詳細](Experimental_record/20260618.md)
- 2026-06-18: GT表示の Eyelid/Caruncle 内部境界を除去(練習GT eyelid を統合外形1本に)し、右サイドバーに**明るさ・コントラスト調整スライダー**を追加(Konva Brighten/Contrast を `imageNode.cache()` 後に適用・画像切替をまたいで値保持)。Playwright で両機能を実機検証 -> [詳細](Experimental_record/20260618.md)
- 2026-06-18: 練習1例目の**GT 遅延ポップインを解消**(初回推論のコールドロードで編集途中に GT が出る問題)。①画像+プレフィルが揃うまで入力ブロックする `#loading-overlay`(「推論中…」)、②起動時モデル事前ウォームアップ(`_warm_models()`、warm predict 0.07〜0.17秒)、③計測タイマーを準備完了後に開始(待ち時間を duration に非計上)を実装(`main.py`/`index.html`/`style.css`/`app.js`)。Playwright + curl で検証。セッション終了時点でサーバ `localhost:8000` 稼働中 -> [詳細](Experimental_record/20260618.md)
- 2026-06-18: **練習を2部構成へ再設計**(練習1「Scratch ゼロ描画」+ 練習2「seg1000 予測修正」、各 正面2+周辺1=3枚・提出ごと GT 点線表示・解析除外)し、scratch/HITL 両ワークフローを必ず事前体験させる。あわせて UI に**「動作テスト用」擬似アノテータ**(`test`=アノテータ1と同一割当、記録は `outputs/results/test_*/`(annotator="test")へ分離しリハーサルが本解析を汚さない)を追加。`prepare_experiment.py`(`PRACTICE_SPEC` 2セッション化・順序 assertion)・`main.py`(`RUN_ALIAS`/`UI_ANNOTATORS`)・`app.js` を編集し `experiment.json` 再生成。セッション終了時点でサーバ `localhost:8000` 稼働中(実アノテーション施行待ち) -> [詳細](Experimental_record/20260618.md)
- 2026-06-18: 練習を2部構成へ再設計(練習1 Scratch + 練習2 seg1000予測修正、各 正面2+周辺1=3枚・提出ごと GT 点線表示・解析除外)し両ワークフローを必ず練習させて習熟差交絡を低減。さらに「動作テスト用」擬似アノテータ(`test`=アノテータ1と同一割当・記録は `outputs/results/test_*/`(annotator="test")へ分離)を追加(`prepare_experiment.py` の `PRACTICE_SPEC`・`main.py` の `RUN_ALIAS`/`UI_ANNOTATORS`・`app.js`、experiment.json 再生成) -> [詳細](Experimental_record/20260618.md)
- 2026-06-19: 実アノテーション直前の運用UI調整を実装し**実機検証まで完了**(ウィンドウ最大化+塗り無しを既定化・練習モードの再実行を可能化・提出ボタン横に赤い中断ボタン・中断時はセッション完全リセットで中途計測の混入を防止=記録フォルダ削除+未完了へ戻す・パストラバーサルガード/backend に `/api/abort` 追加)。`canvas.js`/`index.html`/`style.css`/`app.js`/`main.py` を編集し実サーバ + Playwright で全5点を機械確認 -> [詳細](Experimental_record/20260619.md)
- 2026-06-19: 完了済セッションのやり直し(フォールバック)＋試行回数(attempt)の記録を実装・検証。完了済セッションもクリックでやり直し可(確認アラート)にし、中断(部分破棄)とは別物として前記録を残し attempt 番号(1,2,3…)付きで新規記録(`session_id` を `{annotator}_{key}_a{attempt}_{stamp}` 形式に・試行回数 localStorage 管理・UI に「(N回目)」「[N回完了・やり直し可]」表示)。attempt を `records.jsonl` と `summary.csv` の `attempt` 列両方に保存(`app.js`/`main.py` の `SubmitReq.attempt`/`session.py` の `_BASE_COLS`・`_flatten`)。サーバ再起動後に実 API で `attempt=3` が両ファイルへ到達することを end-to-end 確認 -> [詳細](Experimental_record/20260619.md)
- 2026-06-20: 完了済セッションの「やり直し」UI 表示を簡素化。ユーザー方針(やり直しは“どうしても必要な場合のみ”)を受け「やり直し可」→「[N回完了]」→表示撤去の2段階で削り、完了済は「✓ ラベル (N枚)」のみ表示に。クリック→確認アラート→やり直しの機能本体と attempt 記録(`records.jsonl`/`summary.csv`)はフォールバックとして温存(`app.js` のボタンラベルのみ変更・フロント変更でサーバ再起動不要) -> [詳細](Experimental_record/20260620.md)
- 2026-06-20: 実アノテーション開始前にモデル・データの収納レイアウトを棚卸し(調査のみ)。モデル `outputs/models/seg{100..2500}.pth`(8 ckpt)・入力画像は別プロジェクト参照(git管理外)・サブセット定義 `outputs/training_subsets/`・実験割付 `experiment.json`(SEED=42)・収集結果 `outputs/results/<session_id>/`(`records.jsonl`+`summary.csv`)を確認。`outputs/results/` の annotator「1」動作確認用4フォルダを本番前に削除するかはユーザー回答待ち -> [詳細](Experimental_record/20260620.md)
- 2026-06-20: 3名のアノテータへの配布方法を相談。GPU・モデル・医用画像を持つサーバは1台据え置き、**Cloudflare Tunnel で `localhost:8000`(FastAPI) を外部公開 + HTTP Basic 認証**で3名にブラウザ配信する方針を推奨(デスクトップ配布は非現実的で不採用方向)。quick tunnel のURLは再起動ごとに変わるため安定URLには named tunnel が必要。**推奨提示段階でセッション終了=実装(認証追加・トンネル起動・URL配布)は次セッション** -> [詳細](Experimental_record/20260620.md)
- 2026-06-24: 06-20 の配布方針を**実装・実機検証まで完了**。`main.py` に共有PW HTTP Basic 認証(`HITL_AUTH_PASS` 環境変数ゲート・API/静的両保護・未設定 localhost は認証なし＋警告・401時 `WWW-Authenticate` 返却)を追加し**認証なし→401/誤り→401/正→200** を確認。一括起動 `run_server.ps1`(uvicorn + `cloudflared tunnel --url http://localhost:8000`)、管理者手順 `README_deploy.md`、アノテータ配布資料 `annotator_guide.md` を作成。検証後ローカル開発挙動へ復帰。実アノテーション配布は即時開始可(固定URL要なら named tunnel、test 記録4フォルダ削除は保留)。さらに `$Pass` 変更箇所(run_server.ps1 19行目)を案内し、ダブルクリック起動用 `run_server.bat`(chcp 65001 + ExecutionPolicy Bypass + pause)を作成。その `.bat` が日本語コメントで文字化け＆ウィンドウ即閉じした件は、cmd.exe が cp932 でバッチを解釈しUTF-8日本語が誤実行される事が原因と特定し、`run_server.bat`/`run_server.ps1` を**純ASCII化**(PW `"hitl"` 保持・Pythonでバイト検証=127超ゼロ)して解消。最後に **バッチ起動を Cloudflare 公開URL経由まで end-to-end 検証**(公開URLで 認証なし401/`annotator:hitl`200/トップ200、起動ログの MISMATCH/cert.pem 警告は正常と説明)し、テスト用トンネル＋uvicorn を停止して終了 -> [詳細](Experimental_record/20260624.md)
- 2026-06-30: プロジェクトを git 管理下に置き初回コミット。「画像を外す」だけでなく患者IDがファイル名に埋め込まれた識別情報(`experiment.json`/`training_subsets/`/`results/`)・患者由来の大容量モデル `*.pth`(419MB)・`.venv`・ジャンクを `.gitignore` で除外し、安全なログ/研究ノート/コード/`heldout_dice.csv` のみ保持。コミット前にステージ内容を機械検証(ジャンクのパターン不一致混入を修正)し `master` に初回コミット(4716de3・49ファイル)。続けてユーザー提供の空 private リポジトリ `ykitaguchi77/HITL_validation_test` へ `remote add`/`branch -M main`/`push -u` を **GCM のブラウザ1回サインインで push 成功**(`gh` CLI 自動インストールは UAC 中断で失敗したが不要)。push 後リモートを機械検証(HEAD `4716de3` 一致・49ファイル・機微ヒットは `make_training_subsets.py`=コード本体のみで患者データ無し)し、患者由来でない成果物のみを Private にバックアップ完了 -> [詳細](Experimental_record/20260630.md)
- 2026-07-11: 実アノテーション前の確認としてタスク中の記録項目を棚卸し(調査のみ)。records.jsonl+summary.csv の4群(識別・実験条件=盲検隠し正解/操作計測/精度スコア/JSONL限定の再解析用項目)を整理し、研究概要の比較指標を全カバーと確認。metrics.js:8 に廃止済み caruncle キーの残存を発見(実害なし) -> [詳細](Experimental_record/20260711.md)
- 2026-07-11: 既報(interactive segmentation / AI-assisted annotation の効率評価、医学系+HCI系)における追加計測項目の文献調査を deep-research ワークフローで**完了**(25主張を3-0検証・一次情報源19件)。欠落5系統を同定=①NASA-TLX/SUS 等の主観負荷(最優先)②HD95/ASSD/Surface-Dice 境界距離(保存済ポリゴンからオフライン計算可)③アノテータ間/内一致度(反復設計)④NoC@IoU 等の品質正規化労力⑤ウォッシュアウト/オートメーションバイアス等の交絡対策。上位推奨は NASA-TLX と境界距離。ユーザーへ報告済み・実装要否は判断待ち -> [詳細](Experimental_record/20260711.md)
- 2026-07-11: 上記5系統の実装方針をユーザーと確定(調査・設計のみ)。8 HITL セッションが condition-mixed(`prepare_experiment.py`)のため主観負荷は画像ごとに取るしかなく、フル NASA-TLX は重すぎるため **Paas 9段階単一項目を全画像・submit後に分離**。境界距離は **許容幅3px固定・眼瞼のみ**(瞳孔/虹彩は負荷考慮で対象外)を保存済ポリゴンからオフライン計算。NoC は編集タイムスタンプで修正労力vs品質曲線に翻訳。オートメーションバイアスは scratch 基準比較+初期予測品質との相関で後付け解析。再現性は後半に同一条件5枚再掲で個人内 test-retest。実装見取り図[タイムスタンプ→Paas→境界指標→再掲5枚]を提示し、主観負荷=単一項目でよいかの合意1点を確認提示=回答待ち -> [詳細](Experimental_record/20260711.md)
- 2026-07-11: 上記方針に**全面合意**(「はい、それでいきましょう」)。**境界許容幅を 3px→2px に変更**(3px 以上は意味ある実誤差・2px 以内を一致)し境界指標を **眼瞼のみ・Boundary-F1(Surface Dice)@2px・HD95/ASSD 生距離併記**で確定。実装フェーズに入り `scoring.py`/`geometry.py`/`app.js`/`index.html` を読み込んで構造把握したが**ファイル編集は未実施のままセッション終了**(4段の実装は次セッション) -> [詳細](Experimental_record/20260711.md)
- 2026-07-11: 追加計測5項目を**実装完了・end-to-end 検証**。①編集タイムスタンプ `events[]`+初動/アイドル導出(`metrics.js`)②眼瞼 HD95/ASSD/Boundary-F1@2px(cv2.distanceTransform・新規依存なし)(`scoring.py`)③Paas 9段階モーダル(duration 確定後に表示=回答時間非計上)(`index.html`/`app.js`/`style.css`)④summary.csv に is_repeat/初動/アイドル/effort/境界3指標の7列追加(`session.py`/`main.py`)⑤盲検再掲「Session 9」5枚(専用RNGで既存90枚割当不変・audit 全PASS)(`prepare_experiment.py`)。backend パイプライン+実サーバ+Playwright(提出→モーダル→effort=7 記録→前進)+盲検リークゼロ確認、検証用 test 記録削除・サーバ停止まで完了 -> [詳細](Experimental_record/20260711.md)
- 2026-07-11: ユーザー再確認を受け**境界指標を眼瞼のみ→全3クラス(eyelid/iris/pupil)へ拡張**。オフライン計算でアノテーター負担ゼロのため絞る理由が無いと整理し、楕円(虹彩/瞳孔)も `cv2.ellipse` 塗りつぶし→マスク境界のずれで測る(眼瞼と同じ土俵)。`scoring.py` を全クラス算出へ、`session.py` を眼瞼ハードコード→**per-class 共通カラム** `{k}_hd95`/`{k}_assd`/`{k}_boundary_f1` へリファクタ。3クラス×3指標の列生成と GT 提出時 HD95=0/ASSD=0/F1=1.0 を検証(瞳孔は Boundary-F1@2px が甘めに出る点は認識・HD95/ASSD が有用)-> [詳細](Experimental_record/20260711.md)
- 2026-07-11: アノテーション後の主観負荷(ストレス)指標の状態を確認応答(確認のみ・コード変更なし)。現状は **画像ごとの Paas 9段階単一項目=submit 後にモーダル表示・回答時間は duration 非計上・`effort` 列(1〜9)に保存**として実装/検証済みであることを整理して回答。残判断として **単一項目で確定か、scratch セッション末にフル非加重 NASA-TLX を補助追加するか**をユーザーへ確認提示=回答待ち -> [詳細](Experimental_record/20260711.md)
- 2026-07-11: 努力尺度の目盛りを **1–9(Paas 1992 そのまま)で確定**(意思決定のみ・コード変更なし)。ユーザーの「1–9 の9択でよいか? 医学の問診表は 0–10 の numerical scale が多い」に対し目盛り数のトレードオフ(0–10 臨床NRS / 1–9 Paas / 1–10)を提示。論文で「single-item cognitive load scale (Paas, 1992)」として妥当性を引用できる利点を優先し 1–9 を採用。**現行実装が既に 1–9 のため変更不要**、運用時に「1=非常に少ない〜9=非常に大きい」のアンカー説明を一言添えるのみ。これで追加計測5項目+主観負荷尺度がすべて確定・実装・検証済み -> [詳細](Experimental_record/20260711.md)
- 2026-07-11: 追加計測の実装後、ユーザー依頼でローカル開発モードの webapp を起動し動作確認(手動スモークテスト・コード変更なし)。`python -m uvicorn main:app --port 8000` で正常起動・`/api/config` 200・3クラス/アノテータ1/2/3+動作テスト用を確認。`HITL_AUTH_PASS` 未設定でアクセス制御は無効(ローカル開発なので想定どおり・外部公開時のみ設定)。提出後の Paas 1–9 モーダル・test_ 記録分離・末尾「Session 9」再掲の確認ポイントを案内。**サーバは `localhost:8000` 稼働中(ユーザー確認中)** -> [詳細](Experimental_record/20260711.md)
- 2026-07-12: ローカル起動での動作確認中に発覚した**計測バグを修正**。**scratch 描画(`tools.js` の `_polyClick`)が頂点追加を計上せず**(既存点追加 `_extendClick` のみ `vertexAdded()` を呼んでいた)、**scratch では `vertices_added=0`=scratch vs HITL の労力比較不能**だった非対称を、初点・追加点の2箇所に計上を追加して解消。実サーバ+Playwright で**ゼロから4点→`vertices_added=4`・`eyelid.vertices_edited=4`・`events[]` に `v+`4件**を確認(フロントのみ・no-cache で即反映)。あわせて**Ctrl+ドラッグの複数頂点選択+まとめて移動は未実装**と切り分け、想定仕様(選択中1ポリゴンの矩形内頂点を複数選択→まとめて移動・`vertices_moved` 計上・1ジェスチャ1 undo・Esc 解除)と確認2点(対象は1ポリゴンのみか/トリガは Ctrl+ドラッグか)を提示 -> [詳細](Experimental_record/20260712.md)
- 2026-07-12: 上記②の確認2点にユーザー回答を得て**Ctrl+ドラッグ marquee による複数頂点選択+まとめて移動を実装・実機検証**。スコープ **A(選択中1ポリゴンの頂点のみ・隣クラスの点は矩形内でも無視)**で、`canvas.js` の `PolygonShape` に複数選択状態+移動メソッド、`tools.js` の `ToolController` に marquee 選択・グループドラッグ・矢印微調整・Esc 解除・1ジェスチャ=1 undo・ツール切替時の marquee 掃除を配線。実サーバ+Playwright で**上辺2頂点だけ選択→まとめて移動(`vertices_moved=2`・下2頂点不動)・Esc 解除・undo 復元**を機械確認(undo は `restore()` で図形再構築のため検証は undo 後に読み直して再選択)-> [詳細](Experimental_record/20260712.md)
- 2026-07-12: ユーザー要望で**計測タイミング衛生を2機能で強化・実機検証**。①**フォーカス喪失で計測を一時停止**(タブ切替/最小化=`visibilitychange`+他アプリ `blur`/`focus`、タイマー・全カウント・マウス移動距離の加算を停止し戻ると自動再開、非アクティブ経過は `duration_sec` から除外し `paused_time_sec` に計上、復帰直後のカーソル飛びは非加算、努力モーダル中/保存中=`timing=false` は誤停止せず、`#pause-overlay` で canvas をブロック)、②**席外し監視 heartbeat**(アクティブ中 15秒ごとに `{t,wall}` を JSONL `heartbeats[]` へ=タブを開いたまま離席すると一時停止せず heartbeat 継続・操作イベント途切れ→`idle_time_sec` と併用で「PC前で無操作」と「離席」を区別)。`metrics.js`/`app.js`/`index.html`/`style.css`/`session.py`(`paused_time_sec` 列)を編集。実サーバ+Playwright で 350ms停止→duration除外(0.29s)・`paused_time_sec=0.35`・700pxカーソル飛び非加算(5pxのみ)、backend 再起動後の実API往復で `paused_time_sec=0.124`/heartbeat/events 到達を機械確認。サーバは `localhost:8000` 稼働中 -> [詳細](Experimental_record/20260712.md)
- 2026-07-12: **Cloudflare 遠隔アノテーション配信の現状を確認応答**(確認のみ・コード変更なし)。6/24 実装済みの構成(**Cloudflare quick tunnel + 共有PW HTTP Basic 認証**・`run_server.bat`→`run_server.ps1` で `HITL_AUTH_PASS` 付き uvicorn + `cloudflared tunnel`)が揃っており、今セッション追加分(努力尺度/境界指標/タイムスタンプ/再掲Session/一時停止/heartbeat/複数頂点選択/頂点カウント修正)も同一コードベースでトンネル起動すればそのまま遠隔反映=別途デプロイ不要、と回答。**今 `localhost:8000` で稼働中なのは開発モード(認証なし・ローカルのみ)で外部公開時は `run_server.bat` から起動する**点、quick tunnel の URL は起動ごと変動する点を注意喚起。**未対応の指摘=`annotator_guide.md` のセッション数が古い(Session 1〜8 → 今回の再掲追加で実際は 1〜9)+新操作(Ctrl+ドラッグ複数頂点移動・別ウィンドウで自動一時停止)の追記が望ましい**をユーザーへ提示=資料更新の要否は回答待ち -> [詳細](Experimental_record/20260712.md)
- 2026-07-12: 配布用の**認証情報(ID/パスワード)の在り処を確認応答**(確認のみ・コード変更なし)。実体は `scripts/webapp/run_server.ps1` の16〜18行目のみ(ID=`annotator`・PW=`hitl`)で、`main.py:78-79,94-95` の Basic 認証がユーザー名+パスワード両方を照合すると回答。注意喚起2点=①**現PWは `hitl` のままで本番用に未変更**(`CHANGE_ME_BEFORE_SHARING` ガードはあるが `hitl` はすり抜けるため警告が出ない)、②`run_server.ps1` は git(private リポジトリ)にコミット済みのため本番PWを書くとリポジトリにも入る(手元のみ書き換え運用が安全)。本番PW変更・コミット可否はユーザー回答待ち -> [詳細](Experimental_record/20260712.md)
- 2026-07-12: ユーザー依頼で**アノテータ配布資料 `annotator_guide.md` をセッション1〜9構成へ更新**(ドキュメントのみ・コード/割付への影響なし)。再掲 Session 9 追加で本番が Scratch + Session 1〜9 になったのに合わせ、冒頭のセッション総数を「全10」→「練習2 + 本番(Scratch + Session 1〜9)=**全12セッション**」、作業の流れの表を「4〜11｜Session 1〜8」→「**4〜12｜Session 1〜9**」に修正。あわせて今セッションの新操作(**Ctrl+ドラッグで複数頂点をまとめて移動**・**別ウィンドウ切替で自動一時停止=時間非計上**)を操作表と提出注記へ追記。盲検上 Session 9 が再掲(test-retest)である旨はアノテータに伝えない設計のため資料でも普通の本番セッションとして記載。これで URL+共有PW+本資料をセットで3名へ即配布可能 -> [詳細](Experimental_record/20260712.md)
- 2026-07-12: ユーザー指摘を受け**提出フローを「提出(=タイマー停止)→確認画面(3択: 確認OK・次へ/修正する/中断)→苦痛(Paas 1–9)の記録→保存」へ再構成**(`index.html`/`style.css`/`app.js` の `submit()` 再構成+`_confirming` フラグ。確認・負担度回答・修正時レビュー時間は `duration_sec` 非計上、「修正」で編集へ戻ると計測再開。Playwright で全経路=提出→確認→修正→再提出→確認OK→負担度→保存 を機械確認)。あわせて**再掲 Session 9 を 5枚→10枚(正面7+周辺3)へ拡張**(5枚だけ異質で盲検上目立つため他セッションと不可区別に。`prepare_experiment.py`+audit assertion 更新・`experiment.json` 再生成 全PASS・サーバ再起動→実 API で Session 9=10枚確認)し、`annotator_guide.md` の「提出と中断」節を新フローへ更新。サーバは `localhost:8000` 稼働中 -> [詳細](Experimental_record/20260712.md)
- 2026-07-12: ユーザー指摘でさらに2点を改善・実機検証。**①確認アクションを右上ボタンへ集約**(中央3ボタンダイアログを廃止し「提出」ボタンを確認中は「確認OK・次へ →」ラベルに変化・確認中のみ「修正」ボタンを表示・中断は既存ボタン流用。確認中は半透明オーバーレイで canvas を保護しつつアノテーションは可視)、**②練習の GT マージを最初の確認画面へ前倒し統合**(提出直後の確認画面で GT+per-class Dice を表示し**二度目のマージ確認を廃止**。保存せず GT だけ返す軽量エンドポイント `/api/practice_gt` を追加し、**本番セッション画像には 403** で GT を出さず盲検を維持)。`main.py`(エンドポイント+403ガード)/`index.html`/`app.js` を編集。backend 再起動後、実 API(本番403/練習200)+ Playwright(本番=確認にGTなし・右上ボタン・「修正」で編集復帰、練習=確認画面に GT+Dice「mean 0.226 [eyelid 0.679 …]」表示・確認OKで負担度・二度目確認なしで前進)で機械確認。当日 test 記録は削除(手動テスト分は温存)。サーバは `localhost:8000` 稼働中・実アノテーション配布可能 -> [詳細](Experimental_record/20260712.md)
- 2026-07-12: 最終仕上げとしてユーザー指摘の2点を実装。**①提出時に全ポリゴン/楕円の選択を解除**(`submit()` で確認オーバーレイ表示前に `tools.deselect()`=確認画面をアンカー/ハイライト無しのクリーンな外形で提示)、**②3クラス(まぶた・虹彩・瞳孔)が揃わない状態での提出をブロック**(`_missingClasses()` で現存 shape の classKey 集合と config.classes を突き合わせ、未入力があればアラートで明示し `submit()` を早期 return=確認フローに入らない)。`scripts/webapp/static/js/app.js` のフロントのみ変更。実サーバ+Playwright で まぶただけ→アラートで確認画面が開かず / 3クラス揃い→確認画面へ・全選択解除(selected/vsel/vselMulti=null)を機械確認 -> [詳細](Experimental_record/20260712.md)
- 2026-07-12: ユーザー懸念(眼瞼下垂で瞳孔が完全に隠れた症例)を受け、追加した**「3クラス必須」ガードがデータセット全体で成立するかを GT で機械検査**(調査のみ)。**実験で使う96画像(本番90+練習6)・候補プール463枚はいずれも瞳孔欠損ゼロ=ガードは安全**。一方データセット全体では iris 注釈4467枚中1504枚(約34%)が瞳孔なし・うち「虹彩は見えるが瞳孔は隠れた」部分隠蔽が8枚(患者161/162/166/198/223)実在するが、これらは **画像ID範囲2500–2999・患者分離・虹彩あり** というプールの絞り込みで自然排除されている(別シード再生成でも混入しない)。将来のデータ/ID範囲変更への保険としてプール構築に「pupil も必須」を明示する1行は任意(未実装・現状90枚は不変)-> [詳細](Experimental_record/20260712.md)
- 2026-07-13: 手元での webapp 起動が**ポート8000の bind エラー(WinError 10048=使用中)**で落ちる件を解消(運用対応・コード変更なし)。原因は**前セッションで検証用に立てたままのバックグラウンド uvicorn(:8000)がポートを掴んでいた**こと。残存プロセスを `Stop-Process` で停止しポート開放を確認、ユーザーへ再起動手順と 10048 時の PID 特定・停止方法(`Get-NetTCPConnection -LocalPort 8000`)を案内。再発防止として**検証用バックグラウンドサーバーは検証完了後に必ず停止**する運用を徹底(医用画像サーバーで放置は公開リスクも)-> [詳細](Experimental_record/20260713.md)
- 2026-07-13: ポート解放後にユーザーが再起動し、**`Uvicorn running on http://127.0.0.1:8000` まで正常起動を確認**(bind エラー再発なし)。起動ログの警告2件(`num_labels=3` 非互換=3クラス用の分類ヘッド再初期化・重みで上書きされ実害なし / HF_TOKEN 未認証=ローカル checkpoint 読み込みのため無害)はいずれも**正常・想定どおり**と切り分け。webapp は `localhost:8000` 稼働・実アノテーション施行可能な状態 -> [詳細](Experimental_record/20260713.md)
- 2026-07-13: 上記の続きで、ユーザーがログ末尾の `Shutting down`/`Application shutdown complete` を異常と受け取った件を切り分け応答(確認のみ・コード変更なし)。これは **Ctrl+C 等によるグレースフルな正常停止でクラッシュではない**こと、起動時の8回の「Loading weights…」は **seg100〜2500 の8モデル事前ウォームアップ**で想定どおりであることを説明し、**止めず放置すれば使える**旨を案内。停止が自分の操作か放置での自然終了かを確認依頼(後者なら別原因調査が必要)-> [詳細](Experimental_record/20260713.md)
- 2026-07-13: webapp 起動成功後、配布用の**認証情報(ID/パスワード)の在り処を再確認応答**(確認のみ・コード変更なし)。実体は `scripts/webapp/run_server.ps1` の 17〜18 行目のみ(ID=`annotator`・PW=`hitl`(仮))で、`run_server.ps1`/`run_server.bat` 起動時に環境変数 `HITL_AUTH_USER`/`HITL_AUTH_PASS` へ渡り `main.py` の Basic 認証(ID+PW 両照合)が有効化されると回答。注意喚起=現在起動中の素の `uvicorn` は `HITL_AUTH_PASS` 未設定で**認証無効(ローカル開発なので想定どおり)**、外部公開時は必ず `run_server.bat`/`.ps1` から起動し18行目の仮PW `hitl` を本番値へ変更すること(仮値はガードをすり抜け警告が出ない)-> [詳細](Experimental_record/20260713.md)
- 2026-07-13: ユーザー依頼で**アノテータを実名3名(kubota/maeda/kaisho)へ変更し練習用(test)を先頭に配置**(実装・検証済み)。`prepare_experiment.py` の `ANNOTATOR_NAMES` を実名へ(experiment.json 再生成・audit 全 assertion PASS、割付構造は不変)、`main.py` の `UI_ANNOTATORS = ["test"] + ...` で練習用を先頭に、`app.js` で先頭ラベルを「練習用(本番に含めない)」・本番3名は実名表示に変更。検証用の一時サーバ(port 8011)でバックエンドが `['test','kubota','maeda','kaisho']` 順を返し全員 run 解決できることを確認(練習用の記録は `outputs/results/test_*/` へ分離し本解析を汚さない)。**稼働中の 8000 番サーバは旧設定を起動時ロード済みのため、再起動でドロップダウンへ反映される**旨をユーザーへ申し送り -> [詳細](Experimental_record/20260713.md)
- 2026-07-13: ユーザー報告「校正(HITL)モードでマスクが2つずつ生成される」(重大)を徹底調査 → **現行コードでは再現せず**(調査・コード変更なし)。バックエンド `/api/predict` は1クラス1形状のみ返し、Konva シーングラフ実ノード・サイドバーカウントとも常に **1/1/1**、画像送り・提出フル操作(提出→確認OK→負担度→次へ)を繰り返しても重複せず、練習校正(p_hitl)確認画面の実線+GT点線の重なりは仕様どおりで修正・再提出・次画像で GT は毎回消える。最有力原因は**ユーザー環境の旧JSキャッシュ or 更新後コードで動いていないサーバ**(この時ユーザーの 8000 番は停止していた=6/18 と同型の再発)。対処=サーバ再起動+ハードリロード/シークレットを案内し、再現時の切り分け項目(カウントが2か・実線/点線・練習/本番・出るタイミング)を提示。検証記録(kubota 分含む)は削除・一時サーバ停止 -> [詳細](Experimental_record/20260713.md)
- 2026-07-13: 上記「再現せず」の続報。ユーザーのスクリーンショットで**サイドバーのカウント自体が各クラス2**(=shapes 配列に実在)と判明しキャッシュ説を棄却、**真因=セッション開始ボタンのダブルクリック競合**を特定・修正。`startSession` が `/api/session` を await する間もセッション一覧が押せるため、素早い2回目のクリックで二重セッション開始→`loadCurrent`→predict→初期描画が2回走り1クラス2マスクになっていた(Playwright のダブルクリック模擬で eyelid:2/iris:2/pupil:2 を完全再現)。`app.js` に**①再入ガード `_starting` ②一覧の await 前即時非表示 ③`loadCurrent` の世代ガード `_loadSeq`** の3点で修正し、ダブル/トリプルクリック→1クラス1マスク・通常フロー(提出→確認→負担度→次へ)正常を機械検証。フロントのみ=サーバ再起動不要・ハードリロードで反映、本番3名のデータは未汚染。検証記録・スクリーンショット等の一時ファイルは削除し検証サーバ(8011)停止。**ユーザーがハードリロード後に実ブラウザで確認=「直りました」でバグクローズ**(ダブルクリック連打でも安全なため本番アノテーション/配布に進める状態) -> [詳細](Experimental_record/20260713.md)
- 2026-07-13: **Cloudflare Tunnel の固定URL化について確認応答**(確認のみ・コード変更なし)。「課金すれば固定URLにできるか?」に対し、**Cloudflare への課金は基本不要・条件は自分のドメインを持つことのみ**と回答。現行の quick tunnel(`*.trycloudflare.com`・再起動ごと変動)に対し、固定URLは **named tunnel(Cloudflare 無料プランで利用可)** で実現でき、課金が要るのは**ドメイン取得料(年 ~1,000〜1,500円)のみ**。医用データ配布では **named tunnel + Cloudflare Access(無料枠50ユーザー・メールワンタイムコード)** を推奨(共有PWより堅牢)、ドメイン不要な代替に Tailscale Funnel も提示。ドメイン確定後に `run_server.ps1` へ組み込む形で用意可能(未実装・ユーザー判断待ち)-> [詳細](Experimental_record/20260713.md)
- 2026-09-15: **実験再開に向けた論文戦略の相談**(相談のみ・コード変更なし)。被検者3名前提で①筋書き(問い=「何枚学習でモデルが労力を減らし始め、どこで頭打ちか」、主解析=log(学習枚数)の用量反応トレンド・scratch 別対比・非劣性マージン事前設定、図表6点、横軸に held-out Dice も併記)②3名の妥当性(最低限成立=画像反復270+30観測でトレンド検出可、ただしアノテータは固定効果で結論を3名に限定。Latin 方格は cyclic で最大9名へ拡張可)③論文化リスク7点(scratch セッション0固定の習熟交絡→末尾 scratch 再掲を推奨/GT スタイル継承/主要・副次の事前文書化/倫理審査/学習曲線 単一 run/U-Net ablation 省略可/疲労)を提示。次の一手=事前解析計画書 or 末尾 scratch 追加の設計変更でユーザー判断待ち。追記: 課題は Eyelid(ポリゴン)/Iris・Pupil(回転楕円)の3クラスであることを再確認し、論文はクラス別効率曲線を提示する方針 -> [詳細](Experimental_record/20260915.md)
- 2026-09-15: **クラス別の手間(労力)をログから計算できるかを確認応答**(確認のみ・コード変更なし)。`session.py` の `_per_class_cols()` で eyelid/iris/pupil ごとの `time_sec`/`clicks`/`vertices_edited`/`correction_dice`/`area_change`と品質5指標が `summary.csv` に保存済み、JSONL `events[]`(`{t,type,cls}`)からクラス別の初動/アイドル/編集時系列も再構成可=**現行ログで材料は揃っている**と結論。注意点として時間帰属が「サイドバー選択中クラス」基準で**既定 eyelid にクラス非依存時間が混入**(events の初動時間で補正)、楕円(iris/pupil)の移動/回転は `vertices_edited` に乗らない、`mouse_distance_px` はクラス別なし、を提示。 -> [記録](Experimental_record/20260915.md)
- 2026-09-15: **被験者の一人称でタスク実施の実際をウォークスルー**(相談のみ・コード変更なし)。配布資料 `annotator_guide.md` を基に練習1/2→Scratch→Session1〜9(S9 は再掲・不可区別)を追体験し、総負担 106枚・2〜3時間、Scratch+2セッション/日 → 残りを2〜3日で分割する運用が現実的と評価。実施前に潰すべき5点(①ガイドの「アノテータ番号 1/2/3」が実名化に未追随 ②修正 vs 削除→描き直しの方針未規定 ③楕円回転の練習不足 ④目標精度の伝え方 ⑤休憩・分割の目安)を抽出し、①②の修正を提案 → ユーザー判断待ち。 -> [記録](Experimental_record/20260915.md)
- 2026-09-15: **`annotator_guide.md` の実施前修正を実施**(手順書のみ・コード不変)。ユーザー承認を受け ①ログイン手順を「番号 1/2/3」→実名(kubota/maeda/kaisho)選択+「動作テスト用」回避+選び間違い注意へ ②「予測の直し方は自由(頂点修正でも削除→描き直しでも可、最も早く正確な方法を選ぶ)」を明記。`main.py` の `UI_ANNOTATORS` で UI 表示順を裏取り。②により `shapes_deleted > 0` を描き直しとして識別し**描き直し率 vs 学習枚数を副次指標化**する方針。残り③④⑤は未対応、未コミット分の一括コミットを推奨。 -> [記録](Experimental_record/20260915.md)
- 2026-09-15: **最終セッションに scratch を再掲する案を検討・推奨**(設計相談・未実装)。画像選択3案(A=同一10枚再描画/B=新規共通10枚/C=HITL既出画像)を比較し**案A を推奨**(順序効果を画像対応づけの前後差で最も高感度に推定、B は順序効果と画像難易度が分離不能、C は記憶で汚れる)。解析は習熟後 scratch を主基準(保守的)・前後差を順序効果として別報告。実装は Session 9 の後に専用RNGで追加・`is_repeat=true`+`condition=scratch`・ガイド13セッション化(約1h)。**案A で着手可否のユーザー判断待ち** -> [詳細](Experimental_record/20260915.md)
- 2026-09-15: ユーザー決定「Aで行きましょう」を受け**最終セッション「Scratch（2回目）」を実装・検証完了**(設計変更)。`scripts/prepare_experiment.py` に `SCRATCH_REPEAT_KEY/LABEL` を追加し、各アノテータの Session 9 の後にセッション0と同じ10枚を専用RNG(`SEED+2000+ai`)で再シャッフルした非HITL セッション(`condition=scratch`/`is_repeat=True`/`session_index=10`)を生成、audit に最終位置・非HITL・画像集合==セッション0・順序差・index 連番の assertion を追加。`experiment.json` 再生成(全 PASS)、新旧 JSON 比較で `blocks`/`practice`/`latin_square`/`models`・各 `sessions[0..9]` 完全一致=既存割付不変。backend/frontend はデータ駆動で無変更。ローカル実 API で `/api/run`(13セッション・盲検キー非露出)/`/api/session`(10枚=セッション0)/`/api/predict`(空)/`/api/submit`(CSV に scratch/is_repeat/index=10)を確認し検証記録削除・サーバ停止。`annotator_guide.md` を全13セッションへ更新(1人 116枚)。**本番前に `run_server.bat` で再起動要**・未コミット分の一括コミット推奨 -> [詳細](Experimental_record/20260915.md)

## 関連 Knowledge
- [CVAT風HITLアノーテーションwebappの実装知見](Knowledge/hitl-annotation-webapp-konva.md)
- [Windowsフックで stdin JSON を UTF-8 として読む](Knowledge/windows-powershell-hook-stdin-utf8.md)
- [既存アノテーションから視線方向(正面/周辺)を虹彩偏心度で自動分類](Knowledge/gaze-direction-from-iris-eccentricity.md)
- [SegFormer学習パイプラインを患者リーク無しサブセットへ移植する](Knowledge/segformer-patient-safe-subset-training.md)
- [HITLアノテーション効率研究の盲検化と交絡設計](Knowledge/hitl-blinding-and-confound-design.md)
- [GPU推論WebAppを複数リモート作業者へ配布する(Cloudflare Tunnel + Basic認証)](Knowledge/single-server-webapp-cloudflare-tunnel-distribution.md)
- [Windowsバッチ(.bat)は純ASCIIで書く(日本語コメントは文字化け＆誤実行の原因)](Knowledge/windows-batch-file-ascii-only.md)
- [クラス別の労力計測は「選択中クラス」で帰属させ、既定クラスへの初期時間の混入を解析で補正する](Knowledge/per-class-effort-attribution-by-active-class.md)
- [医用研究リポジトリを公開する前のデータ衛生(.gitignore 設計とコミット前検証)](Knowledge/medical-repo-pre-push-data-hygiene.md)
- [HITL/インタラクティブセグメンテーションの効率評価で使われる計測項目(既報サーベイ)](Knowledge/hitl-annotation-efficiency-metrics-from-literature.md)
- [2Dマスクの境界指標(HD95/ASSD/Boundary-F1@tol)を cv2.distanceTransform だけで実装する](Knowledge/boundary-metrics-2d-cv2-distancetransform.md)
- [シード固定の実験割付へ後から要素を足すときは専用RNGを使う](Knowledge/seeded-design-additive-change-dedicated-rng.md)
- [比較する2つの操作パスは計測を対称に仕込む(片側の計上漏れは条件間比較を壊す)](Knowledge/symmetric-instrumentation-across-comparison-arms.md)
- [計時タスクのタイミング衛生: フォーカス喪失で一時停止 + 席外し監視 heartbeat](Knowledge/timed-task-timing-hygiene-focus-pause-heartbeat.md)
- [必須クラス制約は導入前に実データ全体で成立を検証する(隠れ瞳孔症例)](Knowledge/enforce-required-classes-verify-against-dataset.md)
- [検証用バックグラウンドサーバーは終了後に必ず停止しポートを解放する(WinError 10048 回避)](Knowledge/stop-background-verification-server-to-free-port.md)
- [被験者実験の実施前に「被験者になりきったウォークスルー」で手順書・運用・計測方針の穴を洗い出す](Knowledge/participant-walkthrough-before-study-launch.md)

## 関連リソース
- 計画: `PLAN.md`
- 実装(webapp/実験設計): `scripts/webapp/`, `scripts/prepare_experiment.py`, `scripts/webapp/config/experiment.json`
- 実装(モデル学習): `scripts/make_training_subsets.py`, `scripts/train_subset.py`, `outputs/training_subsets/subsets.json`, `outputs/models/`(`seg{N}.pth`, `train_all.log`, `train_small.log`), `.venv`(transformers 4.57.3)
- 実装(リーク検証・テストセット): `scripts/eval_on_heldout.py`, `scripts/make_heldout_test.py`, `outputs/training_subsets/heldout_test.json`(固定 held-out テスト463枚/37患者), `outputs/models/eval_final_463.log`(全8モデル最終スコア)
- 参照モデル: `C:\Users\CorneAI\Eyelid_Iris_pupil_seg_comparison\train_SegFormerB1_Amodal_Blur_v3.ipynb`
  （checkpoint: `Ablation_SegFormerB1_Amodal_Blur_v3/models/segformer_b1_amodal_v3_best.pth`）
- 参照データ: `C:\Users\CorneAI\Eyelid_Iris_pupil_seg_comparison\Images\`（images, eyelid_caruncle_seg_0-3000.xml, obb_iris_pupil_1-3000.xml）
- 前リポジトリ調査記録: `C:\Users\CorneAI\Eyelid_Iris_pupil_seg_comparison\Experimental_record\20260614.md`
