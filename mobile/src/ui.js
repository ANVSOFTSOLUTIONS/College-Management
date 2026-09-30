import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { errorText } from "./api";

export const colors = {
  brand: "#059669",
  brandDark: "#047857",
  brandSoft: "#ecfdf5",
  text: "#0f172a",
  muted: "#64748b",
  border: "#e2e8f0",
  bg: "#f8fafc",
  danger: "#e11d48",
  dangerSoft: "#fff1f2",
  warn: "#b45309",
  warnSoft: "#fffbeb",
  white: "#ffffff",
};

export function rupees(value) {
  return `₹${Number(value || 0).toLocaleString("en-IN")}`;
}

export function today() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** A pull-to-refresh scroll page with a title. */
export function Screen({ title, subtitle, refreshing = false, onRefresh, children, right }) {
  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.screenContent}
      keyboardShouldPersistTaps="handled"
      refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={[colors.brand]} /> : undefined}
    >
      {title ? (
        <View style={styles.titleRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.title}>{title}</Text>
            {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
          </View>
          {right}
        </View>
      ) : null}
      {children}
    </ScrollView>
  );
}

export function Card({ children, style, onPress }) {
  const body = <View style={[styles.card, style]}>{children}</View>;
  return onPress ? (
    <Pressable onPress={onPress} style={({ pressed }) => pressed && { opacity: 0.7 }}>
      {body}
    </Pressable>
  ) : (
    body
  );
}

export function H({ children }) {
  return <Text style={styles.h}>{children}</Text>;
}

export function Muted({ children, style }) {
  return <Text style={[styles.muted, style]}>{children}</Text>;
}

export function Button({ title, onPress, kind = "primary", disabled, loading, small, style }) {
  const palette = {
    primary: { bg: colors.brand, fg: colors.white },
    secondary: { bg: colors.white, fg: colors.text, border: colors.border },
    danger: { bg: colors.white, fg: colors.danger, border: "#fecdd3" },
  }[kind];
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.button,
        small && styles.buttonSmall,
        { backgroundColor: palette.bg, borderColor: palette.border ?? palette.bg, opacity: disabled ? 0.5 : pressed ? 0.8 : 1 },
        style,
      ]}
    >
      {loading ? <ActivityIndicator color={palette.fg} /> : <Text style={[styles.buttonText, small && { fontSize: 13 }, { color: palette.fg }]}>{title}</Text>}
    </Pressable>
  );
}

export function Input({ label, style, ...props }) {
  return (
    <View style={{ marginBottom: 12 }}>
      {label ? <Text style={styles.label}>{label}</Text> : null}
      <TextInput placeholderTextColor="#94a3b8" style={[styles.input, style]} {...props} />
    </View>
  );
}

export function Chips({ options, value, onChange }) {
  return (
    <View style={styles.chips}>
      {options.map((o) => {
        const active = o.value === value;
        return (
          <Pressable key={o.value} onPress={() => onChange(o.value)} style={[styles.chip, active && styles.chipActive]}>
            <Text style={[styles.chipText, active && { color: colors.white }]}>{o.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function Badge({ text, tone = "slate" }) {
  const tones = {
    slate: ["#f1f5f9", "#475569"],
    green: [colors.brandSoft, colors.brandDark],
    red: [colors.dangerSoft, colors.danger],
    amber: [colors.warnSoft, colors.warn],
    blue: ["#eff6ff", "#1d4ed8"],
  }[tone];
  return (
    <View style={[styles.badge, { backgroundColor: tones[0] }]}>
      <Text style={[styles.badgeText, { color: tones[1] }]}>{text}</Text>
    </View>
  );
}

export function Stat({ label, value, tone }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={[styles.statValue, tone === "red" && { color: colors.danger }, tone === "green" && { color: colors.brandDark }]}>{value}</Text>
    </View>
  );
}

export function Message({ text, error }) {
  if (!text && !error) return null;
  return (
    <View style={[styles.message, error ? { backgroundColor: colors.dangerSoft } : { backgroundColor: colors.brandSoft }]}>
      <Text style={{ color: error ? colors.danger : colors.brandDark, fontWeight: "600" }}>{error ? errorText(error, String(error)) : text}</Text>
    </View>
  );
}

/** Loading spinner, error with retry, or the children. */
export function Loader({ loading, error, onRetry, children, empty }) {
  if (loading) return <ActivityIndicator style={{ marginTop: 32 }} color={colors.brand} />;
  if (error)
    return (
      <Card style={{ alignItems: "center" }}>
        <Text style={{ color: colors.danger, fontWeight: "600", textAlign: "center" }}>
          {error.code === "module_disabled" ? "Your college hasn't switched this on." : errorText(error)}
        </Text>
        {onRetry ? <Button title="Try again" kind="secondary" small onPress={onRetry} style={{ marginTop: 12 }} /> : null}
      </Card>
    );
  if (empty) return <Muted style={{ textAlign: "center", marginTop: 24 }}>{empty}</Muted>;
  return children;
}

export function Row({ children, style }) {
  return <View style={[{ flexDirection: "row", alignItems: "center", gap: 8 }, style]}>{children}</View>;
}

export const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  screenContent: { padding: 16, paddingBottom: 32, gap: 12 },
  titleRow: { flexDirection: "row", alignItems: "flex-end", marginBottom: 4 },
  title: { fontSize: 24, fontWeight: "800", color: colors.text },
  subtitle: { color: colors.muted, marginTop: 2 },
  card: { backgroundColor: colors.white, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 14 },
  h: { fontSize: 16, fontWeight: "700", color: colors.text },
  muted: { color: colors.muted, fontSize: 13 },
  label: { fontSize: 13, fontWeight: "600", color: "#334155", marginBottom: 4 },
  input: { borderWidth: 1, borderColor: "#cbd5e1", borderRadius: 12, paddingHorizontal: 12, paddingVertical: 10, fontSize: 15, backgroundColor: colors.white, color: colors.text },
  button: { borderRadius: 12, paddingVertical: 12, paddingHorizontal: 16, alignItems: "center", borderWidth: 1 },
  buttonSmall: { paddingVertical: 7, paddingHorizontal: 12, borderRadius: 10 },
  buttonText: { fontWeight: "700", fontSize: 15 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: { borderRadius: 999, borderWidth: 1, borderColor: "#cbd5e1", paddingHorizontal: 12, paddingVertical: 6, backgroundColor: colors.white },
  chipActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  chipText: { fontSize: 13, fontWeight: "600", color: "#475569" },
  badge: { borderRadius: 999, paddingHorizontal: 8, paddingVertical: 2, alignSelf: "flex-start" },
  badgeText: { fontSize: 12, fontWeight: "700", textTransform: "capitalize" },
  stat: { flex: 1, backgroundColor: colors.white, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 12 },
  statLabel: { fontSize: 12, color: colors.muted },
  statValue: { fontSize: 20, fontWeight: "800", color: colors.text, marginTop: 2 },
  message: { borderRadius: 12, padding: 12 },
});
