# 実ユーザーの初回セッション 1 本を「列単位」で監査し、0 を「未操作 / 計上漏れ / 未定義」に仕分ける
- type: technique
- created: 2026-09-20
- tags: [instrumentation, user-study, hitl, metrics, data-audit, verification]

## 概要
自前計測の被験者実験では、API テスト(値が列に到達するか)と UI 自動操作(経路が動くか)が両方 PASS していても、
**「保存された値が妥当か」は実ユーザーの 1 セッション分の実データを列ごとに読んで初めて判定できる**。
特に **0 は 3 つの意味を持ち得る**(①本当に操作しなかった ②計上経路の抜け ③その条件では未定義=NaN にすべき)ので、
列ごとに「この行で 0 は妥当か」を問う監査を、本番データ収集前に必ず 1 回行う。

## 背景・発見経緯
HITL 用量反応実験(n-shot 提案 vs 手動)の webapp で、TestClient 検証(全列到達・盲検・応答時間)と Playwright 検証
(一括削除・per-class 計測・undo)を PASS させた翌日、研究者本人が test アカウントで Session 1(10 枚)を通しで実施。
`summary.csv` を全列表示して眺めたところ:
- 手動 1 枚目で eyelid を 32 点描いたのに `eyelid_time_sec=0`・`eyelid_vertices_added=0`(→ ②計上漏れ: `metrics.reset()` が
  直前に設定した既定クラスを消していた。全体列は正しく、クラス別列だけが最初のタブ操作まで無帰属)
- 手動画像(提案なし)の `*_correction_dice=0`(→ ③未定義: 空の初期形状と最終形状の Dice をそのまま保存していた。
  automation bias 解析に「修正量ゼロ」として混入し得る)
どちらも検証スクリプトは通っていた。Playwright の手順が「タブを押す」「提案付きで提出する」経路しか通らず、
**既定クラスのまま作業する経路・手動提出の経路**が抜けていたため。

## 詳細
1. **監査の単位は行×列**。`summary.csv` を `to_string()` で全列を横に並べ、条件列(n・seed・視線)でソートして眺める。
   集計統計(平均・分布)より先に生の行を見る — 計上漏れは「ある行だけ 0」という形で出る。
2. **0 の 3 分類**を列ごとに判定する:
   - 未操作の 0: 他の列(全体カウント・events)と整合しているか確認(例: 全体 `vertices_added=32` なのにクラス別合計 0 は矛盾)。
   - 計上漏れの 0: 同じ指標を生む**全経路**(既定状態のまま作業・別入口からの操作)を洗う([[symmetric-instrumentation-across-comparison-arms]])。
   - 未定義の 0: その条件(アーム)で意味を持たない指標は **NaN/None** で保存し、0 で埋めない。集計時に「0 = 修正なし」と誤読される。
3. **状態のリセットと既定値の順序**: `reset()` は既定状態も消す。リセット後に「既定選択」を再適用する呼び出しを必ず置き、
   検証では**既定のまま操作する経路**を 1 本入れる([[per-class-effort-attribution-by-active-class]])。
4. 監査は同時に**研究上の初期所見**も出す(時間の用量反応の向き・無修正受入の実例・構造別の手描き精度など)。
   1 セッションでも「教示を足すべきか」「非劣性マージンの構造差」のような設計判断の材料になる。
5. 修正後は再検証(API テスト)+サーバ再起動+todo に「発見 → 修正」を残す。監査に使った test 記録は解析除外だが削除しない
   (バグの証拠として残る)。

## 適用場面
- 自前の JS/Python 計測で時間・クリック・編集数・修正量を保存する被験者実験全般(HITL・reader study・UI 効率比較)。
- 検証スクリプトが全 PASS した直後、本番データ収集を始める前。実装済み機能の「発見性」試用([[participant-walkthrough-before-study-launch]])と同じ試用データで実施できる。
- 条件によって定義されない指標(提案なし条件の修正量、片側アームだけの列)を持つ設計。

## 関連
- [[symmetric-instrumentation-across-comparison-arms]](片側の計上漏れ・未定義は NaN)
- [[per-class-effort-attribution-by-active-class]](既定クラスへの帰属と reset の順序)
- [[participant-walkthrough-before-study-launch]](実ユーザー 1 名の試用で答え合わせ)
- [[api-level-checks-miss-stale-ui-copy-snapshot-first-screen]](機械検証が拾えない種類の穴)

## 参照
- Experimental_record/20260920.md
- `scripts/webapp/static/js/app.js`(`loadCurrent()`: `metrics.reset()` → `setActiveClass(this.active)`)
- `scripts/webapp/backend/main.py`(`/api/submit`: 手動は `initial=None`)

## 追記 (2026-09-20)
- 参照: Experimental_record/20260920.md
- **監査は修正後にもう 1 セッション分繰り返す**。同じ症状が再出現したら、修正ごとの所在(サーバ / クライアント)を表にして
  「効いた / 効かない」を照合する — 本件では backend の修正(手動行の `correction_dice` → NaN)は効き、フロントの修正(既定クラスへの帰属)だけ
  効いていなかったため、原因はコードでなく**ユーザーのタブが古い JS のまま**(サーバ再起動後に未リロード)と特定できた
  (→ `Knowledge/stale-frontend-after-server-fix-version-handshake-reload.md`)。
- 2 セッション目の監査で新たに拾えた研究上の観察: 良い提案(eyelid 1.37 px)を疑って作り直し、時間最長・精度悪化(3.83 px)になった試行 = automation bias の**逆向き**。
  `*_prop_assd` → `*_assd` の差(提案より悪化した試行)を副次指標として集計する案を解析計画に追加検討する。

## 追記 (2026-09-20) — 修正の確認は次の実セッションで「全体列 = クラス別列」の一致を見る / 教示変更も同じ監査で数値化できる
- 参照: Experimental_record/20260920.md(Session 3 の監査)
- 修正①(既定クラスへの帰属)と version 照合を入れた後の実セッション 3 では、手動 4 枚で `eyelid_vertices_added` = 50/45/40/46 が
  `vertices_added` と一致し `eyelid_time_sec` が全行に入った。**「全体列とクラス別列の一致」がクラス別計上の健全性の判定式**になるので、
  監査スクリプトに恒久的に入れておく(手動画像なら eyelid のクラス別追加数 = 全体追加数、提案画像なら各クラスの合計 = 全体)。
- 提案が空のクラス(n=16 で瞳孔の提案なし → `pupil_prop_assd` NaN・手動描画)も同じ表で自然に見える。NaN が「未定義」を表す列と
  0 が「未操作」を表す列を混ぜないでおくと、こういう経路も追加コードなしで監査できる。
- 同じ列単位監査は**教示・UI 変更の効果測定**にも流用できる: S1–2(旧教示)と S3(「ピクセル単位で模範解答」)で n≥64 の眼瞼移動頂点数 17〜25 → 38.5、
  眼瞼時間 40〜51 → 87 s と、教示が「良い提案の仕上げ工数」を動かした。pilot 1 名・各 n 2〜3 枚なので因果は断定しないが、
  **教示文は効果量そのものを変えるパラメータ**であり、本番前に確定して Methods に版を書く根拠になる。
