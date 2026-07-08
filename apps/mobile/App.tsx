import { useCallback, useRef, useState } from "react";
import {
  ActivityIndicator,
  LogBox,
  Pressable,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  View,
} from "react-native";
import EventSource from "react-native-sse";

const AGENT_URL = "https://agent.16-59-185-192.nip.io";

// suppress dev warning toasts (e.g. SafeAreaView deprecation) for clean demo recordings
LogBox.ignoreAllLogs();

type Trace = { node: string; kind: string; message: string };
type Causation = Record<string, string>;
type WriteResult = Record<string, { status: string; result?: string }>;

const C = {
  bg: "#0c0d10",
  surface: "#15161b",
  border: "#24262e",
  fg: "#e8e9ec",
  muted: "#a7abb4",
  subtle: "#6b6f78",
  accent: "#8ab0f5",
  accentSoft: "#16233d",
  degraded: "#e6ae5a",
  degradedSoft: "#2a2114",
  healthy: "#6ee7a8",
};

const KIND_COLOR: Record<string, string> = {
  alarm: C.degraded,
  tool_call: C.accent,
  tool_result: C.healthy,
  result: C.muted,
  thinking: C.subtle,
  info: C.subtle,
};

export default function App() {
  const [status, setStatus] = useState<"idle" | "running" | "awaiting" | "done">("idle");
  const [trace, setTrace] = useState<Trace[]>([]);
  const [finding, setFinding] = useState<{ thread_id: string; causation: Causation } | null>(null);
  const [result, setResult] = useState<WriteResult | null>(null);
  const esRef = useRef<EventSource<"trace" | "awaiting_approval"> | null>(null);

  const run = useCallback(() => {
    esRef.current?.close();
    setStatus("running");
    setTrace([]);
    setFinding(null);
    setResult(null);
    const es = new EventSource<"trace" | "awaiting_approval">(`${AGENT_URL}/api/stream?scenario=harmful`);
    esRef.current = es;
    es.addEventListener("trace", (e: { data?: string | null }) => {
      if (!e.data) return;
      setTrace((t) => [...t, JSON.parse(e.data as string) as Trace]);
    });
    es.addEventListener("awaiting_approval", (e: { data?: string | null }) => {
      if (!e.data) return;
      setFinding(JSON.parse(e.data as string) as { thread_id: string; causation: Causation });
      setStatus("awaiting");
      es.close();
    });
    es.addEventListener("error", () => {
      es.close();
      setStatus((s) => (s === "running" ? "done" : s));
    });
  }, []);

  const approve = useCallback(async () => {
    if (!finding) return;
    setStatus("running");
    const r = await fetch(`${AGENT_URL}/api/approve?thread_id=${finding.thread_id}`, {
      method: "POST",
    });
    const data = (await r.json()) as { trace?: Trace[]; writeback?: { result: WriteResult } };
    setTrace((t) => [...t, ...(data.trace ?? [])]);
    setResult(data.writeback?.result ?? null);
    setStatus("done");
  }, [finding]);

  const busy = status === "running";
  const c = finding?.causation;

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar barStyle="light-content" backgroundColor={C.bg} />
      <View style={styles.header}>
        <View style={styles.dotRow}>
          <View style={[styles.dot, { backgroundColor: status === "idle" ? C.subtle : C.degraded }]} />
          <Text style={styles.brand}>SILENT-DRIFT SENTINEL</Text>
        </View>
        <Text style={styles.sub}>on-call / online_shoppers_purchase_intent</Text>
      </View>

      <ScrollView style={styles.body} contentContainerStyle={{ paddingBottom: 24 }}>
        {status === "idle" && (
          <Text style={styles.intro}>
            You are on call for a production model. Run the agent to detect the drift, walk DataHub
            lineage to the upstream cause, and approve the write-back from your phone.
          </Text>
        )}

        {finding && (
          <View style={styles.card}>
            <View style={styles.cardHeadRow}>
              <Text style={styles.cardTitle}>purchase_intent</Text>
              <View style={styles.badge}>
                <Text style={styles.badgeText}>drift-degraded</Text>
              </View>
            </View>
            <Row k="feature" v={c?.drifted_feature} />
            <Row k="change" v={c?.change_type} />
            <Row k="impact" v={c?.drift_metric} />
            <Row k="owner" v={(c?.table_owner || "").split(":").pop()} />
          </View>
        )}

        {result && (
          <View style={[styles.card, { borderColor: C.healthy + "55" }]}>
            <Text style={styles.written}>Written back to DataHub</Text>
            {Object.entries(result).map(([k, v]) => (
              <View key={k} style={styles.resRow}>
                <Text style={styles.resKey}>{k}</Text>
                <Text style={[styles.resVal, { color: v.status === "done" ? C.healthy : C.degraded }]}>
                  {v.status}
                </Text>
              </View>
            ))}
          </View>
        )}

        <Text style={styles.section}>AGENT REASONING</Text>
        {trace.map((t, i) => (
          <View key={i} style={styles.traceItem}>
            <Text style={styles.traceNode}>
              {t.node.toUpperCase()} <Text style={{ color: KIND_COLOR[t.kind] ?? C.subtle }}>{t.kind}</Text>
            </Text>
            <Text style={[styles.traceMsg, t.kind === "alarm" && { color: C.degraded }]}>{t.message}</Text>
          </View>
        ))}
        {busy && <ActivityIndicator color={C.accent} style={{ marginTop: 16 }} />}
      </ScrollView>

      <View style={styles.footer}>
        {status === "awaiting" ? (
          <Pressable style={[styles.btn, styles.btnApprove]} onPress={approve}>
            <Text style={styles.btnApproveText}>Approve write-back</Text>
          </Pressable>
        ) : (
          <Pressable style={[styles.btn, styles.btnRun, busy && { opacity: 0.5 }]} disabled={busy} onPress={run}>
            <Text style={styles.btnRunText}>
              {busy ? "Running..." : status === "done" ? "Run again" : "Run diagnosis"}
            </Text>
          </Pressable>
        )}
      </View>
    </SafeAreaView>
  );
}

