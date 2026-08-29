import { useCallback, useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { App as AntApp, ConfigProvider, Layout as AntLayout, Menu, Spin, theme as antTheme } from "antd";
import { CloudUpload, FolderTree } from "lucide-react";
import zhCN from "antd/locale/zh_CN";
import enUS from "antd/locale/en_US";
import dayjs from "dayjs";
import "dayjs/locale/zh-cn";
import * as api from "./api/client";
import { I18nProvider, useI18n } from "./i18n";
import { ThemeProvider, useTheme } from "./theme";
import LoginPage from "./pages/LoginPage";
import { UploadPage } from "./pages/UploadPage";
import FilesPage from "./pages/FilesPage";
import { SideNav } from "./components/SideNav";

const { Header, Content } = AntLayout;

type AuthState = "loading" | "login" | "ready";

function Shell({
  config,
  onLogout,
  onConfigRefresh,
}: {
  config: api.ClientConfig;
  onLogout: () => void;
  onConfigRefresh: () => Promise<void>;
}) {
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const [bucket, setBucket] = useState("");
  const [prefix, setPrefix] = useState("");

  useEffect(() => {
    dayjs.locale(lang === "zh" ? "zh-cn" : "en");
  }, [lang]);

  return (
    <AntLayout style={{ minHeight: "100vh" }}>
      <Header className="app-header">
        <div className="app-header-inner">
          <div style={{ fontWeight: 700, fontSize: 16 }}>PyUploadX</div>
          <Menu
            mode="horizontal"
            selectedKeys={[location.pathname]}
            items={[
              { key: "/files", icon: <FolderTree size={16} />, label: t("nav.files") },
              { key: "/upload", icon: <CloudUpload size={16} />, label: t("nav.upload") },
            ]}
            onClick={(entry) => navigate(entry.key)}
            style={{ borderBottom: "none", minWidth: 260, background: "transparent" }}
          />
        </div>
      </Header>
      <Content className="app-content app-content-flush">
        <div className="app-body">
          <SideNav
            config={config}
            bucket={bucket}
            prefix={prefix}
            onSelect={(nextBucket, nextPrefix) => {
              setBucket(nextBucket);
              setPrefix(nextPrefix);
            }}
            onConfigRefresh={onConfigRefresh}
            onLogout={onLogout}
          />
          <div className="app-body-main">
            <Routes>
              <Route
                path="/upload"
                element={
                  <UploadPage
                    config={config}
                    bucket={bucket}
                    prefix={prefix}
                    onPrefixChange={setPrefix}
                  />
                }
              />
              <Route
                path="/files"
                element={
                  <FilesPage
                    bucket={bucket}
                    prefix={prefix}
                    onPrefixChange={setPrefix}
                  />
                }
              />
              <Route path="*" element={<Navigate to="/files" replace />} />
            </Routes>
          </div>
        </div>
      </Content>
    </AntLayout>
  );
}

function AuthenticatedApp() {
  const [auth, setAuth] = useState<AuthState>("loading");
  const [config, setConfig] = useState<api.ClientConfig | null>(null);
  const { t } = useI18n();

  const enterApp = useCallback(() => {
    api
      .fetchConfig()
      .then(async (cfg) => {
        // client-config 是公开端点；仍需确认当前上下文已鉴权（本地无 token
        // 且 nginx 未注入时进入登录页），否则所有受保护请求都会 401。
        if (await api.probeAuthenticated()) {
          setConfig(cfg);
          setAuth("ready");
        } else {
          setAuth("login");
        }
      })
      .catch(() => setAuth("login"));
  }, []);

  const handleConfigRefresh = useCallback(async () => {
    setConfig(await api.refreshConfig());
  }, []);

  useEffect(() => {
    const saved = localStorage.getItem("portal-token");
    if (saved) {
      api.setApiToken(saved);
    }
    // 无手动 token 时也尝试加载配置：nginx 会自动注入 X-API-Key（start-stack.sh），
    // 此时免登录；注入不可用时进入登录页。
    void enterApp();
  }, [enterApp]);

  const handleLogout = useCallback(() => {
    localStorage.removeItem("portal-token");
    api.setApiToken(null);
    setConfig(null);
    setAuth("login");
  }, []);

  if (auth === "loading") {
    return <Spin fullscreen description={t("app.connecting")} />;
  }

  if (auth === "login") {
    return <LoginPage onSuccess={enterApp} />;
  }

  return (
    <AntApp>
      <BrowserRouter>
        <Shell config={config!} onLogout={handleLogout} onConfigRefresh={handleConfigRefresh} />
      </BrowserRouter>
    </AntApp>
  );
}

function ThemedApp() {
  const { lang } = useI18n();
  const { mode } = useTheme();

  return (
    <ConfigProvider
      locale={lang === "zh" ? zhCN : enUS}
      theme={{
        algorithm: mode === "dark" ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm,
        token: {
          borderRadius: 8,
          fontSize: 14,
        },
      }}
    >
      <AuthenticatedApp />
    </ConfigProvider>
  );
}

export function App() {
  return (
    <I18nProvider>
      <ThemeProvider>
        <ThemedApp />
      </ThemeProvider>
    </I18nProvider>
  );
}
