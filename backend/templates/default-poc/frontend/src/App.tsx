// A generated PoC's entire frontend: load the spec, render it.
//
// The generator writes dashboard.config.json and the backend endpoints it
// names. Everything visual lives in src/kit/, which the platform owns.
import { Dashboard } from "./kit/render";
import "./kit/theme.css";
import type { DashboardSpec } from "./kit/types";
import spec from "./dashboard.config.json";

export default function App() {
  return <Dashboard spec={spec as DashboardSpec} />;
}
