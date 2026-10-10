/* Operations tutorial content (shown on an annotator's first session and via the ? button).
 * Pure data: title + HTML with a small inline SVG illustration per step. */
(function (HITL) {
  const K = (s) => `<kbd>${s}</kbd>`;
  // tiny illustration helpers (image-like dark box, eye-ish outline)
  const eye = (extra = "") => `
    <svg viewBox="0 0 280 200">
      <ellipse cx="140" cy="100" rx="110" ry="50" fill="#3a2a22"/>
      <ellipse cx="140" cy="100" rx="42" ry="42" fill="#5a3a1a"/>
      <ellipse cx="140" cy="100" rx="16" ry="16" fill="#111"/>
      ${extra}
    </svg>`;
  const lidPoly = (pts, cls = "") => `<polygon points="${pts}" fill="rgba(255,59,48,0.18)" stroke="#ff3b30" stroke-width="2" ${cls}/>`;
  const dots = (pts, color = "#fff", r = 4) => pts.split(" ").map((p) => {
    const [x, y] = p.split(","); return `<circle cx="${x}" cy="${y}" r="${r}" fill="${color}" stroke="#ff3b30" stroke-width="1.5"/>`; }).join("");
  const LID = "30,100 60,72 100,55 140,50 180,55 220,72 250,100 220,128 180,145 140,150 100,145 60,128";
  const LID_PTS = LID;

  // 教示: セッション開始前に表示（計測前）。本番は初回だけでなく毎回同じ短い文を出す
  HITL.SESSION_INTRO = (s) => {
    if (s.key === "p_manual") return `
      <ul>
        <li>まぶた（涙丘を含む一体）をポリゴンで、虹彩・瞳孔を楕円で、<b>ゼロから</b>描く練習です（2 枚）。</li>
        <li><b>練習のみ、完成後に模範解答が点線で表示されます。</b> 微妙な部分（目頭・目尻の端、まつ毛の付け根、
            涙丘の含め方、隠れた虹彩の楕円の描き方）のニュアンスを模範解答で確認し、
            <b>本番でも模範解答と同じようなアノテーションができるように</b>練習してください。</li>
        <li>練習は解析に含まれません。操作に慣れるまで何度でも構いません。</li>
      </ul>`;
    if (s.key === "p_hitl") return `
      <ul>
        <li>AI の提案を<b>修正して仕上げる</b>練習です（3 枚、提案の質はわざと違えてあります）。</li>
        <li><b>提案が大体合っていても、そのまま提出しないでください。</b> 拡大して、
            <b>ピクセル単位で模範解答と同じになるまで直す</b>のが本番のルールです（練習 1 で見た模範解答が基準）。</li>
        <li>大きくずれている・一部しか無い提案は、🗑 で消してゼロから描いて構いません。<b>自分が速く正確に仕上がる方</b>を選んでください。</li>
        <li>提出後に模範解答が点線で出ます。「提案を信じすぎていないか」を確認してください。</li>
      </ul>`;
    return `
      <ul>
        <li>このセッションは 10 枚。<b>AI の提案がある画像と無い画像が混ざって</b>出ます（どの段階の AI かは表示されません）。</li>
        <li>提案があれば修正、無ければゼロから描く。<b>どちらも練習で見た模範解答と同じように</b>仕上げてください。
            <b>提案が大体合っていても、ピクセル単位で正解を目指して</b>ください。</li>
        <li>いつも通りのペースで。提出後は戻れません。困ったら左下の <b>?</b>（計測は止まります）。</li>
      </ul>`;
  };

  HITL.TUTORIAL_STEPS = [
    {
      title: "画面の見方",
      html: `<div class="fig">
        <svg viewBox="0 0 280 200">
          <rect x="0" y="0" width="280" height="24" fill="#1c2128"/><text x="8" y="16" fill="#9ecae1" font-size="10">Session 1  3/10</text>
          <rect x="196" y="4" width="78" height="16" rx="3" fill="#2ea043"/><text x="204" y="16" fill="#fff" font-size="9">提出して次へ →</text>
          <rect x="0" y="24" width="28" height="176" fill="#1c2128"/>
          <text x="8" y="44" fill="#ddd" font-size="12">▢</text><text x="8" y="64" fill="#ddd" font-size="12">⬡</text><text x="8" y="84" fill="#ddd" font-size="12">◯</text><text x="8" y="104" fill="#ddd" font-size="12">✋</text><text x="9" y="184" fill="#ddd" font-size="12">?</text>
          <rect x="200" y="24" width="80" height="176" fill="#1c2128"/>
          <rect x="206" y="32" width="68" height="14" rx="2" fill="#2b3946" stroke="#4fc3f7"/><text x="210" y="42" fill="#fff" font-size="8">■ Eyelid</text>
          <rect x="206" y="50" width="68" height="14" rx="2" fill="#2b3946"/><text x="210" y="60" fill="#fff" font-size="8">■ Iris</text>
          <rect x="206" y="68" width="68" height="14" rx="2" fill="#2b3946"/><text x="210" y="78" fill="#fff" font-size="8">■ Pupil</text>
          <text x="206" y="104" fill="#9ecae1" font-size="8">操作（今できること）</text>
          <rect x="206" y="108" width="68" height="40" fill="#161b22"/>
          <ellipse cx="114" cy="110" rx="70" ry="34" fill="#3a2a22"/>
        </svg>
        <div>
          <ul>
            <li><b>左のツール</b>: ${K("V")} 選択・編集 ／ ${K("P")} ポリゴン ／ ${K("E")} 楕円 ／ ${K("space")} 移動 ／ ${K("?")} このチュートリアル</li>
            <li><b>右のクラスタブ</b>で編集する対象（まぶた・虹彩・瞳孔）を選びます。タブを押すと、その図形が選択状態になります。</li>
            <li><b>「操作（今できること）」</b>には、いまの状態で使える操作がつねに表示されます。迷ったらここを見てください。</li>
            <li>終わったら右上の<b>「提出して次へ」</b>。</li>
          </ul>
          <p class="note">本番では、AI の提案がある画像（修正する）と、無い画像（ゼロから描く）が混ざって出ます。どちらも「正しいと思う輪郭」に仕上げてください。</p>
        </div></div>`,
    },
    {
      title: "まぶたをゼロから描く（ポリゴン）",
      html: `<div class="fig">
        ${eye(`<polyline points="30,100 60,72 100,55 140,50 180,55" fill="none" stroke="#ff3b30" stroke-width="2"/>
               ${dots("30,100 60,72 100,55 140,50 180,55")}
               <circle cx="30" cy="100" r="9" fill="none" stroke="#ffd166" stroke-width="2" stroke-dasharray="3 2"/>
               <text x="188" y="50" fill="#ffd166" font-size="11">クリックで点を打つ</text>
               <text x="34" y="122" fill="#ffd166" font-size="11">最初の点に戻ると閉じる</text>`)}
        <div>
          <ul>
            <li>右で <b>Eyelid</b> を選び、${K("P")}（⬡）でポリゴンツールにします。</li>
            <li>輪郭に沿って<b>クリック</b>で点を打ちます（${K("space")} でも打てます）。<b>涙丘（内側の赤い部分）も含めて一体</b>で囲みます。</li>
            <li><b>最初の点をクリック</b>か<b>ダブルクリック</b>／${K("Enter")} で閉じて確定。${K("Esc")} で描き直し。</li>
            <li>点は多すぎなくて大丈夫です。閉じたあとで辺の中点をドラッグして足せます（次のページ）。</li>
          </ul>
        </div></div>`,
    },
    {
      title: "虹彩・瞳孔（楕円）",
      html: `<div class="fig">
        ${eye(`<ellipse cx="140" cy="100" rx="44" ry="40" fill="none" stroke="#34c759" stroke-width="2" transform="rotate(-15 140 100)"/>
               <rect x="92" y="56" width="96" height="88" fill="none" stroke="#4fc3f7" stroke-width="1" stroke-dasharray="4 3" transform="rotate(-15 140 100)"/>
               ${["96,60", "184,60", "96,140", "184,140"].map((p) => { const [x, y] = p.split(","); return `<rect x="${x - 4}" y="${y - 4}" width="8" height="8" fill="#fff" stroke="#4fc3f7" transform="rotate(-15 140 100)"/>`; }).join("")}
               <circle cx="140" cy="40" r="5" fill="#fff" stroke="#4fc3f7" transform="rotate(-15 140 100)"/>
               <text x="150" y="36" fill="#ffd166" font-size="11">回転ハンドル</text>
               <ellipse cx="140" cy="100" rx="17" ry="16" fill="none" stroke="#0a84ff" stroke-width="2"/>`)}
        <div>
          <ul>
            <li>右で <b>Iris</b>（または Pupil）を選び、${K("E")}（◯）で<b>ドラッグ</b>して楕円を作ります。</li>
            <li>作ったら ${K("V")} 選択ツールで、四隅のハンドルで<b>拡大縮小</b>、上のハンドルで<b>回転</b>、本体ドラッグで<b>移動</b>。矢印キーで 1px ずつ動かせます。</li>
            <li>虹彩はまぶたに隠れた部分も含めた<b>完全な楕円</b>で（アモーダル）。<b>横目（周辺視）の画像では楕円を傾けて</b>ください。</li>
          </ul>
        </div></div>`,
    },
    {
      title: "AI の提案を直す（頂点の移動・追加・削除）",
      html: `<div class="fig">
        ${eye(`${lidPoly(LID_PTS)} ${dots(LID_PTS)}
               <circle cx="100" cy="55" r="7" fill="#ffd166"/>
               <path d="M100,55 L118,38" stroke="#ffd166" stroke-width="2" marker-end="url(#a)"/>
               <circle cx="80" cy="63" r="3.5" fill="#ff3b30" opacity="0.7"/>
               <text x="60" y="34" fill="#ffd166" font-size="11">頂点をドラッグ</text>
               <text x="150" y="176" fill="#ffd166" font-size="11">辺の中点(小さい点)をドラッグで点追加</text>
               <defs><marker id="a" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#ffd166"/></marker></defs>`)}
        <div>
          <ul>
            <li>提案がある画像は ${K("V")} 選択ツールで始まります。右で <b>Eyelid</b> を選ぶと、その図形が編集できます。</li>
            <li><b>提案が大体合っていても、拡大してピクセル単位で</b>模範解答と同じになるまで直してから提出します。</li>
            <li><b>頂点をドラッグ</b>で移動。<b>辺の中点（小さい点）をドラッグ</b>すると点が増えます。</li>
            <li>頂点を<b>クリックして</b> ${K("Backspace")} で削除（${K("Alt")}+クリックでも）。</li>
            <li>大きくずれている・一部しか無いときは、🗑 で<b>図形ごと消してゼロから描いても構いません</b>（どちらでも可。自分が速く正確に仕上がる方で）。</li>
            <li>${K("Shift")}+クリックで点を続けて追加できます（ダブルクリックで確定）。</li>
          </ul>
        </div></div>`,
    },
    {
      title: "複数の点をまとめて動かす・消す（Ctrl+ドラッグ）",
      html: `<div class="fig">
        ${eye(`${lidPoly(LID_PTS)} ${dots(LID_PTS)}
               <rect x="150" y="38" width="112" height="76" fill="rgba(79,195,247,0.15)" stroke="#4fc3f7" stroke-width="1.5" stroke-dasharray="6 4"/>
               ${dots("180,55 220,72 250,100", "#4fc3f7", 5)}
               <text x="150" y="30" fill="#ffd166" font-size="11">Ctrl+ドラッグで囲む</text>
               <text x="30" y="180" fill="#ffd166" font-size="11">→ ドラッグ/矢印キーで移動、Delete で削除</text>`)}
        <div>
          <ul>
            <li>まぶたのポリゴンを選んだ状態で、${K("Ctrl")}<b>を押しながらドラッグ</b>して点を四角く囲みます。</li>
            <li>囲んだ点は、その範囲を<b>ドラッグ</b>するか<b>矢印キー</b>で<b>まとめて移動</b>できます。</li>
            <li>${K("Delete")} で<b>まとめて削除</b>（3 点は残ります）。${K("Esc")} で選択解除。</li>
            <li>提案の一部分だけが大きくずれているとき（例: 目尻側だけ）に便利です。</li>
          </ul>
          <p class="note">Ctrl を押さない普通のドラッグは「画像の移動」です。</p>
        </div></div>`,
    },
    {
      title: "画像の見方を変える",
      html: `<div class="fig">
        ${eye(`<text x="20" y="30" fill="#ffd166" font-size="11">ホイール: 拡大縮小</text>
               <text x="20" y="180" fill="#ffd166" font-size="11">何もない所をドラッグ / space+ドラッグ: 移動</text>`)}
        <div>
          <ul>
            <li><b>マウスホイール</b>で拡大・縮小（カーソル位置を中心に）。</li>
            <li><b>何もない所をドラッグ</b>、または ${K("space")} を押しながらドラッグで画像を移動。${K("F")} で全体表示、⛶ で最大化。</li>
            <li>右下の<b>明るさ・コントラスト</b>スライダーで境界を見やすくできます（保存データには影響しません）。</li>
            <li>🎨 で塗りつぶし表示の ON/OFF。</li>
          </ul>
        </div></div>`,
    },
    {
      title: "提出・中断・時間の計測",
      html: `<div class="fig">
        <svg viewBox="0 0 280 200">
          <rect x="20" y="30" width="240" height="40" rx="6" fill="#2ea043"/><text x="60" y="55" fill="#fff" font-size="13">提出して次へ →</text>
          <text x="30" y="100" fill="#ddd" font-size="11">↓ 確認画面（輪郭を最終チェック）</text>
          <text x="30" y="125" fill="#ddd" font-size="11">↓ 負担度 1〜9 を回答（時間に含まれません）</text>
          <text x="30" y="150" fill="#ddd" font-size="11">↓ 次の画像へ（戻れません）</text>
          <rect x="20" y="165" width="70" height="24" rx="4" fill="#d1242f"/><text x="38" y="181" fill="#fff" font-size="11">中断</text>
          <text x="98" y="181" fill="#9ecae1" font-size="10">= セッションの記録を破棄してやり直し</text>
        </svg>
        <div>
          <ul>
            <li>3 クラスがそろったら<b>提出して次へ</b> → 確認画面で<b>確認OK</b>（または<b>修正</b>で戻る）→ <b>負担度 1〜9</b> を回答。</li>
            <li>提出後は前の画像に戻れません。<b>中断</b>はセッションの記録を破棄して最初からやり直すときだけ使います。</li>
            <li>目標は練習で見た模範解答と同じアノテーションです。いつも通りのペースで作業してください。</li>
            <li>別のウィンドウに切り替えると自動で一時停止します（戻ると再開）。このチュートリアルを開いている間も止まっています。</li>
            <li>操作に迷ったら左下の ${K("?")} でいつでもこの説明を開けます。</li>
          </ul>
        </div></div>`,
    },
  ];
})(window.HITL = window.HITL || {});
