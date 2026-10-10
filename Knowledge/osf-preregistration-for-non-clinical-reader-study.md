# 非臨床の被験者実験(reader study)は UMIN ではなく OSF Registries に解析計画を事前登録する
- type: technique
- created: 2026-09-15
- tags: [preregistration, osf, umin, reader-study, analysis-plan, publication]

## 概要
アノテータ(reader)を被験者とし、作業時間・精度をアウトカムとする HITL 効率実験は、
健康関連アウトカムを扱わないため ICMJE の「臨床試験」にも国内指針の「介入研究」にも該当せず
**UMIN-CTR / jRCT の登録義務はない**。査読で効くのは「解析計画がデータ収集前に固定されていた
第三者証明」なので、**OSF Registries(OSF Preregistration テンプレート)に解析計画書を登録し、
登録 DOI を論文 Methods に書く**のが最短・最も効果的。自前 git のコミットハッシュは補助証拠にとどめる。

## 背景・発見経緯
2026-09-15、事前解析計画書 `outputs/docs/analysis_plan.md` を作成した直後にユーザーから
「UMIN に上げた方が良い? 介入ではないので不要? 前向きと言ってよい?」と質問。
条件割付の対象がアノテータ(どのモデルの予測を見せるか)で、アウトカムが作業時間・Dice で
あることから UMIN 不要と判断し、代替として OSF 登録用の英文ドラフト
`outputs/docs/osf_preregistration.md` を作成 → 著者・IRB・エンバーゴ・承認日を埋めて登録可能な状態にした。

## 詳細
### ドラフトの作り方
- OSF Preregistration テンプレートの5部構成に見出しを揃えておくと、フォームへは上から順にコピペするだけで済む:
  Study Information(Title/Authors/Description/Hypotheses) → Design Plan(Study type/Blinding/Study design/Randomization)
  → Sampling Plan(Existing data/Data collection/Sample size/Rationale/Stopping rule)
  → Variables(Manipulated/Measured/Indices) → Analysis Plan(Models/Transformations/Inference criteria/Exclusion/Missing/Exploratory)
  → Other(Ethics/コード公開方針)。
- **Study type は「実験・非臨床試験」と明記**。「前向き」と書く場合は画像が既存データであることを併記し、
  *prospective, within-subject, blinded reader study using retrospectively collected images* または
  **MRMC (multi-reader multi-case) design** と表現する(reader × case で全 reader が全 case を読む設計は放射線・眼科 AI 論文で定着)。
- 患者 ID を含む割付ファイル(`experiment.json` 等)は**アップロードせず sha256 だけを記載**する。
  割付が登録時点で固定されていたことを第三者検証可能にしつつ、短いエンバーゴ(1週間)で公開されても安全。
- 空欄はプレースホルダ `[ ... ]` で残し、提出前に `grep "\[ "` でゼロを確認する。

### 登録手順(所要 30 分程度)
1. osf.io で Sign Up(所属メール or ORCID)→ Create new project(Private のままで可、Storage は Germany か US)。
2. Registrations タブ → New registration → 「OSF Preregistration」を選択 → 各設問にドラフトを貼付(下書きは自動保存)。
3. Files に `analysis_plan.md`・ドラフトをアップロードし Attachments で選択(登録時点でスナップショット凍結)。
4. Review → Register → **Embargo** を選び終了日を設定(Immediate public にすると即公開)。
   共同研究者は 48h 以内に承認(放置で自動承認)、単独なら即確定。DOI `10.17605/OSF.IO/xxxxx` が付与される。
5. **最初の被験者が本番を始める前に Register まで完了**させる(登録日時 < 収集開始が証拠になる)。
6. 登録は取り消せない。計画変更は Update registration で改訂版を追加し、論文で逸脱として明記する。

## 適用場面
- 被験者を伴うが健康アウトカムを扱わないユーザースタディ・reader study・アノテーション効率実験。
- 事前解析計画書([[pre-specified-analysis-plan-small-n-user-study]])を書き終えて「どこに固定するか」を決めるとき。
- 倫理申請時には「介入研究ではない」旨を一文確認しておく(該当性判断は委員会の管轄)。

## 関連
- Experimental_record/20260915.md
- [[pre-specified-analysis-plan-small-n-user-study]]
- [[pre-launch-paper-risk-triage]]

## 追記 (2026-09-15)
- 出典: Experimental_record/20260915.md
- エンバーゴは当初 1 週間としたが、ユーザー判断で **3 日**に短縮(`Embargo: 3 days.`)。文書に患者情報・重み・割付内容を含めていない
  (`experiment.json` は sha256 のみ)ので短縮しても公開リスクはない。
- 登録の代行をブラウザ自動操作で試みた際、OSF が Minor Service Outage 中で `osf.io/dashboard` が真っ白だった。
  代行前に `status.cos.io` と `api.osf.io/v2/` の応答を curl で確認する([[browser-automation-check-service-status-first]])。
- Register は取消不可なので、代行時も最終送信の直前でユーザー確認を取る。

