# Design System + Restyle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the mobile app a cream/light look — a small design system (tokens + reusable UI components) and a restyle of every screen — without changing behaviour or any test ID.

**Architecture:** `src/theme/tokens.ts` holds colours/spacing/radii/type + a `verdictColor` helper. `src/components/ui/` holds `Screen`, `Text`, `Button`, `Input`, `Card`. Every screen is rebuilt on these, keeping the exact test IDs and visible strings so the 30 existing tests stay green.

**Tech Stack:** React Native + Expo (SDK 54) + TypeScript, expo-router, Jest + RNTL. All under `mobile/`. Run from `mobile/`: `npm test`, `npm run typecheck`.

---

## File Structure (`mobile/src/`)

- `theme/tokens.ts` (new) — colours, space, radius, type, `verdictColor`.
- `components/ui/Screen.tsx`, `Text.tsx`, `Button.tsx`, `Input.tsx`, `Card.tsx` (new).
- restyle: `app/(auth)/login.tsx`, `register.tsx`, `app/(app)/index.tsx`, `history.tsx`, `settings.tsx`, `app/(app)/_layout.tsx`, `components/VerdictResult.tsx`.
- tests co-located under `__tests__/`.

**Invariant:** preserve these test IDs everywhere — `email`, `password`, `submit`, `ingredients`, `check`, `verdict`, `ingredient`, `disclaimer`, `error`, `history-row`, `delete-<id>`, `clear-all`, `empty`, `retry` — and these visible strings the tests assert: the verdict in caps (e.g. `HARAM`), `pork fat`, `Not a religious ruling.`, `No scans yet`, `sugar, lard`, and error messages.

---

## Task 1: Theme tokens

**Files:** `mobile/src/theme/tokens.ts`, `mobile/src/theme/__tests__/tokens.test.ts`

- [ ] **Step 1: Write the failing test**

Create `mobile/src/theme/__tests__/tokens.test.ts`:

```ts
import { verdictColor, colors } from "../tokens";

test("verdictColor maps each verdict and falls back", () => {
  expect(verdictColor("halal")).toBe(colors.halal);
  expect(verdictColor("haram")).toBe(colors.haram);
  expect(verdictColor("shubhah")).toBe(colors.shubhah);
  expect(verdictColor("???")).toBe(colors.text);
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd mobile && npm test -- tokens`
Expected: FAIL — `Cannot find module '../tokens'`.

- [ ] **Step 3: Create the tokens**

Create `mobile/src/theme/tokens.ts`:

```ts
import type { TextStyle } from "react-native";

export const colors = {
  bg: "#F3F1E9",
  surface: "#FFFFFF",
  text: "#1A1A1A",
  muted: "#6B6B6B",
  border: "#E5E1D6",
  green: "#2E7D32",
  terracotta: "#E07A3E",
  halal: "#1F7A33",
  haram: "#C0362C",
  shubhah: "#B5852A",
  onDark: "#FFFFFF",
} as const;

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;

export const radius = { card: 18, pill: 999, input: 0 } as const;

export const type: Record<string, TextStyle> = {
  display: { fontSize: 34, fontWeight: "800", letterSpacing: 0.5 },
  h1: { fontSize: 26, fontWeight: "800" },
  h2: { fontSize: 20, fontWeight: "700" },
  body: { fontSize: 16, fontWeight: "400" },
  small: { fontSize: 13, fontWeight: "400" },
  label: { fontSize: 12, fontWeight: "600", letterSpacing: 0.5 },
};

export function verdictColor(v: string): string {
  return ({ halal: colors.halal, haram: colors.haram, shubhah: colors.shubhah } as Record<string, string>)[v] ?? colors.text;
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd mobile && npm test -- tokens` → PASS. `npm run typecheck` → clean.

- [ ] **Step 5: Commit**

