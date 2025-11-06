const TRUE_VALUES: ReadonlySet<string> = new Set(["1", "true", "yes", "on", "enabled"]);
const FALSE_VALUES: ReadonlySet<string> = new Set(["0", "false", "no", "off", "disabled"]);

const parseBoolean = (value: string | undefined, fallback: boolean): boolean => {
  if (!value) {
    return fallback;
  }
  const normalised = value.trim().toLowerCase();
  if (TRUE_VALUES.has(normalised)) {
    return true;
  }
  if (FALSE_VALUES.has(normalised)) {
    return false;
  }
  return fallback;
};

export type FeatureFlags = {
  biLayer1: boolean;
  biLayer2: boolean;
  biLayer3: boolean;
  knimeBridge: boolean;
  realtimeUpdates: boolean;
  geoSaudiMap: boolean;
};

export type FeatureFlagKey = keyof FeatureFlags;

const defaults: FeatureFlags = {
  biLayer1: true,
  biLayer2: true,
  biLayer3: true,
  knimeBridge: true,
  realtimeUpdates: false,
  geoSaudiMap: false,
};

const sources: Record<FeatureFlagKey, string> = {
  biLayer1: "NEXT_PUBLIC_FEATURE_BI_LAYER1",
  biLayer2: "NEXT_PUBLIC_FEATURE_BI_LAYER2",
  biLayer3: "NEXT_PUBLIC_FEATURE_BI_LAYER3",
  knimeBridge: "NEXT_PUBLIC_FEATURE_KNIME_BRIDGE",
  realtimeUpdates: "NEXT_PUBLIC_FEATURE_REALTIME_UPDATES",
  geoSaudiMap: "NEXT_PUBLIC_FEATURE_GEO_SAUDI_MAP",
};

export const featureFlags: FeatureFlags = {
  biLayer1: parseBoolean(process.env[sources.biLayer1], defaults.biLayer1),
  biLayer2: parseBoolean(process.env[sources.biLayer2], defaults.biLayer2),
  biLayer3: parseBoolean(process.env[sources.biLayer3], defaults.biLayer3),
  knimeBridge: parseBoolean(process.env[sources.knimeBridge], defaults.knimeBridge),
  realtimeUpdates: parseBoolean(process.env[sources.realtimeUpdates], defaults.realtimeUpdates),
  geoSaudiMap: parseBoolean(process.env[sources.geoSaudiMap], defaults.geoSaudiMap),
};

export const featureFlagMetadata: Record<FeatureFlagKey, { env: string; description: string }> = {
  biLayer1: {
    env: sources.biLayer1,
    description: "Controls access to the foundational Layer 1 charts and KPI cards.",
  },
  biLayer2: {
    env: sources.biLayer2,
    description: "Enables the analytical Layer 2 insights panel and assistants.",
  },
  biLayer3: {
    env: sources.biLayer3,
    description: "Toggles the strategic intelligence layer with advanced visuals.",
  },
  knimeBridge: {
    env: sources.knimeBridge,
    description: "Gates the KNIME bridge results panel that surfaces workflow outputs.",
  },
  realtimeUpdates: {
    env: sources.realtimeUpdates,
    description: "Activates live refresh hooks that push real-time metric updates.",
  },
  geoSaudiMap: {
    env: sources.geoSaudiMap,
    description: "Enables the Saudi Arabia geo map visual once the dataset is ready.",
  },
};

export const isFeatureEnabled = (flag: FeatureFlagKey): boolean => featureFlags[flag];

export const listFeatureFlags = (): Array<{ key: FeatureFlagKey; value: boolean; env: string; description: string }> =>
  (Object.keys(featureFlags) as FeatureFlagKey[]).map((key) => ({
    key,
    value: featureFlags[key],
    env: featureFlagMetadata[key].env,
    description: featureFlagMetadata[key].description,
  }));
