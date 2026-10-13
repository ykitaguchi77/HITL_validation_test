# Gmail 下書きはテキスト形式だと段落内に改行が入る。HTML で 1 段落 = 1 つの <p> にする
- type: technique
- created: 2026-10-11
- tags: [gmail, email, draft, html, participant-communication]

## 概要
API(MCP の `create_draft` / `update_draft`)でテキスト形式の下書きを作ると、Gmail は長い行を送信時に自動で折り返す。受信側では段落の途中に改行が入り、スマホや幅の違う画面で読みにくくなる。本文を HTML にし、段落ごとに `<p>` でまとめると、受信者の画面幅に合わせて自然に折り返される。

## 背景・きっかけ
アノテータ 3 名への依頼メール下書きを作った際、ユーザーから「Gmail では段落内は改行しないでください。見にくくなります」と指摘された。過去の送信メールでも「good / fair / bad / worst」の後に不自然な改行が入っており、同じ原因だった。

## 手順
1. 本文を `htmlBody` で渡す。段落は `<p>…</p>`、段落内に改行を入れない。
2. `<br>` を使うのは、意図して行を分けたい箇所だけにする(見出し「■」の直後、URL の行、ID/PASS の行、箇条書き「・」の行)。
3. URL は `<a href="…">…</a>` にする。個人リンクのように宛先ごとに違う値は、スクリプトで差し込んでから渡す(手で打たない)。
4. 更新後は `get_draft` を PLAIN_TEXT などの詳細形式で読み直し、宛先・cc・差し込んだリンクが残っているか確認する(MINIMAL の snippet には宛先が出ない)。

## 注意点
- `update_draft` は本文の差し替えでも宛先・cc を含めて渡す前提で確認する。更新後の読み直しを省かない。
- 署名や名乗り(例:「大阪大学の北口です」)など、ユーザー固有の書式はメモリに残して次回以降も揃える。
- 参加者向けメールでは時間計測に触れない(`Knowledge/timed-task-instructions-never-mention-speed.md`)。

## 関連
- Experimental_record/20261011.md

## 追記 (2026-10-13)
- 出典: Experimental_record/20261013.md
- この規則を共有スキル `claude-skills/gmail-draft-attach/SKILL.md` に反映した(commit `8311c75`)。旧規則の「段落をテキストで 1 行に書く」では Gmail の自動折り返しを防げないため、HTML の `<p>` を使う形に改めた。
- 共有リポジトリに入れるのは汎用の書式規則だけにする。名乗りなど個人を特定できる書式は、ローカルのメモリだけに残す。
- Windows で `bin/lint-skills.sh` を動かすときは `PYTHONUTF8=1` を付ける(付けないと cp932 エラーで検査前に落ちる)。
