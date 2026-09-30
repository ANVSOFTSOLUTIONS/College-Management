import * as SecureStore from "expo-secure-store";
import { useEffect, useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, Text, View } from "react-native";

import { api, errorText } from "../api";
import { useAuth } from "../auth";
import { Button, Chips, colors, Input, Message, Muted } from "../ui";

const CODE_KEY = "college_code";
const MODES = [
  { value: "student", label: "Student" },
  { value: "parent", label: "Parent" },
  { value: "faculty", label: "Faculty" },
];

export function LoginScreen() {
  const { login } = useAuth();
  const [mode, setMode] = useState("student");
  const [collegeCode, setCollegeCode] = useState("");
  const [roll, setRoll] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    SecureStore.getItemAsync(CODE_KEY).then((code) => code && setCollegeCode(code)).catch(() => {});
  }, []);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      if (mode === "student") {
        await SecureStore.setItemAsync(CODE_KEY, collegeCode.trim());
        await login({ college_code: collegeCode.trim(), roll_number: roll.trim(), password });
      } else if (mode === "parent") {
        await login({ phone: phone.trim(), password });
      } else {
        await login({ email: email.trim().toLowerCase(), password });
      }
    } catch (err) {
      const known = ["too_many_attempts", "school_inactive", "school_suspended", "wrong_app", "offline"];
      setError(
        known.includes(err.code)
          ? errorText(err)
          : { student: "Wrong college code, roll number or password.", parent: "Wrong mobile number or password.", faculty: "Wrong email or password." }[mode],
      );
    } finally {
      setBusy(false);
    }
  }

  const ready = password && (mode === "student" ? collegeCode.trim() && roll.trim() : mode === "parent" ? phone.trim() : email.trim());

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: colors.brandDark }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <ScrollView contentContainerStyle={{ flexGrow: 1, justifyContent: "center", padding: 20 }} keyboardShouldPersistTaps="handled">
        <View style={{ alignItems: "center", marginBottom: 24 }}>
          <Text style={{ color: "#a7f3d0", fontWeight: "700", letterSpacing: 1.5, fontSize: 12 }}>ANV COLLEGE ERP</Text>
          <Text style={{ color: colors.white, fontSize: 28, fontWeight: "800", marginTop: 4 }}>Welcome</Text>
        </View>
        <View style={{ backgroundColor: colors.white, borderRadius: 20, padding: 20 }}>
          <Chips options={MODES} value={mode} onChange={(m) => { setMode(m); setError(null); }} />
          <View style={{ height: 16 }} />
          {mode === "student" && (
            <>
              <Input label="College code" value={collegeCode} onChangeText={setCollegeCode} autoCapitalize="characters" placeholder="e.g. ANVCOL" />
              <Input label="Roll number" value={roll} onChangeText={setRoll} autoCapitalize="characters" placeholder="e.g. 24A91A0501" />
            </>
          )}
          {mode === "parent" && <Input label="Mobile number" value={phone} onChangeText={setPhone} keyboardType="phone-pad" placeholder="10-digit mobile" />}
          {mode === "faculty" && (
            <Input label="Email" value={email} onChangeText={setEmail} keyboardType="email-address" autoCapitalize="none" autoComplete="email" />
          )}
          <Input label="Password" value={password} onChangeText={setPassword} secureTextEntry onSubmitEditing={submit} />
          <Message error={error} />
          <Button title="Sign in" onPress={submit} loading={busy} disabled={!ready} style={{ marginTop: 8 }} />
          <Muted style={{ textAlign: "center", marginTop: 14 }}>
            {mode === "faculty" ? "Faculty sign in with their college email." : "Your first password comes from the college office."}
          </Muted>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

export function ChangePasswordScreen({ required }) {
  const { token, logout, markPasswordChanged } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);

  async function submit() {
    setError(null);
    if (next.length < 8) return setError("Use at least 8 characters.");
    if (next !== confirm) return setError("The new passwords don't match.");
    setBusy(true);
    try {
      await api("/auth/change-password", { method: "POST", token, body: { current_password: current, new_password: next } });
      setDone(true);
      setCurrent("");
      setNext("");
      setConfirm("");
      if (required) await markPasswordChanged();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={{ padding: 20, gap: 4 }} keyboardShouldPersistTaps="handled" style={{ backgroundColor: colors.bg }}>
      <Text style={{ fontSize: 22, fontWeight: "800", color: colors.text, marginBottom: 4 }}>{required ? "Choose your password" : "Change password"}</Text>
      {required && <Muted style={{ marginBottom: 12 }}>For your safety, replace the password the college gave you before continuing.</Muted>}
      <Input label="Current password" value={current} onChangeText={setCurrent} secureTextEntry />
      <Input label="New password (8+ characters)" value={next} onChangeText={setNext} secureTextEntry />
      <Input label="Confirm new password" value={confirm} onChangeText={setConfirm} secureTextEntry />
      <Message error={error} text={done && !required ? "Password changed." : null} />
      <Button title="Save password" onPress={submit} loading={busy} disabled={!current || !next} style={{ marginTop: 8 }} />
      {required && <Button title="Sign out" kind="secondary" onPress={logout} style={{ marginTop: 8 }} />}
    </ScrollView>
  );
}
