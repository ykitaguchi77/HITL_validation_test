# 研究進捗 Overview
- last_updated: 2026-06-24

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
- [ ] （ablation）vanilla U-Net 版モデルの学習
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

## 関連 Knowledge
- [CVAT風HITLアノーテーションwebappの実装知見](Knowledge/hitl-annotation-webapp-konva.md)
- [Windowsフックで stdin JSON を UTF-8 として読む](Knowledge/windows-powershell-hook-stdin-utf8.md)
- [既存アノテーションから視線方向(正面/周辺)を虹彩偏心度で自動分類](Knowledge/gaze-direction-from-iris-eccentricity.md)
- [SegFormer学習パイプラインを患者リーク無しサブセットへ移植する](Knowledge/segformer-patient-safe-subset-training.md)
- [HITLアノテーション効率研究の盲検化と交絡設計](Knowledge/hitl-blinding-and-confound-design.md)
- [GPU推論WebAppを複数リモート作業者へ配布する(Cloudflare Tunnel + Basic認証)](Knowledge/single-server-webapp-cloudflare-tunnel-distribution.md)
- [Windowsバッチ(.bat)は純ASCIIで書く(日本語コメントは文字化け＆誤実行の原因)](Knowledge/windows-batch-file-ascii-only.md)

## 関連リソース
- 計画: `PLAN.md`
- 実装(webapp/実験設計): `scripts/webapp/`, `scripts/prepare_experiment.py`, `scripts/webapp/config/experiment.json`
- 実装(モデル学習): `scripts/make_training_subsets.py`, `scripts/train_subset.py`, `outputs/training_subsets/subsets.json`, `outputs/models/`(`seg{N}.pth`, `train_all.log`, `train_small.log`), `.venv`(transformers 4.57.3)
- 実装(リーク検証・テストセット): `scripts/eval_on_heldout.py`, `scripts/make_heldout_test.py`, `outputs/training_subsets/heldout_test.json`(固定 held-out テスト463枚/37患者), `outputs/models/eval_final_463.log`(全8モデル最終スコア)
- 参照モデル: `C:\Users\CorneAI\Eyelid_Iris_pupil_seg_comparison\train_SegFormerB1_Amodal_Blur_v3.ipynb`
  （checkpoint: `Ablation_SegFormerB1_Amodal_Blur_v3/models/segformer_b1_amodal_v3_best.pth`）
- 参照データ: `C:\Users\CorneAI\Eyelid_Iris_pupil_seg_comparison\Images\`（images, eyelid_caruncle_seg_0-3000.xml, obb_iris_pupil_1-3000.xml）
- 前リポジトリ調査記録: `C:\Users\CorneAI\Eyelid_Iris_pupil_seg_comparison\Experimental_record\20260614.md`
