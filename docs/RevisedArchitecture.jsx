import { useState } from "react";

const sections = ["why", "cost", "flow", "pdf", "roadmap"];
const sectionLabels = {
  why: "なぜこの構成？",
  cost: "料金シミュレーション",
  flow: "データの流れ",
  pdf: "PDF取り込み方法",
  roadmap: "開発ロードマップ",
};

export default function RevisedArchitecture() {
  const [activeSection, setActiveSection] = useState("why");

  return (
    <div
      style={{
        fontFamily: "'Noto Sans JP', 'Hiragino Sans', sans-serif",
        background: "#0f172a",
        color: "#e2e8f0",
        minHeight: "100vh",
        padding: "24px 16px",
        maxWidth: 640,
        margin: "0 auto",
      }}
    >
      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: 28 }}>
        <h1
          style={{
            fontSize: 22,
            fontWeight: 800,
            background: "linear-gradient(135deg, #06c755, #0ea5e9)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            margin: "0 0 6px",
          }}
        >
          構成プラン（改訂版）
        </h1>
        <p style={{ color: "#94a3b8", fontSize: 13, margin: 0 }}>
          FastAPI + LINE Bot + Gemini API
        </p>
      </div>

      {/* Navigation */}
      <div
        style={{
          display: "flex",
          gap: 4,
          marginBottom: 20,
          overflowX: "auto",
          paddingBottom: 4,
        }}
      >
        {sections.map((s) => (
          <button
            key={s}
            onClick={() => setActiveSection(s)}
            style={{
              padding: "8px 12px",
              borderRadius: 8,
              border:
                activeSection === s
                  ? "1px solid #06c755"
                  : "1px solid #1e293b",
              background:
                activeSection === s
                  ? "rgba(6, 199, 85, 0.12)"
                  : "rgba(30, 41, 59, 0.4)",
              color: activeSection === s ? "#06c755" : "#64748b",
              cursor: "pointer",
              fontSize: 11,
              fontWeight: 700,
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}
          >
            {sectionLabels[s]}
          </button>
        ))}
      </div>

      {/* WHY Section */}
      {activeSection === "why" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Comparison Table */}
          <Card title="🔄 構成比較：Next.js vs FastAPI + LINE">
            <CompareRow
              label="フロントエンド"
              before="Next.js（自分でUI作成）"
              after="LINE（UIはLINEが提供）"
              verdict="開発量が激減"
            />
            <CompareRow
              label="バックエンド"
              before="Next.js API Routes"
              after="Python FastAPI"
              verdict="Pythonの方がAI系ライブラリ豊富"
            />
            <CompareRow
              label="認証"
              before="Supabase Auth"
              after="LINE User ID"
              verdict="認証の実装が不要"
            />
            <CompareRow
              label="通知"
              before="別途LINE連携が必要"
              after="LINE Botそのものが通知"
              verdict="追加開発なし"
            />
            <CompareRow
              label="ホスティング"
              before="Vercel（ゆめログと競合）"
              after="Railway / Render"
              verdict="ゆめログに影響なし"
            />
          </Card>

          {/* Python OCR Question */}
          <Card title="🐍 PythonのOCRライブラリについて">
            <p style={{ fontSize: 13, color: "#94a3b8", lineHeight: 1.8, margin: "0 0 12px" }}>
              Tesseract OCR（pytesseract）は確かに有名ですが、
              <strong style={{ color: "#f87171" }}>日本語の学校プリントには不向き</strong>
              です。理由は3つ：
            </p>
            <InfoItem
              color="#f87171"
              text="手書き風フォント・表・イラスト混在のプリントは認識精度が低い"
            />
            <InfoItem
              color="#f87171"
              text="OCRはテキスト抽出だけ。日付やタスクの意味理解は別途コードが必要"
            />
            <InfoItem
              color="#f87171"
              text="前処理（画像の二値化・傾き補正等）のチューニングが大変"
            />
            <div
              style={{
                marginTop: 14,
                background: "rgba(6, 199, 85, 0.08)",
                border: "1px solid rgba(6, 199, 85, 0.2)",
                borderRadius: 8,
                padding: 12,
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 700, color: "#06c755", marginBottom: 6 }}>
                ✅ Gemini Flash API なら一石二鳥
              </div>
              <p style={{ fontSize: 12, color: "#86efac", lineHeight: 1.7, margin: 0 }}>
                画像/PDFを送るだけで「テキスト抽出」と「タスク・日付の意味理解」を
                <strong>1回のAPI呼び出し</strong>で同時にやってくれます。
                しかも無料枠があります。
              </p>
            </div>

            {/* Analogy */}
            <div
              style={{
                marginTop: 14,
                background: "rgba(99, 102, 241, 0.08)",
                border: "1px solid rgba(99, 102, 241, 0.2)",
                borderRadius: 8,
                padding: 12,
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 700, color: "#a5b4fc", marginBottom: 6 }}>
                💡 たとえ話で理解
              </div>
              <p style={{ fontSize: 12, color: "#c7d2fe", lineHeight: 1.7, margin: 0 }}>
                <strong>Tesseract OCR</strong> = 「文字を読める外国人バイト」
                <br />→ 文字は読めるけど、意味は分からない。「4/15は早帰り」と読めても、それがタスクだとは気づかない。
                <br /><br />
                <strong>Gemini API</strong> = 「日本語ペラペラの秘書」
                <br />→ 読んで理解して「4/15の予定をカレンダーに入れましょうか？」まで提案してくれる。
              </p>
            </div>
          </Card>

          {/* Tech Stack */}
          <Card title="🛠️ 採用する技術スタック">
            <StackItem icon="🐍" name="Python + FastAPI" role="バックエンド・LINE Webhook処理" color="#3b82f6" />
            <StackItem icon="💬" name="LINE Messaging API" role="UI・通知・PDF受け取り" color="#06c755" />
            <StackItem icon="🧠" name="Gemini Flash API" role="PDF解析・タスク抽出（無料枠あり）" color="#fbbf24" />
            <StackItem icon="📅" name="Google Calendar API" role="予定登録（完全無料）" color="#4285f4" />
            <StackItem icon="🗄️" name="SQLite" role="データ保存（サーバー内・無料）" color="#8b5cf6" />
            <StackItem icon="🚀" name="Railway / Render" role="ホスティング（無料枠あり）" color="#f97316" />
          </Card>
        </div>
      )}

      {/* COST Section */}
      {activeSection === "cost" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <Card title="💰 月間コストシミュレーション">
            <p style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.7, margin: "0 0 14px" }}>
              想定：月20枚のプリントPDF、家族1〜2人で利用
            </p>

            <CostRow service="LINE Messaging API" cost="¥0" note="Reply APIは通数カウントされない" highlight />
            <CostRow service="Gemini Flash API" cost="¥0" note="無料枠：1分5リクエスト / 月600回で十分" highlight />
            <CostRow service="Google Calendar API" cost="¥0" note="個人利用は完全無料" highlight />
            <CostRow service="SQLite" cost="¥0" note="ファイルDB。サーバー内で完結" highlight />
            <CostRow service="Railway（ホスティング）" cost="¥0〜$5" note="月$5無料クレジットあり" />

            <div
              style={{
                marginTop: 16,
                background: "rgba(6, 199, 85, 0.1)",
                border: "1px solid rgba(6, 199, 85, 0.3)",
                borderRadius: 10,
                padding: 14,
                textAlign: "center",
              }}
            >
              <div style={{ fontSize: 22, fontWeight: 800, color: "#06c755" }}>
                月額 ¥0〜約¥750
              </div>
              <div style={{ fontSize: 11, color: "#86efac", marginTop: 4 }}>
                ほぼ無料で運用可能！
              </div>
            </div>
          </Card>

          <Card title="⚠️ ゆめログへの影響">
            <div
              style={{
                background: "rgba(56, 189, 248, 0.08)",
                border: "1px solid rgba(56, 189, 248, 0.2)",
                borderRadius: 8,
                padding: 12,
              }}
            >
              <p style={{ fontSize: 12, color: "#7dd3fc", lineHeight: 1.8, margin: 0 }}>
                <strong style={{ color: "#38bdf8" }}>影響なし</strong> — 今回の構成ではSupabaseもVercelも使いません。
                <br /><br />
                ゆめログ → Next.js + Supabase + Vercel
                <br />
                今回のBot → Python + SQLite + Railway
                <br /><br />
                完全に別のインフラなので、ゆめログの無料枠を食い合うことがありません。
              </p>
            </div>
          </Card>

          <Card title="📊 AI API料金比較（PDF1枚あたり）">
            <APICompare
              name="Gemini Flash"
              inputPrice="$0.15/100万token"
              perPdf="約¥0.3〜0.5"
              free="あり（月600回程度）"
              winner
            />
            <APICompare
              name="Claude Haiku"
              inputPrice="$0.80/100万token"
              perPdf="約¥2〜3"
              free="なし"
            />
            <APICompare
              name="Claude Sonnet"
              inputPrice="$3.00/100万token"
              perPdf="約¥8〜12"
              free="なし"
            />
            <APICompare
              name="GPT-4o mini"
              inputPrice="$0.15/100万token"
              perPdf="約¥0.3〜0.5"
              free="なし"
            />
            <p style={{ fontSize: 11, color: "#64748b", marginTop: 10 }}>
              ※ 学校プリントPDF 1枚 ≈ 画像1〜2ページ ≈ 約2,000〜4,000 token で試算
            </p>
          </Card>
        </div>
      )}

      {/* FLOW Section */}
      {activeSection === "flow" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <Card title="📱 LINE Botの操作フロー">
            <FlowStep
              num={1}
              emoji="📸"
              title="プリントを送る"
              desc="LINEでPDFやスクショを送信"
              color="#06c755"
            />
            <FlowArrow />
            <FlowStep
              num={2}
              emoji="🧠"
              title="AIが自動解析"
              desc="Gemini APIでテキスト抽出＋タスク検出"
              color="#fbbf24"
            />
            <FlowArrow />
            <FlowStep
              num={3}
              emoji="📋"
              title="結果を返信"
              desc="「4/15 早帰り」「〜4/18 植木鉢持参」"
              color="#3b82f6"
            />
            <FlowArrow />
            <FlowStep
              num={4}
              emoji="✅"
              title="カレンダー登録"
              desc="「登録する」ボタンでGoogleカレンダーへ"
              color="#4285f4"
            />
            <FlowArrow />
            <FlowStep
              num={5}
              emoji="🔔"
              title="リマインド"
              desc="前日にLINEで自動通知"
              color="#f97316"
            />
          </Card>

          <Card title="🔍 検索機能">
            <div
              style={{
                background: "rgba(30, 41, 59, 0.6)",
                borderRadius: 8,
                padding: 14,
              }}
            >
              <div style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.8 }}>
                <strong style={{ color: "#e2e8f0" }}>LINEで「運動会」と送信</strong>
                <br />
                → 過去のプリントを全文検索
                <br />
                → 「5/25 春季運動会のお知らせ（5/10配信）」
                <br />
                → タップでプリント画像も表示
              </div>
            </div>
          </Card>

          <Card title="📅 TimeTree連携">
            <div
              style={{
                background: "rgba(251, 191, 36, 0.08)",
                border: "1px solid rgba(251, 191, 36, 0.2)",
                borderRadius: 8,
                padding: 12,
              }}
            >
              <p style={{ fontSize: 12, color: "#fde68a", lineHeight: 1.8, margin: 0 }}>
                TimeTree APIは終了済みですが、間接連携が可能です：
                <br /><br />
                <strong style={{ color: "#fbbf24" }}>
                  Googleカレンダー → iPhone標準カレンダー同期 → TimeTreeインポート
                </strong>
                <br /><br />
                iPhone設定で一度Googleアカウントを同期すれば、
                あとは自動で反映されます。
              </p>
            </div>
          </Card>
        </div>
      )}

      {/* PDF Section */}
      {activeSection === "pdf" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <Card title="📄 PDF取り込み方法の選択肢">
            <PDFMethod
              num={1}
              title="LINEに直接送信 ← おすすめ"
              desc="マチコミでPDFを開く → 共有 → LINEで送信。最も手軽。画像（スクショ）でもOK。"
              effort="手間：★☆☆"
              color="#06c755"
              recommended
            />
            <PDFMethod
              num={2}
              title="メール自動転送"
              desc="マチコミの通知メールをGmailで受信 → フィルタで自動転送 → サーバーが自動処理。ただし添付PDFがない場合も。"
              effort="手間：★★☆（初期設定のみ）"
              color="#3b82f6"
            />
            <PDFMethod
              num={3}
              title="iPhone ショートカット自動化"
              desc="マチコミアプリの共有メニュー → iOSショートカット → LINE Botへ自動送信。やや上級者向け。"
              effort="手間：★★★（設定が複雑）"
              color="#8b5cf6"
            />
          </Card>

          <Card title="💡 おすすめの運用フロー">
            <div
              style={{
                background: "rgba(6, 199, 85, 0.08)",
                borderRadius: 8,
                padding: 14,
              }}
            >
              <ol style={{ margin: 0, paddingLeft: 20, fontSize: 13, color: "#94a3b8", lineHeight: 2 }}>
                <li>マチコミで通知が来る</li>
                <li>PDFを開いて<strong style={{ color: "#06c755" }}>スクショを撮る</strong>（またはPDF共有）</li>
                <li>LINE Botに<strong style={{ color: "#06c755" }}>画像を送るだけ</strong></li>
                <li>→ AIが自動で解析して予定を提案</li>
                <li>→ 「登録」をタップしてカレンダーに追加</li>
              </ol>
            </div>
            <p style={{ fontSize: 11, color: "#64748b", marginTop: 10, lineHeight: 1.7 }}>
              ※ Gemini APIは画像もPDFも両方読めるので、
              スクショでも全く問題ありません。むしろスクショの方が手軽です。
            </p>
          </Card>
        </div>
      )}

      {/* ROADMAP Section */}
      {activeSection === "roadmap" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <Card title="🗓️ 開発ステップ">
            <RoadmapPhase
              phase="Step 1"
              title="LINE Bot の骨格"
              time="1〜2日"
              items={[
                "LINE公式アカウント作成・Webhook設定",
                "FastAPIでメッセージ受信→返信",
                "Railway / Render にデプロイ",
              ]}
              color="#06c755"
            />
            <RoadmapPhase
              phase="Step 2"
              title="PDF解析機能"
              time="2〜3日"
              items={[
                "LINEから受け取ったPDF/画像をGemini APIへ送信",
                "タスク・日付をJSON形式で抽出",
                "SQLiteに保存・解析結果をLINEに返信",
              ]}
              color="#fbbf24"
            />
            <RoadmapPhase
              phase="Step 3"
              title="カレンダー連携"
              time="1〜2日"
              items={[
                "Googleカレンダー API連携",
                "LINEボタンで「登録する」→ カレンダーに追加",
                "TimeTree間接連携の設定ガイド作成",
              ]}
              color="#4285f4"
            />
            <RoadmapPhase
              phase="Step 4"
              title="リマインド＆検索"
              time="2〜3日"
              items={[
                "前日リマインド通知（定期実行）",
                "LINEでキーワード検索（過去プリント全文検索）",
                "Rich Menuでメニュー操作",
              ]}
              color="#f97316"
            />
          </Card>

          <Card title="📐 プロジェクト構成（ファイル構成イメージ）">
            <pre
              style={{
                fontSize: 11,
                color: "#94a3b8",
                background: "rgba(15, 23, 42, 0.8)",
                borderRadius: 8,
                padding: 14,
                margin: 0,
                overflowX: "auto",
                lineHeight: 1.7,
              }}
            >
{`school-print-bot/
├── main.py           # FastAPI エントリポイント
├── line_handler.py   # LINE Webhook 処理
├── gemini_client.py  # Gemini API 呼び出し
├── calendar_client.py# Google Calendar 連携
├── database.py       # SQLite 操作
├── scheduler.py      # リマインド定期実行
├── models.py         # データモデル定義
├── requirements.txt
└── .env              # APIキー管理`}
            </pre>
          </Card>
        </div>
      )}
    </div>
  );
}

