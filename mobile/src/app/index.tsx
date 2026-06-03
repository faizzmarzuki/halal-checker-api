import { View, Text } from "react-native";

// Placeholder home for the foundation scaffold. SP17 Task 6 replaces the route
// tree with the auth flow and the authenticated shell.
export default function Index() {
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: 24 }}>
      <Text style={{ fontSize: 18 }}>Halal Checker — mobile foundation</Text>
    </View>
  );
}
