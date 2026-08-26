import { useEffect, useState } from "react";
import * as api from "./api/client";
import { UploadPage } from "./pages/UploadPage";

export function App() {
  const [token, setToken] = useState<string>(() => sessionStorage.getItem("portal-token") ?? "");
  const [config, setConfig] = useState<api.ClientConfig | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setConfig(null);
      return;
    }
    api.setApiToken(token);
    sessionStorage.setItem("portal-token", token);
    api
      .fetchConfig()
      .then(setConfig)
      .catch((err) => {
        setError(err instanceof Error ? err.message : String(err));
        setConfig(null);
      });
  }, [token]);

  return (
    <main className="app">
      <header className="header">
        <h1>PyUploadX</h1>
        <label className="token-input">
          API Key（仅保存在会话内，不写入 LocalStorage）
          <input
            type="password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="粘贴 X-API-Key"
          />
        </label>
      </header>
      {error ? <p className="error-text">配置加载失败：{error}</p> : null}
      {config ? (
        <UploadPage config={config} />
      ) : (
        !token && <p className="empty">请输入 API Key 以连接上传服务。</p>
      )}
    </main>
  );
}