// ─── Sub-components ───

function Card({ title, children }) {
  return (
    <div
      style={{
        background: "rgba(30, 41, 59, 0.5)",
        border: "1px solid #1e293b",
        borderRadius: 12,
        padding: 16,
      }}
    >
      <div
        style={{
          fontSize: 14,
          fontWeight: 700,
          color: "#f8fafc",
          marginBottom: 14,
          paddingBottom: 10,
          borderBottom: "1px solid #1e293b",
        }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}

function CompareRow({ label, before, after, verdict }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600, marginBottom: 4 }}>
        {label}
      </div>
      <div style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 12 }}>
        <div
          style={{
            flex: 1,
            background: "rgba(239, 68, 68, 0.08)",
            border: "1px solid rgba(239, 68, 68, 0.15)",
            borderRadius: 6,
            padding: "6px 8px",
            color: "#fca5a5",
          }}
        >
          ✕ {before}
        </div>
        <span style={{ color: "#64748b" }}>→</span>
        <div
          style={{
            flex: 1,
            background: "rgba(6, 199, 85, 0.08)",
            border: "1px solid rgba(6, 199, 85, 0.15)",
            borderRadius: 6,
            padding: "6px 8px",
            color: "#86efac",
          }}
        >
          ✓ {after}
        </div>
      </div>
      <div style={{ fontSize: 10, color: "#06c755", marginTop: 3, fontWeight: 600 }}>
        → {verdict}
      </div>
    </div>
  );
}

