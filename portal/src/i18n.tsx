import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

export type Lang = "zh" | "en";

type Messages = Record<string, string>;

const ZH: Messages = {
  "common.save": "保存",
  "common.cancel": "取消",
  "common.create": "创建",
  "common.delete": "删除",
  "common.download": "下载",
  "common.copyLink": "复制下载链接",
  "files.deleteFailed": "删除失败：{msg}",
  "nav.files": "文件浏览",
  "nav.upload": "上传",
  "nav.storage": "存储",
  "nav.collapse": "收起导航",
  "nav.expand": "展开导航",
  "sidebar.createBucket": "新建桶",
  "sidebar.settings": "设置",
  "sidebar.logout": "退出",
  "sidebar.logoutTip": "退出登录",
  "sidebar.language": "语言",
  "sidebar.theme": "主题",
  "tree.all": "全部文件",

  "login.subtitle": "文件上传与共享服务",
  "login.placeholder": "请输入 API Key",
  "login.button": "登录",
  "login.success": "登录成功",
  "login.invalid": "API Key 无效，请检查后重试",
  "login.required": "请输入 API Key",

  "files.title": "文件浏览",
  "files.prefix": "前缀：",
  "files.status": "状态：",
  "files.sort": "排序：",
  "files.statusActive": "正常",
  "files.statusDeleted": "已删除",
  "files.statusAll": "全部",
  "files.sortName": "按名称",
  "files.sortCreated": "按创建时间",
  "files.empty": "没有匹配的文件。",
  "files.total": "共 {count} 个文件",
  "files.loadFailed": "加载失败：{msg}",
  "files.linkCopied": "下载链接已复制（15 分钟有效）",
  "files.deleted": "文件已删除",
  "files.deleteTitle": "确认删除",
  "files.deleteContent": "确定删除 {path}？",
  "files.selected": "已选 {count} 项",
  "files.batchDownload": "批量下载",
  "files.batchDelete": "批量删除",
  "files.batchDeleteTitle": "确认批量删除",
  "files.batchDeleteContent": "确定删除选中的 {count} 个文件？",
  "files.deletedMany": "已删除 {count} 个文件",
  "files.colObject": "对象",
  "files.colBucket": "Bucket",
  "files.colSize": "大小",
  "files.colType": "类型",
  "files.colStatus": "状态",
  "files.colExpires": "过期时间",
  "files.colCreated": "创建时间",
  "files.colActions": "操作",

  "bucket.createTitle": "新建存储桶",
  "bucket.placeholder": "例如 my-bucket",
  "bucket.hint": "3-63 位：小写字母、数字、点、中划线；不能以点开头/结尾，不能包含连续的点。",
  "bucket.required": "请输入存储桶名称",
  "bucket.created": "存储桶 {name} 创建成功",
  "bucket.exists": "存储桶 {name} 已存在",
  "bucket.invalidName": "桶名不合法：3-63 位小写字母、数字、点、中划线",
  "bucket.createFailed": "创建失败：{msg}",

  "settings.title": "设置",
  "settings.storage": "存储",
  "settings.uploads": "上传",
  "settings.lifecycle": "生命周期",
  "settings.loadFailed": "加载设置失败：{msg}",
  "settings.saveFailed": "保存失败：{msg}",
  "settings.saved": "设置已保存",
  "settings.defaultBucket": "默认存储桶",
  "settings.defaultBucketHint": "上传等操作缺省使用的存储桶。",
  "settings.presignExpiry": "下载链接默认有效期（秒）",
  "settings.presignRange": "范围 {min} - {max} 秒。",
  "settings.maxFileSize": "单文件大小上限（字节）",
  "settings.directThreshold": "直传阈值（字节）",
  "settings.defaultMode": "默认上传模式",
  "settings.defaultPartSize": "分片默认大小（字节）",
  "settings.sessionExpiry": "上传会话有效期（秒）",
  "settings.modeAutomatic": "自动",
  "settings.modeProxy": "代理",
  "settings.modePresigned": "预签名",
  "settings.lifecycleMode": "默认生命周期模式",
  "settings.lifecycleAction": "默认到期动作",
  "settings.lifecycleTtl": "默认 TTL（秒）",
  "settings.backendInfo": "存储后端信息（只读，修改配置后需重启生效）",
  "settings.backend": "后端类型",
  "settings.rootPath": "本地存储根路径",
  "settings.endpoint": "服务端点",
  "settings.region": "区域",
  "settings.accessKeyConfigured": "已配置访问密钥",
  "settings.forcePathStyle": "强制路径样式",
  "settings.allowedBuckets": "允许的存储桶",
  "settings.capabilities": "能力",
  "settings.storageHint":
    "本地路径、S3 端点与密钥属于启动配置：请在 config/settings.yaml 或环境变量中修改后重启服务；运行时可调整默认桶、上传与生命周期参数。",

  "lifecycle.permanent": "永久保存",
  "lifecycle.ttl": "定时过期（TTL）",
  "lifecycle.temporary": "临时文件（TTL）",
  "lifecycle.slidingTtl": "滑动过期（访问后续期）",
  "lifecycle.expiresAt": "指定时间过期",
  "lifecycle.actionDelete": "到期删除",
  "lifecycle.actionNotify": "到期通知",
  "lifecycle.actionNone": "仅记录不处理",
  "lifecycle.ttl1h": "1 小时",
  "lifecycle.ttl1d": "1 天",
  "lifecycle.ttl7d": "7 天",
  "lifecycle.ttl30d": "30 天",
  "lifecycle.ttl90d": "90 天",
  "lifecycle.ttl180d": "180 天",
  "lifecycle.ttl365d": "365 天",

  "upload.title": "文件上传",
  "upload.bucket": "Bucket：",
  "upload.prefix": "目标前缀：",
  "upload.prefixPlaceholder": "例如 artists/10001",
  "upload.lifecycle": "生命周期：",

  "drop.hint": "拖放文件到此处，或点击选择",
  "drop.files": "选择文件",
  "drop.directory": "选择目录",

  "queue.empty": "暂无上传任务",
  "queue.pending": "等待中",
  "queue.uploading": "上传中",
  "queue.paused": "已暂停",
  "queue.completed": "已完成",
  "queue.failed": "失败",
  "queue.pause": "暂停",
  "queue.resume": "继续",
  "queue.reselect": "重新选择",
  "queue.retry": "重试",
  "queue.cancel": "取消",
  "queue.download": "下载",

  "app.connecting": "正在连接上传服务…",
};

