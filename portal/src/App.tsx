import { useCallback, useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { App as AntApp, Button, ConfigProvider, Layout as AntLayout, Menu, Spin } from "antd";
import { CloudUpload, FolderTree, LogOut } from "lucide-react";
import zhCN from "antd/locale/zh_CN";
import * as api from "./api/client";
import LoginPage from "./pages/LoginPage";
import { UploadPage } from "./pages/UploadPage";
import FilesPage from "./pages/FilesPage";

const { Header, Content } = AntLayout;

type AuthState = "loading" | "login" | "ready";

function Shell({
  config,
  onLogout,
}: {
  config: api.ClientConfig;
  onLogout: () => void;
}) {
  const navigate = useNavigate();
  const location = useLocation();
  return (
    <AntLayout style={{ minHeight: "100vh" }}>
      <Header
        style={{
          background: "#fff",
          borderBottom: "1px solid #f0f0f0",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 24px",
          position: "sticky",
          top: 0,
          zIndex: 10,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 32 }}>
          <div style={{ fontWeight: 700, fontSize: 16, color: "#1f2937" }}>PyUploadX</div>
          <Menu
            mode="horizontal"
            selectedKeys={[location.pathname]}
            items={[
              { key: "/files", icon: <FolderTree size={16} />, label: "文件浏览" },
              { key: "/upload", icon: <CloudUpload size={16} />, label: "上传" },
            ]}
            onClick={(entry) => navigate(entry.key)}
            style={{ borderBottom: "none", minWidth: 260 }}
          />
        </div>
        <Button icon={<LogOut size={16} />} onClick={onLogout}>
          退出登录
        </Button>
      </Header>
      <Content
        style={
          location.pathname === "/files"
            ? { padding: 0, width: "100%" }
            : { padding: 24, maxWidth: 1100, width: "100%", margin: "0 auto" }
        }
      >
        <Routes>
          <Route path="/upload" element={<UploadPage config={config} />} />
          <Route path="/files" element={<FilesPage config={config} />} />
          <Route path="*" element={<Navigate to="/files" replace />} />
        </Routes>
      </Content>
    </AntLayout>
  );
}

export function App() {
  const [auth, setAuth] = useState<AuthState>("loading");
  const [config, setConfig] = useState<api.ClientConfig | null>(null);

  const enterApp = useCallback(() => {
    api
      .fetchConfig()
      .then((cfg) => {
        setConfig(cfg);
        setAuth("ready");
      })
      .catch(() => setAuth("login"));
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
    return <Spin fullscreen tip="正在连接上传服务…" />;
  }

  if (auth === "login") {
    return (
      <ConfigProvider locale={zhCN}>
        <LoginPage onSuccess={enterApp} />
      </ConfigProvider>
    );
  }

  return (
    <ConfigProvider locale={zhCN}>
      <AntApp>
        <BrowserRouter>
          <Shell config={config!} onLogout={handleLogout} />
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  );
}
