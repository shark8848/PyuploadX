import { useMemo } from "react";
import { DatePicker, Select, Space } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import * as api from "../api/client";

interface Props {
  config: api.ClientConfig;
  /** JSON string as accepted by the upload API; undefined means permanent. */
  value?: string;
  onChange: (value: string | undefined) => void;
}

interface ParsedLifecycle {
  mode: string;
  action?: string;
  ttl_seconds?: number;
  expires_at?: string;
}

const MODE_LABELS: Record<string, string> = {
  permanent: "永久保存",
  ttl: "定时过期（TTL）",
  temporary: "临时文件（TTL）",
  sliding_ttl: "滑动过期（访问后续期）",
  expires_at: "指定时间过期",
};

const ACTION_LABELS: Record<string, string> = {
  delete: "到期删除",
  notify: "到期通知",
  none: "仅记录不处理",
};

const TTL_PRESETS: { label: string; seconds: number }[] = [
  { label: "1 小时", seconds: 3600 },
  { label: "1 天", seconds: 86400 },
  { label: "7 天", seconds: 604800 },
  { label: "30 天", seconds: 2592000 },
  { label: "90 天", seconds: 7776000 },
  { label: "180 天", seconds: 15552000 },
  { label: "365 天", seconds: 31536000 },
];

const TTL_LIKE_MODES = new Set(["ttl", "temporary", "sliding_ttl"]);

export function LifecycleSelect({ config, value, onChange }: Props) {
  const parsed = useMemo<ParsedLifecycle>(() => {
    if (!value) {
      return { mode: "permanent" };
    }
    try {
      const data = JSON.parse(value) as ParsedLifecycle;
      return { ...data, mode: data.mode || "permanent", action: data.action ?? "delete" };
    } catch {
      return { mode: "permanent" };
    }
  }, [value]);

  const modeOptions = useMemo(
    () =>
      config.lifecycle.allowed_modes
        .filter((mode) => MODE_LABELS[mode])
        .filter((mode) => mode !== "permanent" || config.lifecycle.permanent_allowed)
        .map((mode) => ({ value: mode, label: MODE_LABELS[mode] })),
    [config],
  );

  const ttlOptions = useMemo(() => {
    const { minimum_ttl_seconds: min, maximum_ttl_seconds: max } = config.lifecycle;
    return TTL_PRESETS.filter((preset) => preset.seconds >= min && preset.seconds <= max);
  }, [config]);

  const actionOptions = useMemo(
    () =>
      config.lifecycle.allowed_actions.map((action) => ({
        value: action,
        label: ACTION_LABELS[action] ?? action,
      })),
    [config],
  );

  const isTtlMode = TTL_LIKE_MODES.has(parsed.mode);

  const emit = (next: ParsedLifecycle) => {
    if (next.mode === "permanent") {
      onChange(undefined);
      return;
    }
    const payload: Record<string, unknown> = { mode: next.mode, action: next.action ?? "delete" };
    if (TTL_LIKE_MODES.has(next.mode)) {
      payload.ttl_seconds = next.ttl_seconds;
    }
    if (next.mode === "expires_at") {
      payload.expires_at = next.expires_at;
    }
    onChange(JSON.stringify(payload));
  };

  const selectMode = (mode: string) => {
    if (mode === "permanent") {
      onChange(undefined);
      return;
    }
    const defaultTtl =
      config.lifecycle.default_policy?.ttl_seconds ??
      ttlOptions.find((preset) => preset.seconds >= config.lifecycle.minimum_ttl_seconds)?.seconds;
    if (mode === "expires_at") {
      emit({
        mode,
        action: parsed.action,
        expires_at: dayjs().add(1, "day").toISOString(),
      });
      return;
    }
    emit({ mode, action: parsed.action, ttl_seconds: defaultTtl });
  };

  if (!config.lifecycle.enabled) {
    return null;
  }

  return (
    <Space size={8} wrap>
      <Select
        value={parsed.mode}
        onChange={selectMode}
        options={modeOptions}
        style={{ width: 180 }}
      />
      {isTtlMode && (
        <>
          <Select
            value={parsed.ttl_seconds ?? ttlOptions[0]?.seconds}
            onChange={(seconds: number) => emit({ ...parsed, ttl_seconds: seconds })}
            options={ttlOptions.map((preset) => ({ value: preset.seconds, label: preset.label }))}
            style={{ width: 110 }}
          />
          <Select
            value={parsed.action ?? "delete"}
            onChange={(action: string) => emit({ ...parsed, action })}
            options={actionOptions}
            style={{ width: 120 }}
          />
        </>
      )}
      {parsed.mode === "expires_at" && (
        <>
          <DatePicker
            showTime
            value={parsed.expires_at ? dayjs(parsed.expires_at) : undefined}
            onChange={(date: Dayjs | null) => {
              if (date) {
                emit({ ...parsed, expires_at: date.toISOString() });
              }
            }}
            disabledDate={(current: Dayjs) =>
              current.isBefore(dayjs().add(config.lifecycle.minimum_ttl_seconds - 60, "second"))
            }
            style={{ width: 200 }}
          />
          <Select
            value={parsed.action ?? "delete"}
            onChange={(action: string) => emit({ ...parsed, action })}
            options={actionOptions}
            style={{ width: 120 }}
          />
        </>
      )}
    </Space>
  );
}