const EN: Messages = {
  "common.save": "Save",
  "common.cancel": "Cancel",
  "common.create": "Create",
  "common.delete": "Delete",
  "common.download": "Download",
  "common.copyLink": "Copy link",
  "files.deleteFailed": "Delete failed: {msg}",
  "nav.files": "Files",
  "nav.upload": "Upload",
  "nav.storage": "Storage",
  "nav.collapse": "Collapse",
  "nav.expand": "Expand",
  "sidebar.createBucket": "New bucket",
  "sidebar.settings": "Settings",
  "sidebar.logout": "Log out",
  "sidebar.logoutTip": "Log out",
  "sidebar.language": "Language",
  "sidebar.theme": "Theme",
  "tree.all": "All files",

  "login.subtitle": "File upload & sharing service",
  "login.placeholder": "Enter API Key",
  "login.button": "Log in",
  "login.success": "Signed in",
  "login.invalid": "Invalid API Key, please try again",
  "login.required": "Please enter an API Key",

  "files.title": "Files",
  "files.prefix": "Prefix:",
  "files.status": "Status:",
  "files.sort": "Sort:",
  "files.statusActive": "Active",
  "files.statusDeleted": "Deleted",
  "files.statusAll": "All",
  "files.sortName": "By name",
  "files.sortCreated": "By created time",
  "files.empty": "No matching files.",
  "files.total": "{count} files",
  "files.loadFailed": "Failed to load: {msg}",
  "files.linkCopied": "Download link copied (valid 15 min)",
  "files.deleted": "File deleted",
  "files.deleteTitle": "Confirm delete",
  "files.deleteContent": "Delete {path}?",
  "files.selected": "{count} selected",
  "files.batchDownload": "Download all",
  "files.batchDelete": "Delete all",
  "files.batchDeleteTitle": "Confirm batch delete",
  "files.batchDeleteContent": "Delete {count} selected files?",
  "files.deletedMany": "Deleted {count} files",
  "files.colObject": "Object",
  "files.colBucket": "Bucket",
  "files.colSize": "Size",
  "files.colType": "Type",
  "files.colStatus": "Status",
  "files.colExpires": "Expires",
  "files.colCreated": "Created",
  "files.colActions": "Actions",

  "bucket.createTitle": "New bucket",
  "bucket.placeholder": "e.g. my-bucket",
  "bucket.hint": "3-63 chars: lowercase letters, digits, dots and hyphens; no leading/trailing dot, no consecutive dots.",
  "bucket.required": "Please enter a bucket name",
  "bucket.created": "Bucket {name} created",
  "bucket.exists": "Bucket {name} already exists",
  "bucket.invalidName": "Invalid bucket name: 3-63 chars of lowercase letters, digits, dots and hyphens",
  "bucket.createFailed": "Create failed: {msg}",

  "settings.title": "Settings",
  "settings.storage": "Storage",
  "settings.uploads": "Upload",
  "settings.lifecycle": "Lifecycle",
  "settings.loadFailed": "Failed to load settings: {msg}",
  "settings.saveFailed": "Save failed: {msg}",
  "settings.saved": "Settings saved",
  "settings.defaultBucket": "Default bucket",
  "settings.defaultBucketHint": "Bucket used by default for uploads.",
  "settings.presignExpiry": "Default download link expiry (s)",
  "settings.presignRange": "Range {min} - {max} seconds.",
  "settings.maxFileSize": "Max file size (bytes)",
  "settings.directThreshold": "Direct upload threshold (bytes)",
  "settings.defaultMode": "Default upload mode",
  "settings.defaultPartSize": "Default part size (bytes)",
  "settings.sessionExpiry": "Upload session expiry (s)",
  "settings.modeAutomatic": "Automatic",
  "settings.modeProxy": "Proxy",
  "settings.modePresigned": "Presigned",
  "settings.lifecycleMode": "Default lifecycle mode",
  "settings.lifecycleAction": "Default expiry action",
  "settings.lifecycleTtl": "Default TTL (s)",
  "settings.backendInfo": "Storage backend info (read-only; change config and restart)",
  "settings.backend": "Backend",
  "settings.rootPath": "Local storage root",
  "settings.endpoint": "Endpoint",
  "settings.region": "Region",
  "settings.accessKeyConfigured": "Access key configured",
  "settings.forcePathStyle": "Force path style",
  "settings.allowedBuckets": "Allowed buckets",
  "settings.capabilities": "Capabilities",
  "settings.storageHint":
    "Local paths, S3 endpoints and keys are bootstrap config: edit config/settings.yaml or environment variables and restart. Default bucket, upload and lifecycle parameters are adjustable at runtime.",

  "lifecycle.permanent": "Keep forever",
  "lifecycle.ttl": "Expire after TTL",
  "lifecycle.temporary": "Temporary (TTL)",
  "lifecycle.slidingTtl": "Sliding expiry",
  "lifecycle.expiresAt": "Expire at time",
  "lifecycle.actionDelete": "Delete",
  "lifecycle.actionNotify": "Notify",
  "lifecycle.actionNone": "Log only",
  "lifecycle.ttl1h": "1 hour",
  "lifecycle.ttl1d": "1 day",
  "lifecycle.ttl7d": "7 days",
  "lifecycle.ttl30d": "30 days",
  "lifecycle.ttl90d": "90 days",
  "lifecycle.ttl180d": "180 days",
  "lifecycle.ttl365d": "365 days",

  "upload.title": "Upload files",
  "upload.bucket": "Bucket:",
  "upload.prefix": "Target prefix:",
  "upload.prefixPlaceholder": "e.g. artists/10001",
  "upload.lifecycle": "Lifecycle:",

  "drop.hint": "Drop files here or click to choose",
  "drop.files": "Choose files",
  "drop.directory": "Choose directory",

  "queue.empty": "No uploads yet",
  "queue.pending": "Pending",
  "queue.uploading": "Uploading",
  "queue.paused": "Paused",
  "queue.completed": "Completed",
  "queue.failed": "Failed",
  "queue.pause": "Pause",
  "queue.resume": "Resume",
  "queue.reselect": "Re-select",
  "queue.retry": "Retry",
  "queue.cancel": "Cancel",
  "queue.download": "Download",

  "app.connecting": "Connecting to upload service…",
};

const MESSAGES: Record<Lang, Messages> = { zh: ZH, en: EN };

interface I18nValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nValue>({
  lang: "zh",
  setLang: () => undefined,
  t: (key) => key,
});

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    const saved = localStorage.getItem("portal-lang");
    return saved === "en" ? "en" : "zh";
  });

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    localStorage.setItem("portal-lang", next);
  }, []);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => {
      let text = MESSAGES[lang][key] ?? MESSAGES.zh[key] ?? key;
      if (vars) {
        for (const [name, value] of Object.entries(vars)) {
          text = text.replaceAll(`{${name}}`, String(value));
        }
      }
      return text;
    },
    [lang],
  );

  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  return useContext(I18nContext);
}