## 追記 (2026-09-16)
- 出典: Experimental_record/20260916.md
- **現行(2026-09 時点)の「OSF Preregistration」テンプレートは 8 ステップ構成**:
  Metadata(Title / Description / Contributors / License / Subjects / Tags)→ Overview(仮説)→ Research Design
  (Study type・因果推論の種類・盲検の選択式 + **Foreknowledge**=データ既知性の選択式+説明)→ Sampling → Variables →
  Analysis Plan(Statistical models / Transformations / Inference criteria / Data exclusion / Missing data / Exploratory)→ Other → Review。
  上記「ドラフトの作り方」の 5 部構成(旧版)でも全項目を埋められたが、**ドラフトは最初から現行の 8 ステップ順で書く**方が転記が速い。
  Foreknowledge は「画像・GT・モデルは既存だがアウトカムは未収集、割付は seed 固定(sha256 記載)」のように書けば
  「limited observation could not influence analysis decisions」を選べる。
- **プロジェクトを先に作る必要はない。** `https://osf.io/registries/osf/new` で「Do you have an existing OSF project? = No」→
  テンプレート選択 → Create draft で登録単体のドラフト(`osf.io/registries/drafts/<id>/`)ができ、Next ごとに自動保存・
  左ナビに ✓ が付く。上記「登録手順」1〜2 はこの手順に置き換える。
- **添付ファイルは Files タブではなく、Analysis Plan の設問内(Statistical models)の Upload ボタン**で付ける。
  `analysis_plan.md` をここに添付すれば登録スナップショットに凍結される。`experiment.json`(患者 ID 入り)は添付しない。
- License は OSF 既定の **CC0 1.0 Universal** になる。CC-BY 等にしたければ Metadata で変更(Review から Back で戻れる)。
- Review → Register を押すと公開設定ダイアログが出る。**Embargo の終了日は登録日+3 日が最短**(日付ピッカーでそれより前は選べない)。
  その後の「Submit」が取消不可の確定(withdraw は可能だが記録が残る)なので、代行時はここで止めて要約表を見せて確認を取る。
- 所要時間: ログイン確立後、転記〜Submit 直前まで Chrome 拡張で約 25 分(2026-09-16 17:11〜17:35)。


## 追記 (2026-09-16, 2回目)
- 出典: Experimental_record/20260916.md
- **Submit 後の登録は即「Registered」にならず「Pending Embargo Approval」で止まる**(単独貢献者でも同じ)。貢献者宛の承認メールの
  リンクをクリックするか、**48 時間放置で自動承認**。承認後に登録時刻(Submit 時刻)がタイムスタンプとして固定される。
  被験者実験の開始前に「登録済み」を主張するには Submit 時刻で足りるが、承認メールは早めに踏んでおく。
- **DOI(`10.17605/OSF.IO/<id>`)はエンバーゴ明けの公開時に付与**される。それまでは登録 URL(`https://osf.io/<id>`)を
  論文 Methods・研究ノートに記載し、公開後に DOI へ差し替える。上記「登録手順」4 の「DOI が付与される」は公開後の話。
- 「既存プロジェクト無し」で登録しても、OSF は**関連プロジェクト(別 ID)を自動生成**し、設問内で添付したファイル
  (`analysis_plan.md`)をそこに格納する。登録 URL と関連プロジェクト URL の両方を記録しておく。
- 実例: 本研究の登録 `https://osf.io/d7e2g`(2026-09-16 19:30 JST Submit、エンバーゴ 2026-09-19 まで、関連プロジェクト
  `https://osf.io/awgqf`)。ドラフト作成〜Submit までの実作業は Chrome 拡張でのべ約 30 分、OSF 障害・ログイン待ちを含む
  カレンダー時間は 9/15 18:20 〜 9/16 19:30。
- 登録後にローカルへ残すもの: ドラフト md の末尾に「Registration record」節(URL・日時・エンバーゴ・状態・添付・テンプレート差異の注記)
  を追記し、todo の登録項目を完了にしてコミットする。

## 追記 (2026-09-19)
- 出典: Experimental_record/20260919.md
- **登録後・データ収集前に設計そのものが変わる事例**: エンバーゴ明け当日に、別プロジェクトの成果(SAM decoder-LoRA の
  1 枚 1 エポック学習で十分な精度)を受けてモデル系列(SegFormer-B1 8 条件 → LoRA n-shot 9 条件)ごと置換する決定が出た。
  登録は取消不可なので、選択肢は「Update registration で改訂版を追加(旧登録との差分=逸脱を明記)」か「新規登録」の 2 つ。
  **本番データが 0 件なら、旧登録を "superseded" として新規登録し、論文には両 DOI と変更理由を書く**のが最も説明が簡単
  (改訂版だと「収集開始後の変更」と誤読されうる)。
- 教訓: 事前登録は「最初の被験者が始める直前」まで遅らせてもよい。今回は登録(9/16)と設計変更(9/19)の間に 3 日しかなく、
  登録が無駄になった。**並行プロジェクトの結果待ちがあるなら、その結論が出るまで Register を保留**する。
  登録の準備(ドラフト・添付ファイル)は先に済ませておけば、Submit 自体は 30 分で終わる。
- 再登録時は `experiment.json` の sha256・条件数・`log10(train_size)` の定義(n-shot 枚数)・品質ゲートの有無を全て更新し、
  `analysis_plan.md` のバージョンを v2.0 に上げる。
