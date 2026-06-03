const url = process.env.EXPO_PUBLIC_API_URL;

// In dev the default points at localhost; on a device set EXPO_PUBLIC_API_URL to
// the dev machine's LAN IP (or use `expo start --tunnel`) with the backend running.
export const API_URL: string = url ?? "http://localhost:8000";
