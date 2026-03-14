import { useState } from "react";

const services = [
  {
    id: "cloudflare",
    name: "Cloudflare Workers",
    icon: "☁️",
    color: "#f6821f",
    tagline: "エッジ × サーバーレス",
    free: {
      requests: "10万リクエスト/日",
      cpu: "10ms CPU時間/リクエスト",
      db: "D1: 500MB × 10DB",
      kv: "KV: 10万読取/日",
      cron: "Cron Triggers: 5個",
      cost: "¥0",
    },
    pros: [
      "無料枠が圧倒的に太い（10万req/日）",
      "世界330拠点。日本からのレイテンシが極めて低い",
      "D1（SQLite互換DB）が無料で使える",
      "Cron Triggers（定期実行）も無料枠内",
      "スリープしない（コールドスタートが超高速）",
    ],
    cons: [
      "Python対応はまだオープンベータ（安定性リスク）",
      "使えるPythonパッケージに制限あり",
      "CPU時間10ms/リクエストの制限が厳しい場合がある",
      "従来のPython開発と書き方が少し異なる",
      "ファイルシステムがない（画像保存にはR2が必要）",
    ],
    fit: 75,
  },
  {
    id: "railway",
    name: "Railway",
    icon: "🚂",
    color: "#a855f7",
    tagline: "コンテナ × 常時稼働",
    free: {
      requests: "制限なし",
      cpu: "制限なし",
      db: "PostgreSQL: 利用可能",
      kv: "Redis: 利用可能",
      cron: "自前で実装（APScheduler等）",
      cost: "月$5クレジット",
    },
    pros: [
      "普通のPython/FastAPIがそのまま動く",
      "月$5の無料クレジットで個人利用は十分",
      "PostgreSQL/Redisも$5内で使える",
      "Dockerコンテナなので何でもインストール可能",
      "デプロイがGit pushだけで超簡単",
    ],
    cons: [
      "無料クレジットは$5/月（超過で停止）",
      "アイドル時もリソース消費する",
      "日本リージョンなし（US-West中心）",
      "無料枠で常時稼働はギリギリ",
      "スケーリングは手動",
    ],
    fit: 85,
  },
  {
    id: "render",
    name: "Render",
    icon: "🎨",
    color: "#46e3b7",
    tagline: "PaaS × シンプル",
    free: {
      requests: "制限なし",
      cpu: "0.1 CPU / 512MB RAM",
      db: "PostgreSQL: 90日間無料",
      kv: "Redis: 有料のみ",
      cron: "Cron Jobs: 有料のみ",
      cost: "¥0（Web Service無料枠）",
    },
    pros: [
      "完全無料のWeb Service枠がある",
      "FastAPIが普通にそのまま動く",
      "ダッシュボードが見やすい",
      "Git連携でのデプロイが簡単",
      "PostgreSQLの無料枠あり（90日限定）",
    ],
    cons: [
      "15分無アクセスでスリープ（復帰に30〜60秒）",
      "→ LINE Webhookのタイムアウトに引っかかる可能性",
      "無料DBは90日で削除される",
      "Cron Jobsは有料プランのみ（リマインドに必須）",
      "日本リージョンなし",
    ],
    fit: 55,
  },
];