```bash
git add mobile/src/theme/tokens.ts mobile/src/theme/__tests__/tokens.test.ts
git commit -m "feat(mobile): cream/light design tokens

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: UI primitives (Screen, Text, Button, Input, Card)

**Files:** `mobile/src/components/ui/{Screen,Text,Button,Input,Card}.tsx`, tests for Button + Input.

- [ ] **Step 1: Write the failing tests**

Create `mobile/src/components/ui/__tests__/ui.test.tsx`:

```tsx
import React from "react";
import { render, fireEvent } from "@testing-library/react-native";
import { Button } from "../Button";
import { Input } from "../Input";

test("Button renders its title and fires onPress", () => {
  const onPress = jest.fn();
  const { getByText } = render(<Button testID="b" title="Tap me" onPress={onPress} />);
  fireEvent.press(getByText("Tap me"));
  expect(onPress).toHaveBeenCalled();
});

test("Button is disabled while loading", () => {
  const onPress = jest.fn();
  const { getByTestId } = render(<Button testID="b" title="Go" onPress={onPress} loading />);
  fireEvent.press(getByTestId("b"));
  expect(onPress).not.toHaveBeenCalled();
});

test("Input shows label and error and forwards changes", () => {
  const onChangeText = jest.fn();
  const { getByText, getByTestId } = render(
    <Input testID="in" label="Email" error="Bad" value="" onChangeText={onChangeText} />,
  );
  expect(getByText("Email")).toBeTruthy();
  expect(getByText("Bad")).toBeTruthy();
  fireEvent.changeText(getByTestId("in"), "x");
  expect(onChangeText).toHaveBeenCalledWith("x");
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd mobile && npm test -- ui.test`
Expected: FAIL — `Cannot find module '../Button'`.

- [ ] **Step 3: Create the primitives**

Create `mobile/src/components/ui/Text.tsx`:

```tsx
import React from "react";
import { Text as RNText, TextProps } from "react-native";
import { colors, type as typeTokens } from "@/theme/tokens";

type Variant = keyof typeof typeTokens;

export function Text({
  variant = "body",
  color,
  caps,
  style,
  children,
  ...rest
}: TextProps & { variant?: Variant; color?: string; caps?: boolean }) {
  const content = caps && typeof children === "string" ? children.toUpperCase() : children;
  return (
    <RNText style={[typeTokens[variant], { color: color ?? colors.text }, style]} {...rest}>
      {content}
    </RNText>
  );
}

export function Heading(props: TextProps & { variant?: Variant; color?: string }) {
  return <Text variant="display" caps {...props} />;
}
```

Create `mobile/src/components/ui/Screen.tsx`:

```tsx
import React from "react";
import { View, ScrollView, ViewStyle } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { colors, space } from "@/theme/tokens";

export function Screen({
  children,
  scroll,
  style,
}: {
  children: React.ReactNode;
  scroll?: boolean;
  style?: ViewStyle;
}) {
  const inner = { padding: space.xl, gap: space.lg, ...style } as ViewStyle;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
      {scroll ? (
        <ScrollView contentContainerStyle={inner} keyboardShouldPersistTaps="handled">
          {children}
        </ScrollView>
      ) : (
        <View style={{ flex: 1, ...inner }}>{children}</View>
      )}
    </SafeAreaView>
  );
}
```

Create `mobile/src/components/ui/Button.tsx`:

```tsx
import React from "react";
import { Pressable, ActivityIndicator, ViewStyle } from "react-native";
import { Text } from "./Text";
import { colors, radius, space } from "@/theme/tokens";

type Variant = "primary" | "secondary" | "accent";

const BG: Record<Variant, string> = {
  primary: colors.text,
  secondary: "transparent",
  accent: colors.terracotta,
};
const FG: Record<Variant, string> = {
  primary: colors.onDark,
  secondary: colors.text,
  accent: colors.onDark,
};

export function Button({
  title,
  onPress,
  variant = "primary",
  loading,
  testID,
  style,
}: {
  title: string;
  onPress: () => void;
  variant?: Variant;
  loading?: boolean;
  testID?: string;
  style?: ViewStyle;
}) {
  return (
    <Pressable
      testID={testID}
      onPress={loading ? undefined : onPress}
      disabled={loading}
      style={({ pressed }) => ({
        backgroundColor: BG[variant],
        borderRadius: radius.pill,
        borderWidth: variant === "secondary" ? 1 : 0,
        borderColor: colors.border,
        paddingVertical: space.md + 2,
        paddingHorizontal: space.xl,
        alignItems: "center",
        opacity: pressed || loading ? 0.7 : 1,
        ...style,
      })}
    >
      {loading ? <ActivityIndicator color={FG[variant]} /> : <Text variant="h2" color={FG[variant]}>{title}</Text>}
    </Pressable>
  );
}
```

Create `mobile/src/components/ui/Input.tsx`:

```tsx
import React from "react";
import { View, TextInput, TextInputProps } from "react-native";
import { Text } from "./Text";
import { colors, space } from "@/theme/tokens";

export function Input({
  label,
  error,
  style,
  ...rest
}: TextInputProps & { label?: string; error?: string }) {
  return (
    <View style={{ gap: space.xs }}>
      {label ? <Text variant="label" color={colors.muted}>{label}</Text> : null}
      <TextInput
        placeholderTextColor={colors.muted}
        style={[
          { borderBottomWidth: 1, borderColor: colors.border, paddingVertical: space.sm, fontSize: 16, color: colors.text },
          style,
        ]}
        {...rest}
      />
      {error ? <Text variant="small" color={colors.haram}>{error}</Text> : null}
    </View>
  );
}
```

Create `mobile/src/components/ui/Card.tsx`:

```tsx
import React from "react";
import { View, ViewStyle } from "react-native";
import { colors, radius, space } from "@/theme/tokens";

export function Card({ children, style, testID }: { children: React.ReactNode; style?: ViewStyle; testID?: string }) {
  return (
    <View
      testID={testID}
      style={{
        backgroundColor: colors.surface,
        borderRadius: radius.card,
        padding: space.lg,
        gap: space.sm,
        shadowColor: "#000",
        shadowOpacity: 0.06,
        shadowRadius: 8,
        shadowOffset: { width: 0, height: 2 },
        elevation: 2,
        ...style,
      }}
    >
      {children}
    </View>
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd mobile && npm test -- ui.test` → PASS. `npm run typecheck` → clean.

- [ ] **Step 5: Commit**

```bash
git add mobile/src/components/ui mobile/src/components/ui/__tests__/ui.test.tsx
git commit -m "feat(mobile): UI primitives (Screen/Text/Button/Input/Card)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Restyle auth screens (login + register)

**Files:** `mobile/src/app/(auth)/login.tsx`, `register.tsx`

- [ ] **Step 1: Restyle login**

Replace `mobile/src/app/(auth)/login.tsx` with:

```tsx
import React, { useState } from "react";
import { Link, router } from "expo-router";
import { useAuth } from "@/auth/AuthProvider";
import { Screen } from "@/components/ui/Screen";
import { Heading, Text } from "@/components/ui/Text";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { colors } from "@/theme/tokens";

export default function LoginScreen() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit() {
    setError(null);
    setBusy(true);
    try {
      await signIn(email, password);
      router.replace("/(app)");
    } catch (e: any) {
      setError(e?.message ?? "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen scroll style={{ justifyContent: "center", flexGrow: 1 }}>
      <Heading>Log in</Heading>
      <Input testID="email" label="Email" placeholder="you@example.com" autoCapitalize="none"
        keyboardType="email-address" value={email} onChangeText={setEmail} />
      <Input testID="password" label="Password" placeholder="••••••••" secureTextEntry
        value={password} onChangeText={setPassword} />
      {error ? <Text variant="small" color={colors.haram}>{error}</Text> : null}
      <Button testID="submit" title="Log in" onPress={onSubmit} loading={busy} />
      <Link href="/(auth)/register" style={{ color: colors.terracotta, textAlign: "center" }}>
        Need an account? Register
      </Link>
    </Screen>
  );
}
```

- [ ] **Step 2: Restyle register**

Replace `mobile/src/app/(auth)/register.tsx` with:

```tsx
import React, { useState } from "react";
import { Link, router } from "expo-router";
import { registerUser } from "@/api/auth";
import { useAuth } from "@/auth/AuthProvider";
import { Screen } from "@/components/ui/Screen";
import { Heading, Text } from "@/components/ui/Text";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { colors } from "@/theme/tokens";

export default function RegisterScreen() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit() {
    setError(null);
    setBusy(true);
    try {
      await registerUser(email, password);
      await signIn(email, password);
      router.replace("/(app)");
    } catch (e: any) {
      setError(e?.message ?? "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen scroll style={{ justifyContent: "center", flexGrow: 1 }}>
      <Heading>Join</Heading>
      <Input testID="email" label="Email" placeholder="you@example.com" autoCapitalize="none"
        keyboardType="email-address" value={email} onChangeText={setEmail} />
      <Input testID="password" label="Password" placeholder="••••••••" secureTextEntry
        value={password} onChangeText={setPassword} />
      {error ? <Text variant="small" color={colors.haram}>{error}</Text> : null}
      <Button testID="submit" title="Register" onPress={onSubmit} loading={busy} />
      <Link href="/(auth)/login" style={{ color: colors.terracotta, textAlign: "center" }}>
        Have an account? Log in
      </Link>
    </Screen>
  );
}
```

- [ ] **Step 3: Run tests + typecheck**

Run: `cd mobile && npm test -- login` then `npm run typecheck`.
Expected: the login test passes (testIDs `email`/`password`/`submit` + the error message preserved); typecheck clean.

- [ ] **Step 4: Commit**

```bash
git add "mobile/src/app/(auth)/login.tsx" "mobile/src/app/(auth)/register.tsx"
git commit -m "style(mobile): restyle auth screens on the design system

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Restyle Home + VerdictResult

**Files:** `mobile/src/app/(app)/index.tsx`, `mobile/src/components/VerdictResult.tsx`

- [ ] **Step 1: Restyle VerdictResult**

Replace `mobile/src/components/VerdictResult.tsx` with:

```tsx
import React from "react";
import { View } from "react-native";
import type { VerdictOut } from "@/api/scan";
import { Card } from "@/components/ui/Card";
import { Text } from "@/components/ui/Text";
import { colors, space, verdictColor } from "@/theme/tokens";

export default function VerdictResult({ result }: { result: VerdictOut }) {
  return (
    <View style={{ gap: space.md }}>
      <Card style={{ borderLeftWidth: 6, borderLeftColor: verdictColor(result.verdict) }}>
        <Text testID="verdict" variant="h1" color={verdictColor(result.verdict)} caps>
          {result.verdict}
        </Text>
        <Text variant="body">{result.summary}</Text>
      </Card>
      <View style={{ gap: space.sm }}>
        {result.ingredients.map((ing, i) => (
          <Card key={i} testID="ingredient">
            <Text variant="h2">
              {ing.input} — <Text variant="h2" color={verdictColor(ing.status)}>{ing.status}</Text>
            </Text>
            <Text variant="small" color={colors.muted}>{ing.reason}</Text>
          </Card>
        ))}
      </View>
      <Text testID="disclaimer" variant="small" color={colors.muted}>{result.disclaimer}</Text>
    </View>
  );
}
```

- [ ] **Step 2: Restyle Home**

Replace `mobile/src/app/(app)/index.tsx` with:

```tsx
import React, { useState } from "react";
import { ActivityIndicator } from "react-native";
import { useMutation } from "@tanstack/react-query";
import { classify } from "@/api/scan";
import VerdictResult from "@/components/VerdictResult";
import { Screen } from "@/components/ui/Screen";
import { Heading, Text } from "@/components/ui/Text";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { colors } from "@/theme/tokens";

function parseIngredients(text: string): string[] {
  return text.split(/[\n,]+/).map((s) => s.trim()).filter(Boolean);
}

export default function Home() {
  const [text, setText] = useState("");
  const mutation = useMutation({ mutationFn: (items: string[]) => classify(items) });

  function onCheck() {
    const parsed = parseIngredients(text);
    if (parsed.length === 0) return;
    mutation.mutate(parsed);
  }

  return (
    <Screen scroll>
      <Heading>Check ingredients</Heading>
      <Input
        testID="ingredients"
        label="Ingredients"
        placeholder="One per line, or comma-separated"
        multiline
        value={text}
        onChangeText={setText}
        style={{ minHeight: 110, textAlignVertical: "top", borderBottomWidth: 0 }}
      />
      <Button testID="check" title="Check" onPress={onCheck} loading={mutation.isPending} />
      {mutation.isPending ? <ActivityIndicator /> : null}
      {mutation.isError ? (
        <Text testID="error" variant="small" color={colors.haram}>
          {(mutation.error as Error)?.message ?? "Something went wrong"}
        </Text>
      ) : null}
      {mutation.data ? <VerdictResult result={mutation.data} /> : null}
    </Screen>
  );
}
```

- [ ] **Step 3: Run tests + typecheck**

Run: `cd mobile && npm test -- "home|VerdictResult"` then `npm run typecheck`.
Expected: PASS — `verdict`/`ingredient`/`disclaimer` testIDs and the caps verdict, `pork fat`, `Not a religious ruling.` strings preserved; Home `ingredients`/`check`/`error` testIDs preserved.

- [ ] **Step 4: Commit**

```bash
git add "mobile/src/app/(app)/index.tsx" mobile/src/components/VerdictResult.tsx
git commit -m "style(mobile): restyle Home + VerdictResult on the design system

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Restyle History + Settings + tab bar

**Files:** `mobile/src/app/(app)/history.tsx`, `settings.tsx`, `_layout.tsx`

- [ ] **Step 1: Restyle History**

Replace `mobile/src/app/(app)/history.tsx` with:

```tsx
import React from "react";
import { View, FlatList, ActivityIndicator, RefreshControl } from "react-native";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listHistory, deleteHistory, clearHistory, type ScanHistoryOut } from "@/api/history";
import { timeAgo } from "@/lib/time";
import { Card } from "@/components/ui/Card";
import { Text } from "@/components/ui/Text";
import { Button } from "@/components/ui/Button";
import { colors, space, verdictColor } from "@/theme/tokens";

function Row({ item, onDelete }: { item: ScanHistoryOut; onDelete: (id: number) => void }) {
  return (
    <Card testID="history-row" style={{ marginBottom: space.md }}>
      <Text variant="h2" color={verdictColor(item.verdict)} caps>{item.verdict}</Text>
      <Text variant="body" numberOfLines={2}>{item.summary}</Text>
      <Text variant="small" color={colors.muted}>{item.scan_type} · {timeAgo(item.created_at)}</Text>
      <Button testID={`delete-${item.id}`} title="Delete" variant="secondary" onPress={() => onDelete(item.id)} />
    </Card>
  );
}

export default function HistoryScreen() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["history"], queryFn: () => listHistory() });
  const del = useMutation({
    mutationFn: (id: number) => deleteHistory(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["history"] }),
  });
  const clear = useMutation({
    mutationFn: () => clearHistory(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["history"] }),
  });

  if (query.isLoading) {
    return <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center" }}><ActivityIndicator /></View>;
  }
  if (query.isError) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center", padding: space.xl, gap: space.md }}>
        <Text testID="error" variant="body" color={colors.haram}>{(query.error as Error)?.message ?? "Failed to load history"}</Text>
        <Button testID="retry" title="Retry" onPress={() => query.refetch()} />
      </View>
    );
  }

  const data = query.data ?? [];
  return (
    <FlatList
      testID="history-list"
      style={{ backgroundColor: colors.bg }}
      data={data}
      keyExtractor={(it) => String(it.id)}
      contentContainerStyle={{ padding: space.lg }}
      refreshControl={<RefreshControl refreshing={query.isFetching} onRefresh={() => query.refetch()} />}
      ListHeaderComponent={data.length ? <View style={{ marginBottom: space.md }}><Button testID="clear-all" title="Clear all" variant="secondary" onPress={() => clear.mutate()} /></View> : null}
      ListEmptyComponent={<Text testID="empty" variant="body" color={colors.muted} style={{ textAlign: "center", marginTop: 48 }}>No scans yet</Text>}
      renderItem={({ item }) => <Row item={item} onDelete={del.mutate} />}
    />
  );
}
```

- [ ] **Step 2: Restyle Settings**

Replace `mobile/src/app/(app)/settings.tsx` with:

```tsx
import React from "react";
import { router } from "expo-router";
import { useAuth } from "@/auth/AuthProvider";
import { Screen } from "@/components/ui/Screen";
import { Text } from "@/components/ui/Text";
import { Button } from "@/components/ui/Button";
import { colors } from "@/theme/tokens";

export default function Settings() {
  const { email, signOut } = useAuth();
  return (
    <Screen style={{ justifyContent: "center" }}>
      <Text variant="label" color={colors.muted}>SIGNED IN AS</Text>
      <Text variant="h2">{email ?? "—"}</Text>
      <Button title="Log out" onPress={async () => { await signOut(); router.replace("/(auth)/login"); }} />
    </Screen>
  );
}
```

- [ ] **Step 3: Theme the tab bar**

Replace `mobile/src/app/(app)/_layout.tsx` with:

```tsx
import React from "react";
import { Redirect, Tabs } from "expo-router";
import { useAuth } from "@/auth/AuthProvider";
import { colors } from "@/theme/tokens";

export default function AppLayout() {
  const { status } = useAuth();
  if (status === "loading") return null;
  if (status === "unauthenticated") return <Redirect href="/(auth)/login" />;
  return (
    <Tabs
      screenOptions={{
        headerShown: true,
        headerStyle: { backgroundColor: colors.bg },
        headerTitleStyle: { fontWeight: "800", color: colors.text },
        headerShadowVisible: false,
        tabBarActiveTintColor: colors.terracotta,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: { backgroundColor: colors.bg, borderTopColor: colors.border },
      }}
    >
      <Tabs.Screen name="index" options={{ title: "Home" }} />
      <Tabs.Screen name="history" options={{ title: "History" }} />
      <Tabs.Screen name="settings" options={{ title: "Settings" }} />
    </Tabs>
  );
}
```

- [ ] **Step 4: Run the full suite + typecheck**

Run: `cd mobile && npm test` then `npm run typecheck`.
Expected: all 30 existing tests + the new tokens/ui tests pass; typecheck clean.

- [ ] **Step 5: Commit**

```bash
git add "mobile/src/app/(app)/history.tsx" "mobile/src/app/(app)/settings.tsx" "mobile/src/app/(app)/_layout.tsx"
git commit -m "style(mobile): restyle History/Settings + theme the tab bar

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Full verification + checkpoint

- [ ] **Step 1: Full verification**

Run from `mobile/`: `npm test` (all green), `npm run typecheck` (clean), and `npx expo export --platform web` (bundles — catches any import error from the restyle). Report counts.

- [ ] **Step 2: Update the checkpoint**

Edit `docs/CHECKPOINT.md`: refresh the branch section (SP22 merged; SP23 in flight); update the mobile test count; add an SP23 entry under "What's built" (the cream/light design system — tokens + `Screen`/`Text`/`Button`/`Input`/`Card` — and the restyle of every screen; note custom font is a fast-follow and camera screens are next).

- [ ] **Step 3: Commit**

```bash
git add docs/CHECKPOINT.md docs/superpowers/plans/2026-06-03-design-system.md
git commit -m "docs(mobile): SP23 done — design system + restyle

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the implementer

- **Never drop a test ID or an asserted string.** Each restyle keeps `testID=`s and the visible verdict/reason/disclaimer/empty strings the existing tests check. Run the relevant test after each screen.
- The `@/` alias resolves to `src/` (jest `moduleNameMapper` + tsconfig `paths`).
- `Button` uses `Pressable`; RNTL's `fireEvent.press` works on it, and `loading` disables the press (tested).
- The Home `Input` uses `borderBottomWidth: 0` + `minHeight` so the multiline box reads as a card-ish field rather than a single underline.
- Run `npm test` serially (the config already sets `maxWorkers: 1` + `--forceExit`).
- The app can't be run here; "done" = `npm test` green + `npm run typecheck` clean + web export OK. On-device visual check is the user's.
- Every commit message ends with the trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- This branch is from `main`; final `--no-ff` merge to `main` after review.