function Row({ k, v }: { k: string; v?: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowKey}>{k}</Text>
      <Text style={styles.rowVal}>{v ?? "-"}</Text>
    </View>
  );
}

const mono = "Courier";
const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: C.bg },
  header: { paddingHorizontal: 18, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: C.border },
  dotRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  brand: { color: C.muted, fontFamily: mono, fontSize: 12, letterSpacing: 2 },
  sub: { color: C.subtle, fontFamily: mono, fontSize: 11, marginTop: 4 },
  body: { flex: 1, paddingHorizontal: 18 },
  intro: { color: C.muted, fontSize: 15, lineHeight: 23, marginTop: 20 },
  card: { backgroundColor: C.surface, borderColor: C.border, borderWidth: 1, borderRadius: 12, padding: 14, marginTop: 18 },
  cardHeadRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 10 },
  cardTitle: { color: C.fg, fontFamily: mono, fontSize: 15, fontWeight: "600" },
  badge: { backgroundColor: C.degradedSoft, borderColor: C.degraded + "88", borderWidth: 1, borderRadius: 999, paddingHorizontal: 8, paddingVertical: 3 },
  badgeText: { color: C.degraded, fontSize: 10, fontWeight: "600" },
  row: { flexDirection: "row", gap: 10, marginTop: 6 },
  rowKey: { color: C.subtle, fontFamily: mono, fontSize: 12, width: 62 },
  rowVal: { color: C.fg, fontFamily: mono, fontSize: 12, flex: 1 },
  written: { color: C.healthy, fontFamily: mono, fontSize: 11, letterSpacing: 1, marginBottom: 8 },
  resRow: { flexDirection: "row", justifyContent: "space-between", marginTop: 4 },
  resKey: { color: C.muted, fontFamily: mono, fontSize: 12 },
  resVal: { fontFamily: mono, fontSize: 12 },
  section: { color: C.subtle, fontFamily: mono, fontSize: 10, letterSpacing: 2, marginTop: 24, marginBottom: 6 },
  traceItem: { backgroundColor: C.surface, borderColor: C.border, borderWidth: 1, borderRadius: 8, padding: 10, marginTop: 8 },
  traceNode: { color: C.subtle, fontFamily: mono, fontSize: 9, letterSpacing: 1 },
  traceMsg: { color: C.fg, fontSize: 13, lineHeight: 19, marginTop: 4 },
  footer: { paddingHorizontal: 18, paddingTop: 10, paddingBottom: 6, borderTopWidth: 1, borderTopColor: C.border },
  btn: { borderRadius: 10, paddingVertical: 14, alignItems: "center" },
  btnRun: { backgroundColor: C.accentSoft, borderColor: C.accent + "66", borderWidth: 1 },
  btnRunText: { color: C.accent, fontSize: 15, fontWeight: "600" },
  btnApprove: { backgroundColor: C.degradedSoft, borderColor: C.degraded + "88", borderWidth: 1 },
  btnApproveText: { color: C.degraded, fontSize: 15, fontWeight: "600" },
});