export default function HostingComparison() {
  const [selected, setSelected] = useState("railway");
  const [showVerdict, setShowVerdict] = useState(false);

  const current = services.find((s) => s.id === selected);

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
      <div style={{ textAlign: "center", marginBottom: 24 }}>
        <h1
          style={{
            fontSize: 20,
            fontWeight: 800,
            color: "#f8fafc",
            margin: "0 0 6px",
          }}
        >
          ホスティングサービス比較
        </h1>
        <p style={{ color: "#64748b", fontSize: 12, margin: 0 }}>
          LINE Bot (Python FastAPI) をホストする先の選定
        </p>
      </div>

      {/* Service Tabs */}
      <div style={{ display: "flex", gap: 6, marginBottom: 20 }}>
        {services.map((s) => (
          <button
            key={s.id}
            onClick={() => setSelected(s.id)}
            style={{
              flex: 1,
              padding: "10px 6px",
              borderRadius: 10,
              border: `1.5px solid ${selected === s.id ? s.color : "#1e293b"}`,
              background: selected === s.id ? s.color + "15" : "rgba(30,41,59,0.4)",
              color: selected === s.id ? s.color : "#64748b",
              cursor: "pointer",
              fontSize: 11,
              fontWeight: 700,
              textAlign: "center",
              transition: "all 0.2s",
            }}
          >
            <div style={{ fontSize: 20, marginBottom: 2 }}>{s.icon}</div>
            {s.name}
          </button>
        ))}
      </div>

      {/* Selected Service Detail */}
      {current && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Header */}
          <div
            style={{
              background: current.color + "12",
              border: `1px solid ${current.color}30`,
              borderRadius: 12,
              padding: 16,
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: 28 }}>{current.icon}</div>
            <div style={{ fontSize: 18, fontWeight: 800, color: current.color }}>
              {current.name}
            </div>
            <div style={{ fontSize: 12, color: "#94a3b8" }}>{current.tagline}</div>

            {/* Fit meter */}
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 10, color: "#64748b", marginBottom: 4 }}>
                今回の用途との相性
              </div>
              <div
                style={{
                  height: 8,
                  background: "#1e293b",
                  borderRadius: 4,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    height: "100%",
                    width: `${current.fit}%`,
                    background: `linear-gradient(90deg, ${current.color}88, ${current.color})`,
                    borderRadius: 4,
                    transition: "width 0.5s ease",
                  }}
                />
              </div>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 800,
                  color: current.color,
                  marginTop: 4,
                }}
              >
                {current.fit}%
              </div>
            </div>
          </div>

          {/* Free Tier */}
          <Card title="🆓 無料枠の内容">
            {Object.entries(current.free).map(([key, val]) => (
              <div
                key={key}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  padding: "7px 0",
                  borderBottom: "1px solid #1e293b22",
                  fontSize: 12,
                }}
              >
                <span style={{ color: "#94a3b8" }}>
                  {key === "requests" && "リクエスト"}
                  {key === "cpu" && "CPU/メモリ"}
                  {key === "db" && "データベース"}
                  {key === "kv" && "KVストア"}
                  {key === "cron" && "定期実行"}
                  {key === "cost" && "月額"}
                </span>
                <span
                  style={{
                    color: val.includes("¥0") || val.includes("無料")
                      ? "#06c755"
                      : "#e2e8f0",
                    fontWeight: 600,
                  }}
                >
                  {val}
                </span>
              </div>
            ))}
          </Card>

          {/* Pros */}
          <Card title="✅ メリット">
            {current.pros.map((p, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  gap: 8,
                  fontSize: 12,
                  color: "#86efac",
                  lineHeight: 1.6,
                  marginBottom: 6,
                }}
              >
                <span style={{ flexShrink: 0 }}>+</span>
                {p}
              </div>
            ))}
          </Card>

          {/* Cons */}
          <Card title="⚠️ デメリット・注意点">
            {current.cons.map((c, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  gap: 8,
                  fontSize: 12,
                  color: "#fca5a5",
                  lineHeight: 1.6,
                  marginBottom: 6,
                }}
              >
                <span style={{ flexShrink: 0 }}>−</span>
                {c}
              </div>
            ))}
          </Card>
        </div>
      )}

      {/* Verdict */}
      <div style={{ marginTop: 20 }}>
        <button
          onClick={() => setShowVerdict(!showVerdict)}
          style={{
            width: "100%",
            padding: "14px",
            borderRadius: 12,
            border: "1px solid #3b82f6",
            background: "rgba(59, 130, 246, 0.1)",
            color: "#93c5fd",
            cursor: "pointer",
            fontSize: 14,
            fontWeight: 700,
            transition: "all 0.2s",
          }}
        >
          {showVerdict ? "▼" : "▶"} 結論：どれを選ぶべき？
        </button>

        {showVerdict && (
          <div
            style={{
              marginTop: 12,
              background: "rgba(30, 41, 59, 0.6)",
              border: "1px solid #1e293b",
              borderRadius: 12,
              padding: 18,
            }}
          >
            {/* Recommendation 1 */}
            <div
              style={{
                background: "rgba(168, 85, 247, 0.1)",
                border: "1px solid rgba(168, 85, 247, 0.3)",
                borderRadius: 10,
                padding: 14,
                marginBottom: 14,
              }}
            >
              <div style={{ fontSize: 14, fontWeight: 800, color: "#a855f7", marginBottom: 8 }}>
                🏆 おすすめ：Railway
              </div>
              <div style={{ fontSize: 12, color: "#c4b5fd", lineHeight: 1.8 }}>
                <strong>普通のPython/FastAPIがそのまま動く</strong>ことが最大の強み。
                LINE Botのようなリアルタイム処理では、スリープしない常時稼働が重要です。
                月$5の無料クレジットで今回の用途は十分まかなえます。
                初めてのBot開発では「動かないのがバグなのか環境の制限なのか」の切り分けが大変なので、
                制約が少ない環境で始めるのが吉。
              </div>
            </div>

            {/* When Cloudflare */}
            <div
              style={{
                background: "rgba(246, 130, 31, 0.08)",
                border: "1px solid rgba(246, 130, 31, 0.2)",
                borderRadius: 10,
                padding: 14,
                marginBottom: 14,
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 700, color: "#f6821f", marginBottom: 6 }}>
                ☁️ Cloudflare Workers が向くケース
              </div>
              <div style={{ fontSize: 12, color: "#fdba74", lineHeight: 1.8 }}>
                MVPが完成して安定運用フェーズに入ったら、
                Cloudflareへの移行を検討する価値があります。
                無料枠が圧倒的に大きく、D1（DB）もCron Triggersも無料。
                ただしPython対応がベータなので、
                今の段階では「第2の選択肢」として覚えておくのがベスト。
              </div>
            </div>

            {/* Avoid Render */}
            <div
              style={{
                background: "rgba(239, 68, 68, 0.06)",
                border: "1px solid rgba(239, 68, 68, 0.15)",
                borderRadius: 10,
                padding: 14,
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 700, color: "#f87171", marginBottom: 6 }}>
                ❌ Render は今回は避けたほうがいい
              </div>
              <div style={{ fontSize: 12, color: "#fca5a5", lineHeight: 1.8 }}>
                無料枠だと15分でスリープし、復帰に30〜60秒かかります。
                LINEのWebhookは応答が遅いとタイムアウトになるため、
                LINE Bot には致命的な弱点です。
                また、Cron Jobsが有料なのでリマインド機能も実装できません。
              </div>
            </div>

            {/* Analogy */}
            <div
              style={{
                marginTop: 16,
                background: "rgba(99, 102, 241, 0.08)",
                border: "1px solid rgba(99, 102, 241, 0.2)",
                borderRadius: 10,
                padding: 14,
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 700, color: "#a5b4fc", marginBottom: 8 }}>
                💡 たとえ話で整理
              </div>
              <div style={{ fontSize: 12, color: "#c7d2fe", lineHeight: 1.9 }}>
                <strong style={{ color: "#f6821f" }}>Cloudflare Workers</strong>
                 = 世界中のコンビニ
                <br />
                どこでも素早く対応してくれるが、できる作業に制限がある（弁当は温められるけど調理はできない）
                <br /><br />
                <strong style={{ color: "#a855f7" }}>Railway</strong>
                 = 自分のキッチン付きアパート
                <br />
                好きな道具を持ち込んで何でも作れる。家賃が安い（月$5）
                <br /><br />
                <strong style={{ color: "#46e3b7" }}>Render</strong>
                 = 居眠りする受付のいるオフィス
                <br />
                無料だけど、15分放っておくと寝てしまう。起こすのに1分かかる
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

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
          fontSize: 13,
          fontWeight: 700,
          color: "#f8fafc",
          marginBottom: 12,
          paddingBottom: 8,
          borderBottom: "1px solid #1e293b",
        }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}