function InfoItem({ color, text }) {
  return (
    <div style={{ display: "flex", gap: 8, marginBottom: 6, fontSize: 12, color: "#cbd5e1", lineHeight: 1.6 }}>
      <div style={{ width: 6, height: 6, borderRadius: "50%", background: color, flexShrink: 0, marginTop: 7 }} />
      {text}
    </div>
  );
}

function StackItem({ icon, name, role, color }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "10px 0",
        borderBottom: "1px solid #1e293b22",
      }}
    >
      <div style={{ fontSize: 18, width: 32, textAlign: "center" }}>{icon}</div>
      <div>
        <div style={{ fontSize: 13, fontWeight: 700, color }}>{name}</div>
        <div style={{ fontSize: 11, color: "#94a3b8" }}>{role}</div>
      </div>
    </div>
  );
}

function CostRow({ service, cost, note, highlight }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "10px 0",
        borderBottom: "1px solid #1e293b33",
      }}
    >
      <div>
        <div style={{ fontSize: 13, color: "#e2e8f0", fontWeight: 600 }}>{service}</div>
        <div style={{ fontSize: 10, color: "#64748b" }}>{note}</div>
      </div>
      <div
        style={{
          fontSize: 14,
          fontWeight: 800,
          color: highlight ? "#06c755" : "#fbbf24",
        }}
      >
        {cost}
      </div>
    </div>
  );
}

