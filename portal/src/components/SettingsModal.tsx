import { useCallback, useEffect, useState } from "react";
import { App, Descriptions, InputNumber, Modal, Select, Spin, Tabs } from "antd";
import * as api from "../api/client";
import { useI18n } from "../i18n";

interface SettingsForm {
  storage: {
    default_bucket: string;
    presign_default_expires_seconds: number;
  };
  uploads: {
    maximum_file_size_bytes: number;
    direct_upload_threshold_bytes: number;
    default_mode: string;
    multipart: { default_part_size_bytes: number };
    session: { expires_after_seconds: number };
  };
  lifecycle: { default_policy: { mode: string; action: string; ttl_seconds: number } };
}

interface Props {
  config: api.ClientConfig;
  open: boolean;
  onClose: () => void;
  onSaved: () => Promise<void>;
}

function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

export function SettingsModal({ config, open, onClose, onSaved }: Props) {
  const { t } = useI18n();
  const { message: messageApi } = App.useApp();
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settings, setSettings] = useState<api.RuntimeSettings | null>(null);
  const [settingsForm, setSettingsForm] = useState<SettingsForm | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    setSettingsLoading(true);
    api
      .getSettings()
      .then((data) => {
        setSettings(data);
        setSettingsForm({
          storage: {
            default_bucket: data.storage.default_bucket,
            presign_default_expires_seconds: data.storage.presign_default_expires_seconds,
          },
          uploads: {
            maximum_file_size_bytes: data.uploads.maximum_file_size_bytes,
            direct_upload_threshold_bytes: data.uploads.direct_upload_threshold_bytes,
            default_mode: data.uploads.default_mode,
            multipart: { default_part_size_bytes: data.uploads.multipart.default_part_size_bytes },
            session: { expires_after_seconds: data.uploads.session.expires_after_seconds },
          },
          lifecycle: { default_policy: { ...data.lifecycle.default_policy } },
        });
      })
      .catch((err) => {
        messageApi.error(t("settings.loadFailed", { msg: errorText(err) }));
      })
      .finally(() => setSettingsLoading(false));
  }, [open, messageApi, t]);

  const saveSettings = useCallback(async () => {
    if (!settingsForm) {
      return;
    }
    setSettingsSaving(true);
    try {
      await api.updateSettings({
        storage: settingsForm.storage,
        uploads: settingsForm.uploads,
        lifecycle: settingsForm.lifecycle,
      });
      messageApi.success(t("settings.saved"));
      onClose();
      await onSaved();
    } catch (err) {
      messageApi.error(t("settings.saveFailed", { msg: errorText(err) }));
    } finally {
      setSettingsSaving(false);
    }
  }, [settingsForm, messageApi, onClose, onSaved, t]);

  const storageInfo = settings?.storage.info;

  return (
    <Modal
      title={t("settings.title")}
      open={open}
      onOk={() => void saveSettings()}
      confirmLoading={settingsSaving}
      onCancel={onClose}
      okText={t("common.save")}
      cancelText={t("common.cancel")}
      destroyOnHidden
      width={620}
    >
      {settingsLoading || !settingsForm || !settings ? (
        <div style={{ textAlign: "center", padding: 24 }}>
          <Spin />
        </div>
      ) : (
        <Tabs
          items={[
            {
              key: "storage",
              label: t("settings.storage"),
              children: (
                <div className="settings-form">
                  <div className="settings-field">
                    <label>{t("settings.defaultBucket")}</label>
                    <Select
                      value={settingsForm.storage.default_bucket}
                      onChange={(value) =>
                        setSettingsForm((form) =>
                          form
                            ? {
                                ...form,
                                storage: { ...form.storage, default_bucket: value },
                              }
                            : form,
                        )
                      }
                      options={(storageInfo?.allowed_buckets ?? config.uploads.allowed_buckets).map(
                        (name) => ({ value: name, label: name }),
                      )}
                      style={{ width: "100%" }}
                    />
                    <div className="form-hint">{t("settings.defaultBucketHint")}</div>
                  </div>
                  <div className="settings-field">
                    <label>{t("settings.presignExpiry")}</label>
                    <InputNumber
                      min={60}
                      max={settings.storage.maximum_expires_seconds}
                      value={settingsForm.storage.presign_default_expires_seconds}
                      onChange={(value) =>
                        setSettingsForm((form) =>
                          form
                            ? {
                                ...form,
                                storage: {
                                  ...form.storage,
                                  presign_default_expires_seconds: value ?? 900,
                                },
                              }
                            : form,
                        )
                      }
                      style={{ width: "100%" }}
                    />
                    <div className="form-hint">
                      {t("settings.presignRange", {
                        min: 60,
                        max: settings.storage.maximum_expires_seconds,
                      })}
                    </div>
                  </div>
                  <div className="settings-divider" />
                  <div className="settings-field">
                    <label>{t("settings.backendInfo")}</label>
                    {storageInfo && (
                      <Descriptions size="small" column={1} bordered>
                        <Descriptions.Item label={t("settings.backend")}>
                          {storageInfo.backend}
                        </Descriptions.Item>
                        {storageInfo.root_path && (
                          <Descriptions.Item label={t("settings.rootPath")}>
                            {storageInfo.root_path}
                          </Descriptions.Item>
                        )}
                        {storageInfo.endpoint && (
                          <Descriptions.Item label={t("settings.endpoint")}>
                            {storageInfo.endpoint}
                          </Descriptions.Item>
                        )}
                        {storageInfo.region && (
                          <Descriptions.Item label={t("settings.region")}>
                            {storageInfo.region}
                          </Descriptions.Item>
                        )}
                        {storageInfo.access_key_configured !== undefined && (
                          <Descriptions.Item label={t("settings.accessKeyConfigured")}>
                            {storageInfo.access_key_configured ? "✓" : "—"}
                          </Descriptions.Item>
                        )}
                        {storageInfo.force_path_style !== undefined && (
                          <Descriptions.Item label={t("settings.forcePathStyle")}>
                            {String(storageInfo.force_path_style)}
                          </Descriptions.Item>
                        )}
                        <Descriptions.Item label={t("settings.allowedBuckets")}>
                          {storageInfo.allowed_buckets.join(", ")}
                        </Descriptions.Item>
                        <Descriptions.Item label={t("settings.capabilities")}>
                          {Object.entries(storageInfo.capabilities)
                            .filter(([, enabled]) => enabled)
                            .map(([name]) => name)
                            .join(", ") || "—"}
                        </Descriptions.Item>
                      </Descriptions>
                    )}
                    <div className="form-hint">{t("settings.storageHint")}</div>
                  </div>
                </div>
              ),
            },
            {
              key: "uploads",
              label: t("settings.uploads"),
              children: (
                <div className="settings-form">
                  <div className="settings-field">
                    <label>{t("settings.maxFileSize")}</label>
                    <InputNumber
                      min={1}
                      value={settingsForm.uploads.maximum_file_size_bytes}
                      onChange={(value) =>
                        setSettingsForm((form) =>
                          form
                            ? {
                                ...form,
                                uploads: { ...form.uploads, maximum_file_size_bytes: value ?? 0 },
                              }
                            : form,
                        )
                      }
                      style={{ width: "100%" }}
                    />
                  </div>
                  <div className="settings-field">
                    <label>{t("settings.directThreshold")}</label>
                    <InputNumber
                      min={0}
                      value={settingsForm.uploads.direct_upload_threshold_bytes}
                      onChange={(value) =>
                        setSettingsForm((form) =>
                          form
                            ? {
                                ...form,
                                uploads: {
                                  ...form.uploads,
                                  direct_upload_threshold_bytes: value ?? 0,
                                },
                              }
                            : form,
                        )
                      }
                      style={{ width: "100%" }}
                    />
                  </div>
                  <div className="settings-field">
                    <label>{t("settings.defaultMode")}</label>
                    <Select
                      value={settingsForm.uploads.default_mode}
                      onChange={(value) =>
                        setSettingsForm((form) =>
                          form
                            ? { ...form, uploads: { ...form.uploads, default_mode: value } }
                            : form,
                        )
                      }
                      options={[
                        { value: "automatic", label: t("settings.modeAutomatic") },
                        { value: "proxy", label: t("settings.modeProxy") },
                        { value: "presigned", label: t("settings.modePresigned") },
                      ]}
                      style={{ width: "100%" }}
                    />
                  </div>
                  <div className="settings-field">
                    <label>{t("settings.defaultPartSize")}</label>
                    <InputNumber
                      min={settings.uploads.multipart.minimum_part_size_bytes}
                      max={settings.uploads.multipart.maximum_part_size_bytes}
                      value={settingsForm.uploads.multipart.default_part_size_bytes}
                      onChange={(value) =>
                        setSettingsForm((form) =>
                          form
                            ? {
                                ...form,
                                uploads: {
                                  ...form.uploads,
                                  multipart: {
                                    ...form.uploads.multipart,
                                    default_part_size_bytes: value ?? 0,
                                  },
                                },
                              }
                            : form,
                        )
                      }
                      style={{ width: "100%" }}
                    />
                    <div className="form-hint">
                      {settings.uploads.multipart.minimum_part_size_bytes} -{" "}
                      {settings.uploads.multipart.maximum_part_size_bytes}
                    </div>
                  </div>
                  <div className="settings-field">
                    <label>{t("settings.sessionExpiry")}</label>
                    <InputNumber
                      min={60}
                      max={settings.uploads.session.maximum_lifetime_seconds}
                      value={settingsForm.uploads.session.expires_after_seconds}
                      onChange={(value) =>
                        setSettingsForm((form) =>
                          form
                            ? {
                                ...form,
                                uploads: {
                                  ...form.uploads,
                                  session: {
                                    ...form.uploads.session,
                                    expires_after_seconds: value ?? 60,
                                  },
                                },
                              }
                            : form,
                        )
                      }
                      style={{ width: "100%" }}
                    />
                  </div>
                </div>
              ),
            },
            {
              key: "lifecycle",
              label: t("settings.lifecycle"),
              children: (
                <div className="settings-form">
                  <div className="settings-field">
                    <label>{t("settings.lifecycleMode")}</label>
                    <Select
                      value={settingsForm.lifecycle.default_policy.mode}
                      onChange={(value) =>
                        setSettingsForm((form) =>
                          form
                            ? {
                                ...form,
                                lifecycle: {
                                  default_policy: { ...form.lifecycle.default_policy, mode: value },
                                },
                              }
                            : form,
                        )
                      }
                      options={settings.lifecycle.allowed_modes.map((mode) => ({
                        value: mode,
                        label: mode,
                      }))}
                      style={{ width: "100%" }}
                    />
                  </div>
                  <div className="settings-field">
                    <label>{t("settings.lifecycleAction")}</label>
                    <Select
                      value={settingsForm.lifecycle.default_policy.action}
                      onChange={(value) =>
                        setSettingsForm((form) =>
                          form
                            ? {
                                ...form,
                                lifecycle: {
                                  default_policy: {
                                    ...form.lifecycle.default_policy,
                                    action: value,
                                  },
                                },
                              }
                            : form,
                        )
                      }
                      options={settings.lifecycle.allowed_actions.map((action) => ({
                        value: action,
                        label: action,
                      }))}
                      style={{ width: "100%" }}
                    />
                  </div>
                  <div className="settings-field">
                    <label>{t("settings.lifecycleTtl")}</label>
                    <InputNumber
                      min={settings.lifecycle.minimum_ttl_seconds}
                      max={settings.lifecycle.maximum_ttl_seconds}
                      value={settingsForm.lifecycle.default_policy.ttl_seconds}
                      onChange={(value) =>
                        setSettingsForm((form) =>
                          form
                            ? {
                                ...form,
                                lifecycle: {
                                  default_policy: {
                                    ...form.lifecycle.default_policy,
                                    ttl_seconds: value ?? settings.lifecycle.minimum_ttl_seconds,
                                  },
                                },
                              }
                            : form,
                        )
                      }
                      style={{ width: "100%" }}
                    />
                    <div className="form-hint">
                      {settings.lifecycle.minimum_ttl_seconds} - {settings.lifecycle.maximum_ttl_seconds}
                    </div>
                  </div>
                </div>
              ),
            },
          ]}
        />
      )}
    </Modal>
  );
}
