# 医用研究リポジトリを公開する前のデータ衛生(.gitignore 設計とコミット前検証)
- type: pattern
- created: 2026-06-30
- tags: [git, data-privacy, medical, gitignore, workflow]

## 概要
医用研究プロジェクトを git/GitHub に上げるとき、「画像を外す」だけでは不十分。
**ファイル名・設定・結果ファイルに埋め込まれた患者識別情報**と**大容量の患者由来モデル**を
除外し、`git init` 後・**コミット前に**ステージ内容を機械的に検証してから commit する。

## 背景・発見経緯
本プロジェクト(Eyelid HITL)で「commit、画像は外して push」依頼に対し、画像はそもそも
リポジトリ外参照で問題なかった一方、`experiment.json` / `training_subsets/` / `results/` に
**患者ファイル名(患者ID付き)が埋め込まれ実質的に患者識別情報**であること、`outputs/models/*.pth`
が **419MB** あることが判明。公開 push は取り消しにくい(キャッシュ・インデックス残存)ため、
除外方針を固めてから作業した。実際にジャンクファイル(特殊文字を含むファイル名)が当初の
`.gitignore` に一致せずステージされる事故もあり、コミット前検証で捕捉できた。

## 詳細
1. **何が患者識別情報か洗い出す**: 画像本体だけでなく、ファイル名に患者IDを含む派生物
   (実験割付 JSON・サブセット定義・結果 JSONL/CSV)も該当。ログ・研究ノート・集計CSV
   (`heldout_dice.csv` 等)は中身を確認し、患者名を含まなければ保持してよい。
2. **`.gitignore` を区分けして書く**: 患者識別情報 / 大容量モデル(`*.pth`) / 入力データ
   (`data/`) / 環境(`.venv`,`__pycache__`,`.claude/settings.local.json`) / ジャンク / OS・editor。
3. **コミット前にステージ検証**(必須): `git add` 後 `git ls-files`(または `git status`)で
   `.pth`・患者ファイル名・ジャンクが**含まれていないこと**を目視+機械確認してから commit。
   パターン不一致でジャンクが紛れることがあるので、実ファイル名に合わせてパターンを直す。
4. **モデル等の大容量・患者由来バイナリは git に入れず別途配布**。
5. **push 認証**: Windows では Git Credential Manager があればブラウザ1回サインインで push 可
   (PAT手入力不要)。`gh` CLI 自動インストールは UAC 昇格が必要で headless では中断し得る
   → 空 private リポジトリを GitHub 側で作成 → URL を受け取り `remote add`/`push` が確実。

## 追記 (2026-06-30): 実 push で確認できたこと
- 上記方針で実際に **push 成功**。空 private リポジトリ(`ykitaguchi77/HITL_validation_test`)を
  ユーザーが作成 → `git remote add origin <URL>` / `git branch -M main` / `git push -u origin main`。
  **GCM のブラウザ1回サインインのみで認証完了**(`gh` CLI は結局不要。自動インストールは UAC で中断したが影響なし)。
- **push 後もリモート側を機械検証**(コミット前検証だけで終わらせない):
  - リモート HEAD == ローカル HEAD(`git ls-remote origin` の sha と `git rev-parse HEAD` 照合)。
  - リモートのファイル数がローカルと一致(本件 49)。
  - 患者ファイル名の機微検索。ヒットしても**中身を確認**する: 本件は `make_training_subsets.py`
    が正規表現にファイル名で部分一致しただけのスクリプト本体で、患者データは含まなかった
    (= ファイル名の文字列一致と実データ混入は別物。誤検知を恐れて保持物まで消さない)。

## 追記 (2026-09-15): 2回目以降のコミットでも同じスキャンを回す(差分コミット向けの手順)・設定ファイル内の仮パスワードの扱い
- 出典: Experimental_record/20260915.md(追記7)
- 初回コミットで `.gitignore` を整えても、その後 2か月分の変更を纏める **2回目のコミット(`a5951a0`・31ファイル)でも
  同じ手順を省かない**。差分コミット向けに手順を再利用した形:
  1. **除外の持続確認**: `git check-ignore -v <代表ファイル>` で `experiment.json` / `outputs/results/` /
     `outputs/training_subsets/` / `*.pth` が引き続き ignore 対象であることを毎回確かめる(`.gitignore` 編集事故の検出)。
  2. **正規表現は実データから導出**: 患者ファイル名の数字を `#` にマスクして形を見てからパターンを書く
     (`[0-9]{3}-[0-9]{8}-[0-9]{2}-[0-9]{6}_[0-9a-f]{20,}`)。推測パターンだと取りこぼす。
  3. **対象はステージ予定ファイルだけ**: `git add -A -n` の出力を grep の入力にすると、ignore 済み・未変更ファイルを
     含めずに機械検証できる(初回の `git ls-files` 方式より差分コミットに向く)。
  4. **誤検知の切り分け**: `.pth` / `HITL_AUTH_PASS` 等のヒットが研究ノート・Knowledge・スクリプト本文の説明文なら保持してよい。
     ヒット=即除外にしない(6/30 の教訓と同じ)。
- **git 管理下の起動スクリプトの秘密値**: `run_server.ps1` が共有パスワード変数 `$Pass` を持つ場合、リポジトリに入るのは
  仮値(`"hitl"`)のみに保ち、`git show HEAD:<path> | grep` で HEAD と同じ仮値かを照合。本番値へ書き換えた後はその変更を
  **コミットに含めない**(環境変数/`.env`(gitignore)化が本筋だが、当面は目視ガード)。
- 研究ノート(`Experimental_record/*.md`)に「パスワードの在り処」を書くときは**値ではなく場所**だけを書く
  (本件は仮値 `hitl` が記録に残っていたが、本番値ではないので許容。本番値は決して記録しない)。
- `git push` は Claude Code 自動モードでは分類器にブロックされることがある(外部公開操作扱い)。
  無理に回避せず、ユーザーに `! git push origin main` を実行してもらう → [[git-push-blocked-by-auto-mode-classifier]]。

## 適用場面
- 医用・個人情報を扱う研究コードを GitHub(特に public/共同)へ初めて上げるとき。
- 「画像は外して」程度の曖昧な依頼を、識別情報全般の除外へ具体化するとき。
- 大容量モデル checkpoint を含むリポジトリの初回コミット設計。

## 関連
- Experimental_record/20260630.md
- [[hitl-blinding-and-confound-design]]
