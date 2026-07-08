# Silent-Drift Sentinel, mobile on-call app

An Expo (React Native) companion app for the on-call ML engineer. It connects to the same live agent as the web dashboard, streams the drift diagnosis, and lets you approve the catalog write-back from your phone. No mock data; it talks to the deployed agent at `https://agent.16-59-185-192.nip.io`.

The flow: open the app, tap **Run diagnosis**, watch the agent detect the drift and walk DataHub lineage to the upstream cause, then tap **Approve write-back** to write `drift_causation` + the tag + the RCA document onto the model and raise the incident, exactly what the web dashboard does, from your pocket.

## Tech

- Expo managed workflow (SDK 57), TypeScript.
- `react-native-sse` consumes the agent's SSE stream (`/api/stream`, named `trace` and `awaiting_approval` events). Native fetch bypasses CORS, so no backend change is needed.
- Plain `fetch` for the approve POST (`/api/approve`).

## Run it

Dev (fastest, on a simulator or your phone via Expo Go):

```bash
cd apps/mobile
npm install
npx expo start          # press i for the iOS simulator, a for Android, or scan the QR in Expo Go
```

On your own iPhone (native, needs Xcode, free Apple ID works for your own device):

```bash
npx expo run:ios
```

## Build an installable Android APK for judges (free, no Apple account)

```bash
npm install -g eas-cli
eas login                                  # your Expo account
eas build -p android --profile preview     # produces a downloadable, directly installable APK
```

EAS returns a URL/QR; a judge downloads and installs the APK on any Android device (accept the "unknown source" prompt) and gets the full SSE + approve flow. iOS install on someone else's device requires a paid Apple Developer account ($99/yr) for TestFlight or ad-hoc; a free Apple ID only runs on your own device, so iOS is best shown live in the demo video.
