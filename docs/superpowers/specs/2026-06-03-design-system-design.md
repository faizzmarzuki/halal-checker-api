# Sub-project 23 — Design System + Restyle (Design)

Date: 2026-06-03

Give the mobile app a real look: a small cream/light design system (tokens +
reusable UI components) inspired by the user's references (Honest Greens / CREME),
then restyle every existing screen to use it. Functional behaviour and all test
IDs are preserved, so the existing tests keep passing. Branched from `main`; lives
under `mobile/`. No camera screens (SP24), no custom fonts yet (system bold;
custom display font is a fast-follow), no animations.

## Visual direction (cream / light)

Warm cream background, heavy black ALL-CAPS headings, pill buttons, underline
inputs, generous spacing; green + terracotta accents; verdict colours pop on cream.

## Tokens — `src/theme/tokens.ts`

```ts
export const colors = {
  bg: "#F3F1E9",        // warm cream
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
};
export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 };
export const radius = { card: 18, pill: 999, input: 0 };
export const type = {
  display: { fontSize: 34, fontWeight: "800", letterSpacing: 0.5 },
  h1: { fontSize: 26, fontWeight: "800" },
  h2: { fontSize: 20, fontWeight: "700" },
  body: { fontSize: 16, fontWeight: "400" },
  small: { fontSize: 13, fontWeight: "400" },
  label: { fontSize: 12, fontWeight: "600", letterSpacing: 0.5 },
} as const;
export const verdictColor = (v: string): string =>
  ({ halal: colors.halal, haram: colors.haram, shubhah: colors.shubhah }[v] ?? colors.text);
```

## UI components — `src/components/ui/`

- **`Screen`** — `SafeAreaView` with the cream bg + horizontal padding; `scroll`
  prop wraps content in a `ScrollView` (used by forms/Home).
- **`Text`** — `<Text variant="display|h1|h2|body|small|label" color? caps?>`,
  applying the type tokens + colour; `caps` upper-cases the content.
- **`Button`** — pill (`borderRadius: pill`), variants `primary` (black bg / white
  text), `secondary` (transparent + border), `accent` (terracotta bg / white);
  `loading` shows a spinner and disables; forwards `testID`, `onPress`, `title`.
- **`Input`** — label (token `label`, muted) above a bottom-bordered `TextInput`
  (no box), optional `error` text below in `haram`; forwards `testID`, value,
  `onChangeText`, and the usual TextInput props (`secureTextEntry`, `multiline`,
  `keyboardType`, `autoCapitalize`, `placeholder`).
- **`Card`** — white, `radius.card`, subtle shadow/elevation, padded.

Each is small, presentational, and independently testable.

## Restyle (preserve every testID + visible text the tests assert)

Test IDs that MUST remain: `email`, `password`, `submit`, `ingredients`, `check`,
`verdict`, `ingredient`, `disclaimer`, `error`, `history-row`, `delete-<id>`,
`clear-all`, `empty`, `retry`. Visible strings asserted: `HARAM`/verdict caps,
`pork fat`, `Not a religious ruling.`, `No scans yet`, `sugar, lard`, error
messages.

- **`(auth)/login.tsx` / `register.tsx`** — `Screen`, a bold caps `Heading`
  ("LOG IN" / "JOIN"), `Input`s for email/password, a primary `Button` ("Log in" /
  "Register") keeping `testID="submit"`, the navigation `Link`.
- **`(app)/index.tsx` (Home)** — `Screen scroll`, heading "CHECK INGREDIENTS",
  a multiline `Input` (`testID="ingredients"`), a primary `Button`
  (`testID="check"`), the spinner/error, and `VerdictResult`.
- **`components/VerdictResult.tsx`** — the verdict as a bold caps badge in a
  `Card` coloured by `verdictColor`; each ingredient a row (`testID="ingredient"`)
  with the input bold + status coloured + reason muted; `disclaimer` small/muted.
- **`(app)/history.tsx`** — each scan a `Card` (`testID="history-row"`): verdict
  caps coloured, summary, `scan_type · timeAgo`, a `secondary` Delete `Button`
  (`testID="delete-<id>"`); a `clear-all` button header; `empty`/`error`/`retry`
  preserved.
- **`(app)/settings.tsx`** — `Screen`, the signed-in email, a primary Logout
  `Button`.
- **`(app)/_layout.tsx`** — `Tabs` `screenOptions` themed: cream `tabBarStyle`,
  active tint terracotta, header cream/bold.
- **`app/_layout.tsx`** — keep the providers; optionally set the status-bar style.

## Testing

- Existing 30 tests stay green (behaviour + testIDs unchanged; RNTL doesn't assert
  styles).
- New unit tests for the UI primitives:
  - `Button`: renders the title, calls `onPress`, and is disabled while `loading`
    (a press does nothing).
  - `Input`: renders the label, forwards `onChangeText`, shows the `error` text.
  - `tokens.verdictColor`: maps halal/haram/shubhah and falls back for unknown.

Commands: `cd mobile && npm test`, `npm run typecheck`.

## Out of scope / fast-follow

Custom display font (heavy grotesk via `expo-font` + async load) — fast-follow.
Camera screens (SP24). Animations / parallax. A dark theme / toggle.

## Conventions

Branch `sub-project-23-design-system` (from `main`); spec here; plan in
`docs/superpowers/plans/`; TDD where it applies (Jest); `--no-ff` merge to `main`;
delete the branch. Commit trailer:
`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
