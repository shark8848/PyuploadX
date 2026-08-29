import { useCallback, useState } from "react";
import { App, Button, Input, Modal, Tooltip } from "antd";
import {
  FolderPlus,
  Languages,
  LogOut,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  Sun,
} from "lucide-react";
import * as api from "../api/client";
import { BucketTree } from "./BucketTree";
import { SettingsModal } from "./SettingsModal";
import { useI18n } from "../i18n";
import { useTheme } from "../theme";

interface Props {
  config: api.ClientConfig;
  bucket: string;
  prefix: string;
  onSelect: (bucket: string, prefix: string) => void;
  onConfigRefresh: () => Promise<void>;
  onLogout: () => void;
}

function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

export function SideNav({ config, bucket, prefix, onSelect, onConfigRefresh, onLogout }: Props) {
  const { t, lang, setLang } = useI18n();
  const { mode, toggle: toggleTheme } = useTheme();
  const { message: messageApi } = App.useApp();
  const [navCollapsed, setNavCollapsed] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [newBucketName, setNewBucketName] = useState("");
  const [creating, setCreating] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const handleCreateBucket = useCallback(async () => {
    const name = newBucketName.trim();
    if (!name) {
      messageApi.warning(t("bucket.required"));
      return;
    }
    setCreating(true);
    try {
      await api.createBucket(name);
      messageApi.success(t("bucket.created", { name }));
      setCreateOpen(false);
      setNewBucketName("");
      await onConfigRefresh();
    } catch (err) {
      const code = errorText(err);
      if (code === "BUCKET_ALREADY_EXISTS") {
        messageApi.error(t("bucket.exists", { name }));
      } else if (code === "INVALID_BUCKET_NAME") {
        messageApi.error(t("bucket.invalidName"));
      } else {
        messageApi.error(t("bucket.createFailed", { msg: code }));
      }
    } finally {
      setCreating(false);
    }
  }, [newBucketName, messageApi, onConfigRefresh, t]);

  const switchLang = useCallback(() => {
    setLang(lang === "zh" ? "en" : "zh");
  }, [lang, setLang]);

  return (
    <aside className={`file-nav${navCollapsed ? " collapsed" : ""}`}>
      <div className="file-nav-header">
        {!navCollapsed && <span className="file-nav-title">{t("nav.storage")}</span>}
        <Tooltip title={navCollapsed ? t("sidebar.createBucket") : undefined} placement="right">
          <Button
            type="text"
            size="small"
            icon={<FolderPlus size={16} />}
            onClick={() => setCreateOpen(true)}
            className="file-nav-create"
            aria-label={t("sidebar.createBucket")}
          >
            {!navCollapsed && t("sidebar.createBucket")}
          </Button>
        </Tooltip>
        <Button
          type="text"
          size="small"
          icon={navCollapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
          onClick={() => setNavCollapsed((value) => !value)}
          aria-label={navCollapsed ? t("nav.expand") : t("nav.collapse")}
        />
      </div>
      <div className="file-nav-body">
        <BucketTree
          config={config}
          bucket={bucket}
          prefix={prefix}
          onSelect={onSelect}
          onConfigRefresh={onConfigRefresh}
        />
      </div>
      <div className="file-nav-footer">
        <Tooltip title={navCollapsed ? t("sidebar.settings") : undefined} placement="right">
          <Button type="text" icon={<Settings size={16} />} onClick={() => setSettingsOpen(true)}>
            {!navCollapsed && t("sidebar.settings")}
          </Button>
        </Tooltip>
        <Tooltip title={navCollapsed ? t("sidebar.language") : undefined} placement="right">
          <Button type="text" icon={<Languages size={16} />} onClick={switchLang}>
            {!navCollapsed && (lang === "zh" ? "EN" : "中文")}
          </Button>
        </Tooltip>
        <Tooltip title={navCollapsed ? t("sidebar.theme") : undefined} placement="right">
          <Button
            type="text"
            icon={mode === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            onClick={toggleTheme}
          >
            {!navCollapsed && (mode === "dark" ? t("sidebar.theme") + " · ☀" : t("sidebar.theme") + " · ☾")}
          </Button>
        </Tooltip>
        <Tooltip title={navCollapsed ? t("sidebar.logoutTip") : undefined} placement="right">
          <Button type="text" icon={<LogOut size={16} />} onClick={onLogout}>
            {!navCollapsed && t("sidebar.logout")}
          </Button>
        </Tooltip>
      </div>
      <Modal
        title={t("bucket.createTitle")}
        open={createOpen}
        onOk={() => void handleCreateBucket()}
        confirmLoading={creating}
        onCancel={() => {
          setCreateOpen(false);
          setNewBucketName("");
        }}
        okText={t("common.create")}
        cancelText={t("common.cancel")}
        destroyOnHidden
      >
        <Input
          value={newBucketName}
          onChange={(event) => setNewBucketName(event.target.value)}
          onPressEnter={() => void handleCreateBucket()}
          placeholder={t("bucket.placeholder")}
          maxLength={63}
          autoFocus
        />
        <div className="form-hint">{t("bucket.hint")}</div>
      </Modal>
      <SettingsModal
        config={config}
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSaved={onConfigRefresh}
      />
    </aside>
  );
}