function APICompare({ name, inputPrice, perPdf, free, winner }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "10px 0",
        borderBottom: "1px solid #1e293b33",
        background: winner ? "rgba(6, 199, 85, 0.05)" : "transparent",
        borderRadius: winner ? 6 : 0,
        paddingLeft: winner ? 8 : 0,
        paddingRight: winner ? 8 : 0,
      }}
    >
      <div>
        <div style={{ fontSize: 13, color: winner ? "#06c755" : "#e2e8f0", fontWeight: 700 }}>
          {winner && "⭐ "}{name}
        </div>
        <div style={{ fontSize: 10, color: "#64748b" }}>{inputPrice}</div>
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: winner ? "#06c755" : "#e2e8f0" }}>
          {perPdf}/枚
        </div>
        <div style={{ fontSize: 10, color: free === "あり" ? "#86efac" : "#f87171" }}>
          無料枠: {free}
        </div>
      </div>
    </div>
  );
}

function FlowStep({ num, emoji, title, desc, color }) {
  return (
    <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
      <div
        style={{
          width: 44,
          height: 44,
          borderRadius: 10,
          background: color + "18",
          border: `1px solid ${color}40`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 22,
          flexShrink: 0,
          position: "relative",
        }}
      >
        {emoji}
        <div
          style={{
            position: "absolute",
            top: -4,
            right: -4,
            width: 16,
            height: 16,
            borderRadius: "50%",
            background: color,
            fontSize: 9,
            fontWeight: 800,
            color: "#0f172a",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {num}
        </div>
      </div>
      <div>
        <div style={{ fontSize: 13, fontWeight: 700, color }}>{title}</div>
        <div style={{ fontSize: 11, color: "#94a3b8" }}>{desc}</div>
      </div>
    </div>
  );
}

function FlowArrow() {
  return (
    <div style={{ display: "flex", justifyContent: "center", padding: "4px 0" }}>
      <div style={{ width: 2, height: 16, background: "#334155" }} />
    </div>
  );
}

function PDFMethod({ num, title, desc, effort, color, recommended }) {
  return (
    <div
      style={{
        background: recommended ? `${color}0d` : "rgba(30, 41, 59, 0.4)",
        border: `1px solid ${recommended ? color + "40" : "#1e293b"}`,
        borderRadius: 10,
        padding: 14,
        marginBottom: 10,
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 700, color, marginBottom: 4 }}>
        方法{num}. {title}
      </div>
      <div style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.7, marginBottom: 6 }}>
        {desc}
      </div>
      <div style={{ fontSize: 10, color: "#64748b" }}>{effort}</div>
    </div>
  );
}

function RoadmapPhase({ phase, title, time, items, color }) {
  return (
    <div
      style={{
        borderLeft: `3px solid ${color}`,
        paddingLeft: 14,
        marginBottom: 18,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
        <div>
          <span style={{ fontSize: 10, color, fontWeight: 700 }}>{phase}</span>
          <span style={{ fontSize: 14, fontWeight: 700, color: "#f8fafc", marginLeft: 8 }}>{title}</span>
        </div>
        <span
          style={{
            fontSize: 10,
            color,
            background: color + "18",
            padding: "3px 8px",
            borderRadius: 10,
            fontWeight: 600,
          }}
        >
          {time}
        </span>
      </div>
      {items.map((item, i) => (
        <div key={i} style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.7, display: "flex", gap: 8 }}>
          <span style={{ color: color + "99" }}>•</span> {item}
        </div>
      ))}
    </div>
  );
}
